"""
Janela principal.

Três abas: a execução (abrir o jogo, calibrar, iniciar e acompanhar o log), a
escolha das criptas e os parâmetros. A execução roda em uma thread da própria
janela e o log dela aparece aqui - não há mais processo filho nem janela de
status, porque pelo CDP o jogo não precisa estar na frente.
"""

import logging
import os
import queue
import threading
import webbrowser
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk
from PIL import Image

from ..browser import Browser, BrowserError, BrowserNotOpen, GameTabNotFound
from ..calibration import Calibration
from ..cancel import Cancelled, cancellation, escape_watcher
from ..collector import Collector, CollectorError, all_icon_names, icon_path
from ..i18n import set_language, tr
from ..logger import QueueHandler, logger
from ..paths import BROWSER_PROFILE_DIR, ICON_FILE, LOG_DIR
from ..settings import ANY_MODE, CRYPT_TYPES, FIELDS, LANGUAGES, Settings
from ..version import __version__
from ..vision import Vision
from . import (ACCENT, BUTTON_BG, CARD_BG, DARK_BG, ERROR_COLOR, HOVER_BG, MUTED, OK_COLOR, PANEL_BG,
               TEXT, WARN_COLOR, place)
from .calibration_wizard import CalibrationWizard

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ICON_SIZE = 72
ICON_COLUMNS = 8
MAX_LOG_LINES = 2000
LOG_COLOURS = {logging.WARNING: WARN_COLOR, logging.ERROR: ERROR_COLOR}


