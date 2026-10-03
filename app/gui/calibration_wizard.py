"""
Assistente de calibração: marcar os controles do jogo sobre uma imagem do jogo.

Calibrar clicando na tela ao vivo exigiria converter pixels do monitor em pixels
da página, passando pela posição da janela, pela moldura do navegador e pela
escala do Windows - e qualquer um deles pode mudar entre a calibração e a
execução. Trabalhar sobre uma captura tirada pelo CDP elimina a cadeia inteira:
a imagem É a página, então um clique nela já é uma coordenada da página.

Os passos são a execução em ordem, e o assistente a executa: um passo que marca
um botão o pressiona antes de abrir o passo seguinte (um ponto, no próprio
ponto; uma área de botão, no centro dela), para que o jogo chegue à tela que o
próximo passo descreve. Um passo que marca só uma área de validação não tem o
que pressionar e segue adiante sem clicar.
"""

import queue
import threading
import time
import tkinter as tk
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from ..browser import Browser
from ..calibration import STEPS, STORE_STEPS, Calibration, Step
from ..collector import icon_name, recognise_icon
from ..i18n import tr
from ..vision import Vision, changed_fraction, expand
from . import (ACCENT, BUTTON_BG, DARK_BG, ERROR_COLOR, HOVER_BG, MUTED, OK_COLOR, PANEL_BG, TEXT,
               WARN_COLOR, place)

MAGNIFIER_SIZE = 150
MAGNIFIER_ZOOM = 4
DRAG_THRESHOLD = 6          # pixels do canvas: menos que isto é um clique, não um arrasto
# Abaixo disto o clique não mudou nada na tela. O limite é baixo de propósito:
# trocar um botão por outro, ou gastar uma aceleração, mexe em menos de 1% da página.
MIN_SCREEN_CHANGE = 0.002