class App(ctk.CTk):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        set_language(settings.language)
        self.calibration = Calibration()
        self.browser = self._new_browser()
        self.wizard: Optional[CalibrationWizard] = None
        self.worker: Optional[threading.Thread] = None
        self.log_queue: queue.Queue = queue.Queue()
        # O Tk não é thread-safe: as threads de trabalho deixam aqui o que a
        # thread principal deve fazer, e ela o faz no seu próprio ritmo.
        self.ui_queue: queue.Queue = queue.Queue()
        self.log_lines: List[tuple] = []
        self.icons = all_icon_names()
        self.thumbnails: Dict[str, ctk.CTkImage] = {}

        run = self.settings.section("run")
        self.mode: str = run.get("mode") if run.get("mode") in CRYPT_TYPES + (ANY_MODE,) else "epic"
        self.selected = {name for name in run.get("selected", []) if name.startswith(self.mode + "/")}

        place(self, 1100, 760)
        self.minsize(940, 600)
        self._apply_icon()
        # customtkinter reapplies its default icon shortly after startup; override it afterwards.
        self.after(250, self._apply_icon)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        logger.addHandler(QueueHandler(self.log_queue))
        self.after(150, self._drain_log)

    def _apply_icon(self) -> None:
        try:
            self.iconbitmap(ICON_FILE)
        except Exception:
            pass

    def _new_browser(self) -> Browser:
        return Browser(self.settings.section("browser"), BROWSER_PROFILE_DIR)

    # ---------------------------------------------------------------------- UI
    def _build(self):
        self.title(f"{tr('app.title')} v{__version__}")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))
        try:
            logo = Image.open(ICON_FILE)
            logo.load()
            self._logo_image = ctk.CTkImage(light_image=logo, dark_image=logo, size=(32, 32))
            ctk.CTkLabel(header, text="", image=self._logo_image).pack(side="left", padx=(0, 8))
        except Exception:
            pass
        ctk.CTkLabel(header, text=tr("app.title"), font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(header, text=f"v{__version__}", font=ctk.CTkFont(size=12),
                     text_color=MUTED).pack(side="left", padx=(8, 0), pady=(6, 0))

        self.language_menu = ctk.CTkOptionMenu(header, values=list(LANGUAGES.values()), width=120,
                                               fg_color=BUTTON_BG, button_color=BUTTON_BG,
                                               button_hover_color=HOVER_BG, command=self.change_language)
        self.language_menu.set(LANGUAGES[self.settings.language])
        self.language_menu.pack(side="right")
        self.lbl_status = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=12), text_color=MUTED)
        self.lbl_status.pack(side="right", padx=14)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=18, pady=(0, 8))
        ctk.CTkLabel(footer, text=tr("app.developed_by"), font=ctk.CTkFont(size=11),
                     text_color=MUTED).pack(side="left")
        author = ctk.CTkLabel(footer, text="Crash BR", font=ctk.CTkFont(size=11), text_color=ACCENT,
                              cursor="hand2")
        author.pack(side="left", padx=(4, 0))
        author.bind("<Button-1>", lambda _event: webbrowser.open("mailto:crashbrtb@gmail.com"))

        self.tab_names = {key: tr(f"tab.{key}") for key in ("run", "crypts", "parameters")}
        self.tabs = ctk.CTkTabview(self, fg_color=PANEL_BG)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(4, 6))
        for name in self.tab_names.values():
            self.tabs.add(name)

        self._build_run_tab(self.tabs.tab(self.tab_names["run"]))
        self._build_crypts_tab(self.tabs.tab(self.tab_names["crypts"]))
        self._build_parameters_tab(self.tabs.tab(self.tab_names["parameters"]))
        self._refresh_status()

    # -- aba de execução
    def _build_run_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(10, 6))

        ctk.CTkButton(top, text=tr("run.btn_open_game"), width=210, height=38,
                      command=self.open_game).pack(side="left", padx=4)
        ctk.CTkButton(top, text=tr("run.btn_calibrate"), width=140, height=38,
                      command=self.open_calibration).pack(side="left", padx=4)
        self.btn_run = ctk.CTkButton(top, text=tr("run.btn_start"), width=170, height=38,
                                     fg_color="#238636", hover_color="#2ea043", command=self.start_run)
        self.btn_run.pack(side="right", padx=4)
        self.btn_stop = ctk.CTkButton(top, text=tr("run.btn_stop"), width=100, height=38, state="disabled",
                                      fg_color=BUTTON_BG, hover_color=ERROR_COLOR, command=self.stop_run)
        self.btn_stop.pack(side="right", padx=4)

        info = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=8)
        info.pack(fill="x", padx=8, pady=(4, 8))
        self.lbl_info = ctk.CTkLabel(info, text="", justify="left", anchor="w",
                                     font=ctk.CTkFont(size=12), text_color=TEXT)
        self.lbl_info.pack(fill="x", padx=14, pady=12)

        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=8, pady=(0, 10))
        ctk.CTkLabel(bottom, text=tr("run.esc_hint"), font=ctk.CTkFont(size=11),
                     text_color=MUTED).pack(side="left")
        ctk.CTkButton(bottom, text=tr("run.btn_logs"), width=150, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=self._open_logs).pack(side="right")

        ctk.CTkLabel(parent, text=tr("run.log_title"), font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=12, pady=(4, 2))
        self.log_box = ctk.CTkTextbox(parent, fg_color=DARK_BG, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        for level, colour in LOG_COLOURS.items():
            self.log_box.tag_config(str(level), foreground=colour)
        for level, line in self.log_lines:
            self._append_log(level, line)

    # -- aba de criptas
    def _build_crypts_tab(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(10, 4))

        self.mode_labels = {tr(f"mode.{mode}"): mode for mode in CRYPT_TYPES + (ANY_MODE,)}
        self.mode_selector = ctk.CTkSegmentedButton(toolbar, values=list(self.mode_labels), height=34,
                                                    command=lambda label: self.set_mode(self.mode_labels[label]))
        self.mode_selector.set(tr(f"mode.{self.mode}"))
        self.mode_selector.pack(side="left", padx=4)

        self.btn_select_all = ctk.CTkButton(toolbar, text=tr("crypts.select_all"), width=140, height=34,
                                            fg_color=BUTTON_BG, hover_color=HOVER_BG, command=self.select_all)
        self.btn_select_all.pack(side="left", padx=(12, 4))
        self.btn_clear = ctk.CTkButton(toolbar, text=tr("crypts.clear"), width=100, height=34,
                                       fg_color=BUTTON_BG, hover_color=HOVER_BG, command=self.clear_selection)
        self.btn_clear.pack(side="left", padx=4)

        self.quantity = ctk.CTkEntry(toolbar, width=70, height=34, justify="center")
        self.quantity.insert(0, str(self.settings.get("run", "crypt_count")))
        self.quantity.pack(side="right", padx=4)
        self.quantity.bind("<KeyRelease>", lambda _event: self._save_run_settings())
        ctk.CTkLabel(toolbar, text=tr("crypts.quantity")).pack(side="right", padx=(12, 4))

        ctk.CTkLabel(parent, text=tr("crypts.hint"), font=ctk.CTkFont(size=11), text_color=MUTED,
                     justify="left", wraplength=980).pack(anchor="w", padx=14, pady=(2, 6))

        self.grid_box = ctk.CTkScrollableFrame(parent, fg_color=DARK_BG)
        self.grid_box.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self._fill_grid()

    def _thumbnail(self, name: str) -> Optional[ctk.CTkImage]:
        if name not in self.thumbnails:
            try:
                image = Image.open(icon_path(name)).convert("RGBA")
            except OSError:
                return None
            self.thumbnails[name] = ctk.CTkImage(light_image=image, dark_image=image,
                                                 size=(ICON_SIZE, ICON_SIZE))
        return self.thumbnails[name]

    def _fill_grid(self):
        for widget in self.grid_box.winfo_children():
            widget.destroy()
        self.tiles: Dict[str, ctk.CTkButton] = {}

        state = "disabled" if self.mode == ANY_MODE else "normal"
        self.btn_select_all.configure(state=state)
        self.btn_clear.configure(state=state)

        if self.mode == ANY_MODE:
            ctk.CTkLabel(self.grid_box, text=tr("crypts.any_active"), font=ctk.CTkFont(size=14),
                         text_color=TEXT, wraplength=700).pack(pady=60)
            return
        names = self.icons.get(self.mode, [])
        if not names:
            ctk.CTkLabel(self.grid_box, text=tr("crypts.no_images", folder=f"images/cript/{self.mode}"),
                         text_color=WARN_COLOR).pack(pady=60)
            return

        for position, name in enumerate(names):
            tile = ctk.CTkButton(self.grid_box, text="", image=self._thumbnail(name),
                                 width=ICON_SIZE + 20, height=ICON_SIZE + 20, corner_radius=8,
                                 fg_color=CARD_BG, hover_color=HOVER_BG, border_width=3,
                                 command=lambda n=name: self.toggle(n))
            tile.grid(row=position // ICON_COLUMNS, column=position % ICON_COLUMNS, padx=6, pady=6)
            self.tiles[name] = tile
            self._paint_tile(name)

    def _paint_tile(self, name: str):
        chosen = name in self.selected
        self.tiles[name].configure(border_color=ACCENT if chosen else CARD_BG,
                                   fg_color="#1f2733" if chosen else CARD_BG)

    # -- aba de parâmetros
    def _build_parameters_tab(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(10, 4))
        ctk.CTkLabel(toolbar, text=tr("params.intro"), font=ctk.CTkFont(size=12),
                     text_color=MUTED).pack(side="left")
        ctk.CTkButton(toolbar, text=tr("params.save"), width=180,
                      command=self.save_parameters).pack(side="right", padx=4)

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        block = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=8)
        block.pack(fill="x", pady=6)

        self.param_entries: Dict[tuple, ctk.CTkEntry] = {}
        for field in FIELDS:
            row = ctk.CTkFrame(block, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=6)
            key = f"param.{field.section}.{field.key}"
            ctk.CTkLabel(row, text=tr(key), width=230, anchor="w",
                         font=ctk.CTkFont(size=12)).pack(side="left")
            entry = ctk.CTkEntry(row, width=300 if field.type == "str" else 110)
            entry.insert(0, str(self.settings.get(field.section, field.key)))
            entry.pack(side="left")
            ctk.CTkLabel(row, text=tr(key + ".help"), font=ctk.CTkFont(size=11), text_color=MUTED,
                         wraplength=440, justify="left", anchor="w").pack(side="left", padx=12,
                                                                          fill="x", expand=True)
            self.param_entries[(field.section, field.key)] = entry

    # ----------------------------------------------------------------- criptas
    def set_mode(self, mode: str):
        if mode == self.mode:
            return
        # A lista do jogo mostra um tipo por vez, então a seleção também.
        self.mode = mode
        self.selected.clear()
        self._fill_grid()
        self._save_run_settings()

    def toggle(self, name: str):
        self.selected.symmetric_difference_update({name})
        self._paint_tile(name)
        self._save_run_settings()

    def select_all(self):
        self.selected = set(self.icons.get(self.mode, []))
        for name in self.tiles:
            self._paint_tile(name)
        self._save_run_settings()

    def clear_selection(self):
        self.selected.clear()
        for name in self.tiles:
            self._paint_tile(name)
        self._save_run_settings()

    def _save_run_settings(self):
        self.settings.set("run", "mode", self.mode)
        self.settings.set("run", "selected", [n for n in self.icons.get(self.mode, []) if n in self.selected])
        text = self.quantity.get().strip()
        if text.isdigit() and int(text) > 0:
            self.settings.set("run", "crypt_count", int(text))
        self.settings.save()
        self._refresh_status()

    # ------------------------------------------------------------------- ações
    def change_language(self, label: str):
        code = next(code for code, name in LANGUAGES.items() if name == label)
        if code == self.settings.language:
            return
        if self._busy() or (self.wizard is not None and self.wizard.winfo_exists()):
            self.language_menu.set(LANGUAGES[self.settings.language])
            messagebox.showwarning(tr("app.title"), tr("app.busy"))
            return
        self.settings.language = code
        self.settings.save()
        set_language(code)
        current = next((key for key, name in self.tab_names.items() if name == self.tabs.get()), "run")
        for widget in self.winfo_children():
            widget.destroy()
        self._build()
        self.tabs.set(self.tab_names[current])

    def save_parameters(self):
        for field in FIELDS:
            entry = self.param_entries[(field.section, field.key)]
            try:
                self.settings.set_field(field, entry.get())
            except ValueError:
                messagebox.showerror(tr("app.title"),
                                     tr("params.invalid", name=tr(f"param.{field.section}.{field.key}")))
                return
        self.settings.save()
        if not self._busy():
            self.browser.disconnect()
            self.browser = self._new_browser()
        self._refresh_status()
        messagebox.showinfo(tr("app.title"), tr("params.saved"))

    def open_game(self):
        """Abre o Chrome com CDP - ou reaproveita o que já está aberto - e conecta à aba do jogo."""
        def work():
            try:
                launched = self.browser.open_game()
            except BrowserError as exc:
                logger.error(tr("run.open_failed", error=exc))
                return
            logger.info(tr("run.opened_now" if launched else "run.already_open"))

        self._run_in_background(work)

    def open_calibration(self):
        """Garante o navegador com o jogo e parte para a calibração."""
        if self.wizard is not None and self.wizard.winfo_exists():
            self.wizard.lift()
            return

        def work():
            try:
                launched = self.browser.open_game()
            except BrowserError as exc:
                logger.error(tr("run.open_failed", error=exc))
                return
            logger.info(tr("run.opened_now" if launched else "run.already_open"))
            self.ui_queue.put(lambda: self._show_wizard(launched))

        self._run_in_background(work)

    def _show_wizard(self, just_launched: bool):
        self.wizard = CalibrationWizard(
            self, self.browser, Vision(self.browser, self.settings.section("vision")), self.calibration,
            click_delay=self.settings.get("timing", "click_delay"), just_launched=just_launched,
            on_close=self._refresh_status)

    def start_run(self):
        if self.wizard is not None and self.wizard.winfo_exists():
            messagebox.showwarning(tr("app.title"), tr("run.close_wizard"))
            return
        self._save_run_settings()
        collector = Collector(self.browser, Vision(self.browser, self.settings.section("vision")),
                              self.calibration, self.settings)
        problems = collector.preflight()
        if problems:
            messagebox.showwarning(tr("app.title"), "\n\n".join(problems))
            return

        def work():
            try:
                summary = collector.run()
                logger.info(tr("run.finished", **summary))
            except Cancelled:
                logger.warning(tr("run.cancelled"))
            except (BrowserNotOpen, GameTabNotFound):
                logger.error(tr("run.game_not_open"))
            except (BrowserError, CollectorError) as exc:
                logger.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.exception(tr("run.unexpected", error=exc))

        cancellation.reset()
        escape_watcher.start()
        self._run_in_background(work, running=True)

    def stop_run(self):
        cancellation.cancel()
        self.btn_stop.configure(state="disabled")
        logger.warning(tr("run.stopping"))

    # ---------------------------------------------------------------- auxiliares
    def _busy(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def _run_in_background(self, target: Callable[[], None], running: bool = False):
        if self._busy():
            messagebox.showwarning(tr("app.title"), tr("app.busy"))
            return
        self.btn_run.configure(state="disabled", text=tr("run.btn_running") if running else tr("run.btn_start"))
        if running:
            self.btn_stop.configure(state="normal")
        self.tabs.set(self.tab_names["run"])

        def wrapper():
            try:
                target()
            finally:
                escape_watcher.stop()
                self.ui_queue.put(self._work_done)

        self.worker = threading.Thread(target=wrapper, daemon=True)
        self.worker.start()

    def _work_done(self):
        self.btn_run.configure(state="normal", text=tr("run.btn_start"))
        self.btn_stop.configure(state="disabled")
        self._refresh_status()

    def _append_log(self, level: int, line: str):
        tag = str(level) if level in LOG_COLOURS else None
        self.log_box.insert("end", line + "\n", tag)
        self.log_box.see("end")

    def _drain_log(self):
        while True:
            try:
                level, line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            level = logging.ERROR if level >= logging.ERROR else level
            self.log_lines.append((level, line))
            del self.log_lines[:-MAX_LOG_LINES]
            self._append_log(level, line)
        while True:
            try:
                self.ui_queue.get_nowait()()
            except queue.Empty:
                break
        self.after(150, self._drain_log)

    def _open_logs(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        os.startfile(LOG_DIR)

    def _refresh_status(self):
        missing = self.calibration.missing_steps()
        if missing:
            calibration_text = tr("status.calibration_missing", count=len(missing))
            colour = ERROR_COLOR
        else:
            calibration_text = tr("status.calibration_ok", date=self.calibration.created_at,
                                  width=self.calibration.viewport[0], height=self.calibration.viewport[1])
            colour = OK_COLOR
        self.lbl_status.configure(text=calibration_text, text_color=colour)

        if self.mode == ANY_MODE:
            selection = tr("crypts.any_active")
        else:
            selection = tr("status.selection", type=tr(f"mode.{self.mode}"), count=len(self.selected))
        self.lbl_info.configure(text="\n".join((
            tr("status.crypts", selection=selection),
            tr("status.quantity", count=self.settings.get("run", "crypt_count"),
               speedups=self.settings.get("run", "speedups_per_march")),
            tr("status.calibration", text=calibration_text),
            tr("status.browser", port=self.settings.get("browser", "cdp_port"),
               state=tr("status.connected" if self.browser.connected else "status.not_connected")),
        )))

    def _on_close(self):
        cancellation.cancel()
        self.browser.disconnect()
        self.destroy()


def launch():
    App(Settings()).mainloop()