class CalibrationWizard(ctk.CTkToplevel):
    """Grava pontos e regiões marcados sobre uma captura da página do jogo."""

    def __init__(self, master, browser: Browser, vision: Vision, calibration: Calibration,
                 click_delay: float = 1.5, just_launched: bool = False,
                 on_close: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.browser = browser
        self.vision = vision
        self.calibration = calibration
        self.click_delay = max(1.2, float(click_delay))
        self.just_launched = just_launched
        self.on_close = on_close

        # A ordem dos passos nesta janela: a de STEPS, a não ser que os passos
        # da loja sejam adiados para o fim (ver defer_store).
        self.steps = list(STEPS)
        self.deferred = False
        missing = self.calibration.missing_steps()
        self.index = next((i for i, step in enumerate(self.steps) if step.name in missing), 0)
        self.corners: List[Tuple[int, int]] = []
        self.press: Optional[Tuple[int, int]] = None
        self.screenshot = None            # numpy BGR, pixels da página
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.display_scale = 1.0
        self.chain = True
        # True enquanto uma thread opera o jogo. Os cliques na captura são
        # ignorados nesse meio tempo: a captura na tela já está velha.
        self.busy = False
        self.prompt = ""
        self.rows: dict = {}
        # O Tk não é thread-safe: a thread só deixa o resultado aqui e a thread
        # principal o aplica no seu próprio ritmo.
        self.results: queue.Queue = queue.Queue()

        self.title(tr("wizard.window_title"))
        place(self, 1320, 820)
        self.minsize(1000, 600)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self._build()
        self.after(250, self.refresh_capture)
        self.after(150, self._drain_results)
        # No Windows uma Toplevel do customtkinter nasce atrás da janela principal.
        self.after(300, self.lift)

    # ---------------------------------------------------------------------- UI
    def _build(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        # --- passos
        left = ctk.CTkFrame(body, fg_color=PANEL_BG, corner_radius=8, width=300)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text=tr("wizard.steps"), font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=ACCENT).pack(anchor="w", padx=12, pady=(12, 2))
        ctk.CTkLabel(left, text=tr("wizard.steps_hint"), font=ctk.CTkFont(size=11), text_color=MUTED,
                     wraplength=270, justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        steps_list = ctk.CTkScrollableFrame(left, fg_color=DARK_BG)
        steps_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for position in range(len(self.steps)):
            button = ctk.CTkButton(steps_list, text="", anchor="w", height=30, fg_color="transparent",
                                   hover_color=BUTTON_BG, font=ctk.CTkFont(size=12),
                                   command=lambda index=position: self.go_to(index))
            button.pack(fill="x", pady=1)
            self.rows[position] = button

        # --- captura e instrução
        right = ctk.CTkFrame(body, fg_color=PANEL_BG, corner_radius=8)
        right.pack(side="left", fill="both", expand=True)

        header = ctk.CTkFrame(right, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))

        self.magnifier = tk.Canvas(header, width=MAGNIFIER_SIZE, height=MAGNIFIER_SIZE, bg=DARK_BG,
                                   highlightthickness=1, highlightbackground=HOVER_BG)
        self.magnifier.pack(side="right", padx=(10, 0))

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", fill="both", expand=True)
        self.lbl_progress = ctk.CTkLabel(titles, text="", font=ctk.CTkFont(size=11), text_color=MUTED)
        self.lbl_progress.pack(anchor="w")
        self.lbl_title = ctk.CTkLabel(titles, text="", font=ctk.CTkFont(size=17, weight="bold"),
                                      text_color=ACCENT)
        self.lbl_title.pack(anchor="w")
        self.lbl_instruction = ctk.CTkLabel(titles, text="", font=ctk.CTkFont(size=13), justify="left",
                                            wraplength=640, text_color=TEXT)
        self.lbl_instruction.pack(anchor="w", pady=(6, 0))

        self.lbl_state = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                      text_color=MUTED, justify="left", anchor="w", wraplength=880)
        self.lbl_state.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        self._text_width = 0
        right.bind("<Configure>", self._fit_text)

        self.canvas = tk.Canvas(right, bg=DARK_BG, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=14, pady=(4, 8))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Configure>", lambda _event: self._draw())

        # --- rodapé
        ctk.CTkButton(footer, text=tr("wizard.close"), width=100, height=36, fg_color=BUTTON_BG,
                      hover_color=HOVER_BG, command=self.close).pack(side="left")
        self.chk_chain = ctk.CTkCheckBox(footer, text=tr("wizard.auto_advance"),
                                         font=ctk.CTkFont(size=11), command=self._toggle_chain)
        self.chk_chain.select()
        self.chk_chain.pack(side="left", padx=16)

        self.btn_defer = ctk.CTkButton(footer, text=tr("wizard.defer_store"), width=220, height=36,
                                       fg_color="#9e6a03", hover_color="#bb8009", command=self.defer_store)

        for label, width, colour, hover, command in (
            ("wizard.test", 150, "#1f6feb", "#388bfd", self.test_step),
            ("wizard.refresh", 170, None, None, self.refresh_capture),
            ("wizard.skip", 90, BUTTON_BG, HOVER_BG, self.skip),
            ("wizard.redo", 90, BUTTON_BG, HOVER_BG, self.redo),
        ):
            options = {"fg_color": colour, "hover_color": hover} if colour else {}
            ctk.CTkButton(footer, text=tr(label), width=width, height=36, command=command,
                          **options).pack(side="right", padx=4)

        self._show_step()

    def _fit_text(self, event):
        """Quebra os textos na largura que o painel tem agora, para nada ficar cortado."""
        width = int(event.width / (ctk.ScalingTracker.get_window_scaling(self) or 1.0)) - 40
        if width < 200 or abs(width - self._text_width) < 8:
            return
        self._text_width = width
        self.lbl_state.configure(wraplength=width)
        self.lbl_instruction.configure(wraplength=max(200, width - MAGNIFIER_SIZE - 30))

    def _toggle_chain(self):
        self.chain = bool(self.chk_chain.get())

    def _set_state(self, message: str, colour: str = MUTED):
        self.lbl_state.configure(text=message, text_color=colour)

    # ----------------------------------------------------------------- captura
    def refresh_capture(self):
        """Tira uma nova imagem da página do jogo e a mostra."""
        if self.busy:
            return
        self._set_state(tr("wizard.capturing"))
        self.update_idletasks()
        try:
            self.browser.ensure_attached()
            self.browser.refresh_dpr()
            image = self.browser.capture()
        except Exception as exc:  # noqa: BLE001
            self._set_state(tr("wizard.capture_failed", error=exc), ERROR_COLOR)
            return
        if image is None or image.size == 0:
            self._set_state(tr("wizard.capture_empty"), ERROR_COLOR)
            return

        self.screenshot = image
        self.corners.clear()
        self._draw()
        if self.just_launched:
            self.just_launched = False
            self._set_state(tr("wizard.login_first"), WARN_COLOR)
        else:
            self._set_state(tr("wizard.capture_done", width=image.shape[1], height=image.shape[0])
                            + "\n" + self.prompt)

    def _viewport(self) -> Tuple[int, int]:
        return (self.screenshot.shape[1], self.screenshot.shape[0])

    def _draw(self):
        """Redesenha a captura, ajustada ao espaço, e o que já está calibrado neste passo."""
        self.canvas.delete("all")
        if self.screenshot is None:
            return

        canvas_w = max(self.canvas.winfo_width(), 10)
        canvas_h = max(self.canvas.winfo_height(), 10)
        height, width = self.screenshot.shape[:2]
        self.display_scale = min(canvas_w / width, canvas_h / height, 1.0)

        shown = (max(1, int(width * self.display_scale)), max(1, int(height * self.display_scale)))
        rgb = cv2.cvtColor(self.screenshot, cv2.COLOR_BGR2RGB)
        self.photo = ImageTk.PhotoImage(Image.fromarray(rgb).resize(shown, Image.LANCZOS))
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

        # O que foi gravado só é desenhado sobre uma captura do mesmo tamanho:
        # em outro tamanho de página as coordenadas não são as desta imagem.
        step = self._current()
        if self.calibration.step_viewports.get(step.name) == self._viewport():
            if step.is_rectangle:
                region = self.calibration.regions.get(step.name)
                if region:
                    self._outline((region["left"], region["top"]),
                                  (region["left"] + region["width"], region["top"] + region["height"]),
                                  OK_COLOR)
                    if step.acts:
                        self._crosshair(region["left"] + region["width"] // 2,
                                        region["top"] + region["height"] // 2, OK_COLOR)
            else:
                point = self.calibration.points.get(step.name)
                if point:
                    self._crosshair(point[0], point[1], OK_COLOR)

        if len(self.corners) == 1:
            self._crosshair(self.corners[0][0], self.corners[0][1], WARN_COLOR)

    def _to_canvas(self, x: int, y: int) -> Tuple[float, float]:
        return x * self.display_scale, y * self.display_scale

    def _to_page(self, x: int, y: int) -> Tuple[int, int]:
        """Posição do canvas em pixels da página, presa dentro da captura."""
        height, width = self.screenshot.shape[:2]
        page_x = int(round(x / self.display_scale))
        page_y = int(round(y / self.display_scale))
        return max(0, min(page_x, width - 1)), max(0, min(page_y, height - 1))

    def _crosshair(self, x: int, y: int, colour: str):
        cx, cy = self._to_canvas(x, y)
        self.canvas.create_line(cx - 9, cy, cx + 9, cy, fill=colour, width=2)
        self.canvas.create_line(cx, cy - 9, cx, cy + 9, fill=colour, width=2)
        self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, outline=colour, width=2)

    def _outline(self, corner_a, corner_b, colour: str, tag: str = ""):
        ax, ay = self._to_canvas(*corner_a)
        bx, by = self._to_canvas(*corner_b)
        self.canvas.create_rectangle(ax, ay, bx, by, outline=colour, width=2, tags=tag)

    def _draw_magnifier(self, page_x: int, page_y: int):
        """A lupa em volta do ponteiro, na resolução original: os alvos são pequenos."""
        self.magnifier.delete("all")
        half = MAGNIFIER_SIZE // (2 * MAGNIFIER_ZOOM)
        height, width = self.screenshot.shape[:2]
        left, top = max(0, page_x - half), max(0, page_y - half)
        right, bottom = min(width, page_x + half), min(height, page_y + half)
        if right - left < 2 or bottom - top < 2:
            return
        crop = cv2.cvtColor(self.screenshot[top:bottom, left:right], cv2.COLOR_BGR2RGB)
        zoomed = Image.fromarray(crop).resize((MAGNIFIER_SIZE, MAGNIFIER_SIZE), Image.NEAREST)
        self._magnifier_photo = ImageTk.PhotoImage(zoomed)
        self.magnifier.create_image(0, 0, anchor="nw", image=self._magnifier_photo)
        middle = MAGNIFIER_SIZE // 2
        self.magnifier.create_line(middle, 0, middle, MAGNIFIER_SIZE, fill=ACCENT)
        self.magnifier.create_line(0, middle, MAGNIFIER_SIZE, middle, fill=ACCENT)
        self.magnifier.create_text(middle, MAGNIFIER_SIZE - 10, text=f"{page_x}, {page_y}",
                                   fill="#ffffff", font=("Consolas", 9))

    # ------------------------------------------------------------------ passos
    def _current(self) -> Step:
        return self.steps[self.index]

    def go_to(self, index: int):
        if self.busy:
            return
        self.index = max(0, min(index, len(self.steps) - 1))
        self.corners.clear()
        self._show_step()

    def _show_step(self):
        step = self._current()
        if not step.is_rectangle:
            kind = "wizard.kind_click"
        elif step.acts:
            kind = "wizard.kind_button_area"
        else:
            kind = "wizard.kind_validation_area"
        self.lbl_progress.configure(
            text=tr("wizard.progress", current=self.index + 1, total=len(self.steps)) + "  ·  " + tr(kind)
            + ("  ·  " + tr("wizard.optional") if step.optional else ""))
        self.lbl_title.configure(text=tr(f"step.{step.name}.title"), text_color=ACCENT)
        self.lbl_instruction.configure(text=tr(f"step.{step.name}.text"))

        self.prompt = (tr("wizard.already_done") + " " if self.calibration.is_calibrated(step.name) else "") \
            + tr("wizard.prompt_area" if step.is_rectangle else "wizard.prompt_click")
        self._set_state(self.prompt)
        self._update_list()
        self._draw()

        # "Deixar a loja para o final" só existe nos passos da loja, e uma vez só.
        if step.name in STORE_STEPS and not self.deferred:
            self.btn_defer.pack(side="right", padx=4)
        else:
            self.btn_defer.pack_forget()

    def defer_store(self):
        """
        A loja não abriu: leva os dois passos dela para o fim da sequência.

        A loja abre sozinha depois do Go, mas não todas as vezes. Sem ela na
        tela não há o que marcar, e o resto da calibração não depende dela.
        """
        if self.busy:
            return
        self.deferred = True
        self.steps = [step for step in self.steps if step.name not in STORE_STEPS] \
            + [step for step in self.steps if step.name in STORE_STEPS]
        after_go = next(i for i, step in enumerate(self.steps) if step.name == "go_button") + 1
        self.go_to(after_go)
        self._set_state(tr("wizard.store_deferred") + "\n" + self.prompt, WARN_COLOR)

    def _update_list(self):
        for position, step in enumerate(self.steps):
            done = self.calibration.is_calibrated(step.name)
            mark = "✔" if done else ("·" if step.optional else "○")
            current = "▸ " if position == self.index else "   "
            self.rows[position].configure(
                text=f"{current}{mark}  {position + 1:>2}. {tr(f'step.{step.name}.title')}",
                text_color=OK_COLOR if done else MUTED,
                fg_color="#1f2733" if position == self.index else "transparent",
            )

    # ---------------------------------------------------------------- marcação
    def _ready(self) -> bool:
        if self.busy:
            self._set_state(tr("wizard.busy"), WARN_COLOR)
            return False
        if self.screenshot is None:
            self._set_state(tr("wizard.capture_first"), WARN_COLOR)
            return False
        if self.display_scale < 0.05:
            self._draw()
            return False
        return True

    def _on_press(self, event):
        self.press = (event.x, event.y) if self._ready() else None

    def _on_motion(self, event):
        if self.screenshot is None or self.display_scale < 0.05:
            return
        page = self._to_page(event.x, event.y)
        self._draw_magnifier(*page)

        # Elástico: do canto já marcado, ou de onde o botão foi pressionado.
        self.canvas.delete("band")
        if not self._current().is_rectangle or self.busy:
            return
        if self.corners:
            self._outline(self.corners[0], page, WARN_COLOR, tag="band")
        elif self.press and event.state & 0x0100:
            self._outline(self._to_page(*self.press), page, WARN_COLOR, tag="band")

    def _on_release(self, event):
        press, self.press = self.press, None
        if press is None or not self._ready():
            return
        step = self._current()
        page = self._to_page(event.x, event.y)

        if not step.is_rectangle:
            self.calibration.set_point(step.name, page[0], page[1], self._viewport())
            self.calibration.save()
            self._recorded(tr("wizard.point_saved", x=page[0], y=page[1]))
            return

        dragged = abs(event.x - press[0]) > DRAG_THRESHOLD or abs(event.y - press[1]) > DRAG_THRESHOLD
        if dragged:
            self.corners = [self._to_page(*press), page]
        else:
            self.corners.append(page)
            if len(self.corners) == 1:
                self._set_state(tr("wizard.first_corner", x=page[0], y=page[1]), OK_COLOR)
                self._draw()
                return

        corner_a, corner_b = self.corners[0], self.corners[1]
        self.corners.clear()
        try:
            low_contrast = self.calibration.set_region(step.name, corner_a, corner_b,
                                                       self.screenshot, self._viewport())
        except ValueError:
            self._set_state(tr("wizard.area_too_small"), ERROR_COLOR)
            self._draw()
            return
        self.calibration.save()

        if low_contrast is not None:
            # Uma referência sem detalhe é "achada" em qualquer fundo liso:
            # fica gravada, mas o assistente não avança sozinho por cima dela.
            self._set_state(tr("wizard.low_contrast", contrast=low_contrast), WARN_COLOR)
            self._update_list()
            self._draw()
            return

        region = self.calibration.regions[step.name]
        message = tr("wizard.area_saved", width=region["width"], height=region["height"])
        colour = OK_COLOR
        if step.name == "crypt_icon_area":
            note, colour = self._recognise_icon()
            message += "\n" + note
        self._recorded(message, colour)

    def _recognise_icon(self) -> Tuple[str, str]:
        """Confere se a área marcada mostra um ícone de cripta conhecido, e mede a escala dele."""
        raw = self.calibration.regions["crypt_icon_area"]
        region = expand((raw["left"], raw["top"], raw["width"], raw["height"]),
                        raw["width"] // 2, raw["height"] // 2)
        left, top = max(0, region[0]), max(0, region[1])
        crop = self.screenshot[top:region[1] + region[3], left:region[0] + region[2]]
        hit = recognise_icon(self.vision, cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
        if hit is None or not hit.passed:
            return (tr("wizard.icon_unknown", name=icon_name(hit.path) if hit else "-",
                       score=hit.score if hit else 0.0), WARN_COLOR)
        self.calibration.set_icon_scale(hit.scale, self._viewport())
        self.calibration.save()
        return tr("wizard.icon_known", name=icon_name(hit.path), score=hit.score, scale=hit.scale), OK_COLOR

    def _recorded(self, message: str, colour: str = OK_COLOR):
        self._set_state(message, colour)
        self._update_list()
        self._draw()
        if self.chain:
            self.busy = True        # nada de marcar outro ponto até o avanço acontecer
            self.after(500, lambda: self._advance(message, colour))

    # ------------------------------------------------------------------ avanço
    def _advance(self, note: str, colour: str):
        """
        Segue para o próximo passo - depois de fazer no jogo o que este marcou.

        Se o clique não muda nada na tela o assistente fica onde está: seguir
        adiante colocaria as marcas do próximo passo na tela errada.
        """
        self.busy = False
        step = self._current()
        if not step.acts:
            # Área de validação: nada a pressionar, a tela continua a mesma.
            self._go_next(note, colour)
            return

        self.busy = True
        self._set_state(tr("wizard.pressing", title=tr(f"step.{step.name}.title")))
        threading.Thread(target=self._run_press, args=(step, True), daemon=True).start()

    def _press(self, step: Step) -> Tuple[Tuple[int, int], float]:
        """Clica no que o passo marcou e mede o quanto a tela mudou. Roda fora da thread do Tk."""
        self.browser.ensure_attached()
        recorded = self.calibration.step_viewports.get(step.name)
        if recorded != self.browser.viewport():
            raise RuntimeError(tr("wizard.viewport_changed"))

        if step.is_rectangle:
            region = self.calibration.regions[step.name]
            target = (region["left"] + region["width"] // 2, region["top"] + region["height"] // 2)
        else:
            target = self.calibration.points[step.name]

        before = self.browser.capture()
        self.browser.click(target[0], target[1])
        time.sleep(self.click_delay)
        return target, changed_fraction(before, self.browser.capture())

    def _run_press(self, step: Step, advancing: bool):
        try:
            target, moved = self._press(step)
        except Exception as exc:  # noqa: BLE001
            self._post(tr("wizard.press_failed", error=exc), ERROR_COLOR, recapture=True)
            return
        if moved < MIN_SCREEN_CHANGE:
            if advancing and (step is self.steps[-1] or step.name == "use_button"):
                # Nada depois depende deste clique: não há tela seguinte para
                # errar. (Usar uma aceleração quase não muda a tela, e com a
                # loja adiada ele deixa de ser o último passo.)
                self._post(tr("wizard.press_done", x=target[0], y=target[1]), OK_COLOR,
                           recapture=True, advance=True)
                return
            self._post(tr("wizard.press_no_change", x=target[0], y=target[1], change=moved * 100),
                       ERROR_COLOR, recapture=True)
            return
        self._post(tr("wizard.press_ok", x=target[0], y=target[1], change=moved * 100), OK_COLOR,
                   recapture=True, advance=advancing)

    def _go_next(self, note: str = "", colour: str = MUTED):
        """Abre o próximo passo, mantendo visível o que acabou de ser informado."""
        if self.index >= len(self.steps) - 1:
            self._finished(note)
            return
        self.go_to(self.index + 1)
        if note:
            self._set_state(note + "\n" + self.prompt, colour)

    def _finished(self, note: str = ""):
        missing = self.calibration.missing_steps()
        if missing:
            titles = ", ".join(tr(f"step.{name}.title") for name in missing)
            self._set_state((note + "\n" if note else "") + tr("wizard.still_missing", steps=titles),
                            WARN_COLOR)
            return
        self.lbl_title.configure(text=tr("wizard.complete_title"), text_color=OK_COLOR)
        self._set_state((note + "\n" if note else "") + tr("wizard.complete"), OK_COLOR)

    def _post(self, message: str, colour: str, recapture: bool = False, advance: bool = False):
        """O resultado de uma thread, para a thread principal aplicar."""
        self.results.put({"message": message, "colour": colour, "recapture": recapture,
                          "advance": advance})

    def _drain_results(self):
        while True:
            try:
                result = self.results.get_nowait()
            except queue.Empty:
                break
            self.busy = False
            if result["recapture"]:
                self.refresh_capture()
            if result["advance"]:
                self._go_next(result["message"], result["colour"])
            else:
                self._set_state(result["message"], result["colour"])
        self.after(150, self._drain_results)

    # ------------------------------------------------------------------ testes
    def test_step(self):
        """Exercita o passo calibrado contra o jogo e mostra o resultado."""
        step = self._current()
        if not self._ready():
            return
        if not self.calibration.is_calibrated(step.name):
            self._set_state(tr("wizard.not_calibrated"), WARN_COLOR)
            return

        if step.acts:
            self.busy = True
            self._set_state(tr("wizard.testing"))
            threading.Thread(target=self._run_press, args=(step, False), daemon=True).start()
        elif step.keeps_reference:
            self.busy = True
            self._set_state(tr("wizard.testing"))
            threading.Thread(target=self._run_find, args=(step,), daemon=True).start()
        elif step.name == "crypt_icon_area" and \
                self.calibration.step_viewports.get(step.name) == self._viewport():
            self._set_state(*self._recognise_icon())
        else:
            self._set_state(tr("wizard.nothing_to_test"))

    def _run_find(self, step: Step):
        try:
            self.browser.ensure_attached()
            self.calibration.use_viewport(*self.browser.viewport())
            hit = self.vision.find(self.calibration.ref_path(step.name), None,
                                   base_scale=self.calibration.image_scale(step.name))
        except Exception as exc:  # noqa: BLE001
            self._post(tr("wizard.press_failed", error=exc), ERROR_COLOR)
            return
        if hit and hit.passed:
            self._post(tr("wizard.image_found", x=hit.center[0], y=hit.center[1], score=hit.score),
                       OK_COLOR, recapture=True)
        else:
            self._post(tr("wizard.image_not_found", score=hit.score if hit else 0.0), ERROR_COLOR,
                       recapture=True)

    def redo(self):
        if self.busy:
            return
        self.calibration.forget(self._current().name)
        self.calibration.save()
        self.corners.clear()
        self._show_step()
        self._set_state(tr("wizard.step_cleared"), WARN_COLOR)

    def skip(self):
        if not self.busy and self.index < len(self.steps) - 1:
            self.go_to(self.index + 1)

    def close(self):
        if self.on_close:
            self.on_close()
        self.destroy()
