"""
Janela principal.

Abas:
  Execução            abrir o jogo, conectar, iniciar/parar, situação de cada capitão e o log
  Capitães e criptas  as 3 faixas (capitão, família, nível, imagens das criptas, quantidade,
                      armaduras e artefato) e as seleções salvas
  Parâmetros          busca, aceleração, alcatrão, vigia do jogo e navegador

O trabalho de rede roda em threads; o Tk só é tocado na thread principal (ui_queue).
"""

import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser
from tkinter import messagebox, simpledialog
from typing import Dict, List, Optional

import customtkinter as ctk
from PIL import Image

from .. import catalog as catalog_mod
from .. import evolution as evo
from .. import gear as gear_mod
from ..browser import Browser, BrowserError
from ..cancel import CancelToken, Cancelled, cancellation, escape_watcher
from ..collector import Collector, CollectorError
from ..game import Game
from ..gamelink import GameError, GameLink
from ..i18n import set_language, tr
from ..logger import QueueHandler, logger
from ..paths import BROWSER_PROFILE_DIR, ICON_FILE, LOG_DIR
from ..settings import CHOICES, FIELDS, LANGUAGES, MAX_LANES, Settings
from ..version import __version__
from . import (ACCENT, BUTTON_BG, CARD_BG, DARK_BG, ERROR_COLOR, HOVER_BG, MUTED, OK_COLOR, PANEL_BG,
               TEXT, WARN_COLOR, place)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

TILE = 64
TILE_COLUMNS = 9
MAX_LOG_LINES = 2000
LOG_COLOURS = {logging.WARNING: WARN_COLOR, logging.ERROR: ERROR_COLOR}
SELECTED_BORDER = ACCENT


class App(ctk.CTk):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        set_language(settings.language)
        self.worker: Optional[threading.Thread] = None
        self.log_queue: queue.Queue = queue.Queue()
        self.ui_queue: queue.Queue = queue.Queue()
        self.cat: Optional[dict] = None
        self.city_state: Optional[dict] = None
        self.images = None
        self.thumbs: Dict[str, ctk.CTkImage] = {}
        self.thumb_pending: set = set()
        self.image_lock = threading.Lock()
        self.found_counts: Dict[int, tuple] = {}
        self.lane_widgets: List[dict] = []
        self.status_labels: List[ctk.CTkLabel] = []

        place(self, 1180, 820)
        self.minsize(980, 640)
        self._apply_icon()
        self.after(250, self._apply_icon)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.title(f"{tr('app.title')} {__version__}")
        self._build()
        logger.addHandler(QueueHandler(self.log_queue))
        self.after(150, self._pump)
        self._bg(self._load_catalog)

    # ------------------------------------------------------------ infraestrutura
    def _apply_icon(self):
        try:
            self.iconbitmap(ICON_FILE)
        except Exception:
            pass

    def ui(self, fn, *a):
        self.ui_queue.put((fn, a))

    def _pump(self):
        try:
            while True:
                fn, a = self.ui_queue.get_nowait()
                try:
                    fn(*a)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"ui: {exc}")
        except queue.Empty:
            pass
        lines = []
        try:
            while True:
                lines.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        if lines:
            self.log_box.configure(state="normal")
            for level, text in lines:
                self.log_box.insert("end", text + "\n", LOG_COLOURS.get(level, "info"))
            excess = int(self.log_box.index("end-1c").split(".")[0]) - MAX_LOG_LINES
            if excess > 0:
                self.log_box.delete("1.0", f"{excess}.0")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(150, self._pump)

    def _bg(self, fn, *a):
        threading.Thread(target=self._safe, args=(fn,) + a, daemon=True).start()

    def _safe(self, fn, *a):
        try:
            fn(*a)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"{exc}")

    def _browser(self) -> Browser:
        return Browser(self.settings.section("browser"), BROWSER_PROFILE_DIR)

    @property
    def running(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    # ------------------------------------------------------------------ layout
    def _build(self):
        self.configure(fg_color=PANEL_BG)
        head = ctk.CTkFrame(self, fg_color=PANEL_BG)
        head.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(head, text=tr("app.title"), font=("Segoe UI", 20, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(head, text=f"v{__version__} · {tr('app.network')}", text_color=MUTED).pack(side="left", padx=10)
        self.lang = ctk.CTkOptionMenu(head, values=list(LANGUAGES.values()), width=120, command=self._set_language)
        self.lang.set(LANGUAGES[self.settings.language])
        self.lang.pack(side="right")

        self.tabs = ctk.CTkTabview(self, fg_color=CARD_BG, segmented_button_selected_color=ACCENT)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=10)
        self._build_run(self.tabs.add(tr("tab.run")))
        self._build_lanes(self.tabs.add(tr("tab.lanes")))
        self._build_combine(self.tabs.add(tr("tab.combine")))
        self._build_params(self.tabs.add(tr("tab.parameters")))

    # ---------------------------------------------------------------- execução
    def _build_run(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 6))
        self.open_btn = ctk.CTkButton(bar, text=tr("run.open_game"), command=self._open_game, width=200)
        self.open_btn.pack(side="left", padx=(0, 6))
        self.connect_btn = ctk.CTkButton(bar, text=tr("run.connect"), command=self._connect, width=160)
        self.connect_btn.pack(side="left", padx=6)
        self.start_btn = ctk.CTkButton(bar, text=tr("run.start"), command=self._start, width=140,
                                       fg_color=OK_COLOR, hover_color="#2ea043")
        self.start_btn.pack(side="left", padx=6)
        self.stop_btn = ctk.CTkButton(bar, text=tr("run.stop"), command=self._stop, width=120,
                                      fg_color=ERROR_COLOR, hover_color="#da3633", state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        ctk.CTkButton(bar, text=tr("run.logs"), width=110, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=lambda: webbrowser.open(LOG_DIR)).pack(side="right")

        self.conn_label = ctk.CTkLabel(tab, text=tr("run.not_connected"), text_color=MUTED, anchor="w", justify="left")
        self.conn_label.pack(fill="x", pady=(0, 6))
        lanes = ctk.CTkFrame(tab, fg_color="transparent")
        lanes.pack(fill="x")
        for i in range(MAX_LANES):
            card = ctk.CTkFrame(lanes, fg_color=DARK_BG, corner_radius=8)
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))
            lbl = ctk.CTkLabel(card, text=f"{i + 1} · —", text_color=TEXT, anchor="w", justify="left",
                               wraplength=330)
            lbl.pack(fill="both", padx=10, pady=8)
            self.status_labels.append(lbl)
        ctk.CTkLabel(tab, text=tr("run.hint"), text_color=MUTED, anchor="w", justify="left",
                     wraplength=1100).pack(fill="x", pady=(8, 4))
        self.log_box = ctk.CTkTextbox(tab, fg_color=DARK_BG, text_color=TEXT, font=("Consolas", 12), wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_config("info", foreground=TEXT)
        self.log_box.tag_config(WARN_COLOR, foreground=WARN_COLOR)
        self.log_box.tag_config(ERROR_COLOR, foreground=ERROR_COLOR)
        self.log_box.configure(state="disabled")
        self._refresh_status_cards()

    # ------------------------------------------------------------ capitães/criptas
    def _build_lanes(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(bar, text=tr("presets.label"), text_color=TEXT).pack(side="left")
        self.preset_box = ctk.CTkComboBox(bar, values=self._preset_names(), width=220)
        self.preset_box.set("")
        self.preset_box.pack(side="left", padx=6)
        for text, cmd in ((tr("presets.load"), self._load_preset), (tr("presets.save"), self._save_preset),
                          (tr("presets.delete"), self._delete_preset)):
            ctk.CTkButton(bar, text=text, width=90, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                          command=cmd).pack(side="left", padx=3)
        ctk.CTkButton(bar, text=tr("lanes.search"), width=170, command=self._search_map).pack(side="right")
        ctk.CTkLabel(tab, text=tr("lanes.hint"), text_color=MUTED, anchor="w", justify="left",
                     wraplength=1100).pack(fill="x")
        self.lane_area = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.lane_area.pack(fill="both", expand=True, pady=(6, 0))
        for i in range(MAX_LANES):
            self.lane_widgets.append(self._build_lane(self.lane_area, i))
        self._refresh_lanes()

    def _build_lane(self, parent, i: int) -> dict:
        card = ctk.CTkFrame(parent, fg_color=DARK_BG, corner_radius=8)
        card.pack(fill="x", pady=(0, 10))
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 4))
        w = {"card": card, "index": i}
        w["enabled"] = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text=f"{tr('lanes.captain')} {i + 1}", variable=w["enabled"], width=110,
                        command=lambda: self._lane_changed(i)).pack(side="left")
        w["captain"] = ctk.CTkOptionMenu(top, values=["—"], width=170, command=lambda _v: self._lane_changed(i))
        w["captain"].pack(side="left", padx=6)
        ctk.CTkLabel(top, text=tr("lanes.kind"), text_color=MUTED).pack(side="left", padx=(10, 4))
        w["kind"] = ctk.CTkOptionMenu(top, values=[tr(f"kind.{k}") for k in catalog_mod.KIND_ORDER], width=170,
                                      command=lambda _v: self._kind_changed(i))
        w["kind"].pack(side="left")
        ctk.CTkLabel(top, text=tr("lanes.level"), text_color=MUTED).pack(side="left", padx=(10, 4))
        w["level"] = ctk.CTkOptionMenu(top, values=["—"], width=80, command=lambda _v: self._level_changed(i))
        w["level"].pack(side="left")
        ctk.CTkLabel(top, text=tr("lanes.quantity"), text_color=MUTED).pack(side="left", padx=(10, 4))
        w["quantity"] = ctk.CTkEntry(top, width=60)
        w["quantity"].pack(side="left")
        w["quantity"].bind("<FocusOut>", lambda _e: self._lane_changed(i))
        ctk.CTkButton(top, text=tr("lanes.gear"), width=130, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=lambda: self._open_gear(i)).pack(side="right")
        ctk.CTkButton(top, text=tr("lanes.none"), width=70, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=lambda: self._select_all(i, False)).pack(side="right", padx=3)
        ctk.CTkButton(top, text=tr("lanes.all"), width=70, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=lambda: self._select_all(i, True)).pack(side="right", padx=3)
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=12)
        w["gear_label"] = ctk.CTkLabel(row2, text="", text_color=MUTED, anchor="w", justify="left", wraplength=760)
        w["gear_label"].pack(side="left", fill="x", expand=True)
        w["fallback"] = ctk.CTkOptionMenu(row2, values=self._fallback_values(i), width=190,
                                          command=lambda _v: self._fallback_changed(i))
        w["fallback"].pack(side="right")
        ctk.CTkLabel(row2, text=tr("lanes.fallback"), text_color=MUTED).pack(side="right", padx=(10, 4))
        w["tiles"] = ctk.CTkFrame(card, fg_color="transparent")
        w["tiles"].pack(fill="x", padx=8, pady=(2, 8))
        w["tile_widgets"] = {}
        return w

    def _lane_cfg(self, i: int) -> dict:
        return self.settings.data["lanes"][i]

    def _captain_choices(self) -> Dict[str, int]:
        if not self.cat:
            return {}
        if self.city_state:
            ids = [c for c in self.city_state["captains"] if c != catalog_mod.HERO]
        else:
            ids = [int(ln["captain"]) for ln in self.settings.data["lanes"] if ln.get("captain")]
        names = {}
        for cid in sorted(ids, key=lambda c: self.cat["captains"].get(c, {}).get("name", str(c))):
            name = self.cat["captains"].get(cid, {}).get("name", f"#{cid}")
            lvl = (self.city_state or {}).get("captains", {}).get(cid, {}).get("level")
            names[f"{name} ({lvl})" if lvl else name] = cid
        return names

    def _refresh_lanes(self):
        choices = self._captain_choices()
        self.captain_choices = choices
        by_id = {v: k for k, v in choices.items()}
        kinds = {tr(f"kind.{k}"): k for k in catalog_mod.KIND_ORDER}
        self.kind_choices = kinds
        for w in self.lane_widgets:
            lc = self._lane_cfg(w["index"])
            w["enabled"].set(bool(lc.get("enabled")))
            w["captain"].configure(values=list(choices) or ["—"])
            w["captain"].set(by_id.get(lc.get("captain"), "—"))
            w["kind"].set(tr(f"kind.{lc.get('kind') or 'epic'}"))
            self._fill_levels(w)
            w["quantity"].delete(0, "end")
            w["quantity"].insert(0, str(lc.get("quantity") or 0))
            self._draw_tiles(w)
            self._draw_gear_label(w)
            fb = lc.get("fallback")
            w["fallback"].set(tr("lanes.fallback.help", n=fb + 1) if isinstance(fb, int) else tr("lanes.fallback.stop"))

    def _fallback_values(self, i: int) -> List[str]:
        return [tr("lanes.fallback.stop")] + [tr("lanes.fallback.help", n=j + 1) for j in range(MAX_LANES) if j != i]

    def _fallback_changed(self, i: int):
        value = self.lane_widgets[i]["fallback"].get()
        choice = {tr("lanes.fallback.help", n=j + 1): j for j in range(MAX_LANES) if j != i}
        self._lane_cfg(i)["fallback"] = choice.get(value)
        self._save_quiet()

    def _fill_levels(self, w):
        lc = self._lane_cfg(w["index"])
        lv = catalog_mod.levels(self.cat, lc.get("kind") or "epic") if self.cat else []
        if lv and lc.get("level") not in lv:
            lc["level"] = lv[-1]
            lc["groups"] = []
        w["level"].configure(values=[str(x) for x in lv] or ["—"])
        w["level"].set(str(lc.get("level")) if lv else "—")

    def _kind_changed(self, i):
        w = self.lane_widgets[i]
        lc = self._lane_cfg(i)
        lc["kind"] = self.kind_choices.get(w["kind"].get(), "epic")
        lc["groups"] = []
        self._fill_levels(w)
        self._draw_tiles(w)
        self._save_quiet()

    def _level_changed(self, i):
        w = self.lane_widgets[i]
        lc = self._lane_cfg(i)
        try:
            new = int(w["level"].get())
        except ValueError:
            return
        if new != lc.get("level"):
            lc["level"], lc["groups"] = new, []      # um nível por capitão: a seleção recomeça
        self._draw_tiles(w)
        self._save_quiet()

    def _lane_changed(self, i):
        w = self.lane_widgets[i]
        lc = self._lane_cfg(i)
        lc["enabled"] = bool(w["enabled"].get())
        cid = self.captain_choices.get(w["captain"].get()) if hasattr(self, "captain_choices") else None
        if cid and cid != lc.get("captain"):
            for j, other in enumerate(self.settings.data["lanes"]):
                if j != i and other.get("captain") == cid:
                    messagebox.showwarning(tr("app.title"), tr("lanes.captain_taken", n=j + 1))
                    w["captain"].set({v: k for k, v in self.captain_choices.items()}.get(lc.get("captain"), "—"))
                    return
            lc["captain"] = cid
            lc["gear"], lc["artifact"] = [None, None, None], None
            if self.city_state:
                lc["gear"] = gear_mod.from_game(self.city_state, cid)
            self._draw_gear_label(w)
        try:
            lc["quantity"] = max(0, int(w["quantity"].get() or 0))
        except ValueError:
            w["quantity"].delete(0, "end")
            w["quantity"].insert(0, str(lc.get("quantity") or 0))
        self._save_quiet()
        self._refresh_status_cards()

    def _draw_tiles(self, w):
        for child in w["tiles"].winfo_children():
            child.destroy()
        w["tile_widgets"] = {}
        if not self.cat:
            ctk.CTkLabel(w["tiles"], text=tr("lanes.loading"), text_color=MUTED).grid(row=0, column=0)
            return
        lc = self._lane_cfg(w["index"])
        groups = catalog_mod.groups(self.cat, lc.get("kind") or "epic", int(lc.get("level") or 0))
        chosen = set(lc.get("groups") or [])
        for n, (icon, types) in enumerate(groups.items()):
            cell = ctk.CTkFrame(w["tiles"], fg_color=CARD_BG, corner_radius=6, border_width=2,
                                border_color=SELECTED_BORDER if icon in chosen else CARD_BG)
            cell.grid(row=n // TILE_COLUMNS, column=n % TILE_COLUMNS, padx=3, pady=3)
            btn = ctk.CTkButton(cell, text="" if icon in self.thumbs else icon[:10], image=self.thumbs.get(icon),
                                width=TILE + 8, height=TILE + 8, fg_color="transparent", hover_color=HOVER_BG,
                                command=lambda g=icon, i=w["index"]: self._toggle(i, g))
            btn.pack(padx=2, pady=(2, 0))
            info = self._found_text(types)
            lbl = ctk.CTkLabel(cell, text=info, text_color=OK_COLOR if info else MUTED, font=("Segoe UI", 10),
                               height=14)
            lbl.pack(pady=(0, 2))
            w["tile_widgets"][icon] = (cell, btn, lbl)
            if icon not in self.thumbs and icon not in self.thumb_pending:
                self.thumb_pending.add(icon)
                self._bg(self._load_thumb, icon)

    def _found_text(self, types) -> str:
        best = None
        n = 0
        for t in types:
            c = self.found_counts.get(t)
            if c:
                n += c[0]
                best = c[1] if best is None else min(best, c[1])
        return f"{n} · {best:.0f}" if n else ""

    def _toggle(self, i, icon):
        lc = self._lane_cfg(i)
        groups = set(lc.get("groups") or [])
        groups.symmetric_difference_update({icon})
        lc["groups"] = sorted(groups)
        cell = self.lane_widgets[i]["tile_widgets"].get(icon)
        if cell:
            cell[0].configure(border_color=SELECTED_BORDER if icon in groups else CARD_BG)
        self._save_quiet()

    def _select_all(self, i, on: bool):
        lc = self._lane_cfg(i)
        groups = catalog_mod.groups(self.cat, lc.get("kind") or "epic", int(lc.get("level") or 0)) if self.cat else {}
        lc["groups"] = sorted(groups) if on else []
        self._draw_tiles(self.lane_widgets[i])
        self._save_quiet()

    def _load_thumb(self, icon):
        with self.image_lock:
            if self.images is None:
                from ..unity import ImageIndex
                self.images = ImageIndex()
        path = self.images.path(icon)
        if not path:
            return
        img = Image.open(path).convert("RGBA")
        self.ui(self._put_thumb, icon, img)

    def _put_thumb(self, icon, img):
        self.thumbs[icon] = ctk.CTkImage(light_image=img, dark_image=img, size=(TILE, TILE))
        for w in self.lane_widgets:
            cell = w["tile_widgets"].get(icon)
            if cell:
                cell[1].configure(image=self.thumbs[icon], text="")

    def _draw_gear_label(self, w):
        lc = self._lane_cfg(w["index"])
        if not self.cat:
            w["gear_label"].configure(text="")
            return
        parts = []
        for g in lc.get("gear") or []:
            parts.append(gear_mod.piece_name(self.cat, g[1]) if g else "—")
        art = lc.get("artifact")
        art_name = self.cat["gear"]["artifacts"].get(int(art), {}).get("name") if art else "—"
        w["gear_label"].configure(text=f"🛡 {' · '.join(parts)}    ✦ {art_name}")

    # --------------------------------------------------------------- presets
    def _preset_names(self) -> List[str]:
        return sorted((self.settings.data.get("presets") or {}).keys())

    def _save_preset(self):
        name = (self.preset_box.get() or "").strip()
        if not name:
            name = simpledialog.askstring(tr("app.title"), tr("presets.ask_name"), parent=self) or ""
            name = name.strip()
        if not name:
            return
        self._commit_quantities()
        self.settings.save_preset(name)
        self.settings.save()
        self.preset_box.configure(values=self._preset_names())
        self.preset_box.set(name)
        logger.info(tr("presets.saved", name=name))

    def _load_preset(self):
        name = (self.preset_box.get() or "").strip()
        if self.settings.load_preset(name):
            self.settings.save()
            self._refresh_lanes()
            self._refresh_status_cards()
            logger.info(tr("presets.loaded", name=name))

    def _delete_preset(self):
        name = (self.preset_box.get() or "").strip()
        if name and messagebox.askyesno(tr("app.title"), tr("presets.confirm_delete", name=name)):
            self.settings.delete_preset(name)
            self.settings.save()
            self.preset_box.configure(values=self._preset_names())
            self.preset_box.set("")

    def _commit_quantities(self):
        for w in self.lane_widgets:
            self._lane_changed(w["index"])

    def _save_quiet(self):
        self.settings.save()

    # -------------------------------------------------------------- parâmetros
    def _build_params(self, tab):
        area = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        area.pack(fill="both", expand=True)
        ctk.CTkLabel(area, text=tr("params.intro"), text_color=MUTED, anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.param_widgets = {}
        for r, f in enumerate(FIELDS, start=1):
            ctk.CTkLabel(area, text=tr(f"param.{f.section}.{f.key}"), text_color=TEXT, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, 10), pady=3)
            value = self.settings.get(f.section, f.key)
            if f.type == "bool":
                var = ctk.BooleanVar(value=bool(value))
                wdg = ctk.CTkCheckBox(area, text="", variable=var)
                wdg.var = var
            elif f.type == "choice":
                opts = CHOICES[(f.section, f.key)]
                wdg = ctk.CTkOptionMenu(area, values=[tr(f"choice.{o}") for o in opts], width=220)
                wdg.set(tr(f"choice.{value}"))
                wdg.opts = {tr(f"choice.{o}"): o for o in opts}
            else:
                wdg = ctk.CTkEntry(area, width=320 if f.type == "str" else 120)
                wdg.insert(0, "" if value is None else str(value))
            wdg.grid(row=r, column=1, sticky="w", pady=3)
            ctk.CTkLabel(area, text=tr(f"param.{f.section}.{f.key}.help"), text_color=MUTED, anchor="w",
                         justify="left", wraplength=470).grid(row=r, column=2, sticky="w", padx=10)
            self.param_widgets[f] = wdg
        ctk.CTkButton(area, text=tr("params.save"), command=self._save_params).grid(
            row=len(FIELDS) + 1, column=0, sticky="w", pady=12)

    def _save_params(self):
        bad = []
        for f, wdg in self.param_widgets.items():
            try:
                if f.type == "bool":
                    self.settings.set_field(f, wdg.var.get())
                elif f.type == "choice":
                    self.settings.set_field(f, wdg.opts.get(wdg.get()))
                else:
                    self.settings.set_field(f, wdg.get())
            except ValueError:
                bad.append(tr(f"param.{f.section}.{f.key}"))
        self.settings.save()
        if bad:
            messagebox.showwarning(tr("app.title"), tr("params.invalid", fields=", ".join(bad)))
        else:
            logger.info(tr("params.saved"))

    # ---------------------------------------------------------------- combinar
    def _build_combine(self, tab):
        self.chains = None
        self.combine_res: Dict[int, int] = {}
        self.combine_worker: Optional[threading.Thread] = None
        self.combine_cancel = CancelToken()
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=(4, 4))
        self.combine_cat_names = {tr(f"combine.cat.{k}"): k for k in evo.CATEGORIES}
        self.combine_cat = ctk.CTkSegmentedButton(bar, values=list(self.combine_cat_names),
                                                  command=lambda _v: self._fill_combine())
        self.combine_cat.set(tr("combine.cat.gemas"))
        self.combine_cat.pack(side="left")
        self.combine_filter = ctk.CTkEntry(bar, placeholder_text=tr("combine.filter"), width=200)
        self.combine_filter.pack(side="left", padx=8)
        self.combine_filter.bind("<KeyRelease>", lambda _e: self._fill_combine())
        self.combine_only_stock = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(bar, text=tr("combine.only_stock"), variable=self.combine_only_stock,
                        command=self._fill_combine).pack(side="left", padx=4)
        ctk.CTkButton(bar, text=tr("combine.refresh"), width=150, fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=self._combine_refresh).pack(side="right")

        opts = ctk.CTkFrame(tab, fg_color="transparent")
        opts.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(opts, text=tr("combine.level"), text_color=MUTED).pack(side="left")
        self.combine_level = ctk.CTkOptionMenu(opts, values=[str(x) for x in range(2, 9)], width=70,
                                               command=lambda _v: self._fill_combine())
        self.combine_level.set("8")
        self.combine_level.pack(side="left", padx=(4, 12))
        ctk.CTkLabel(opts, text=tr("combine.quantity"), text_color=MUTED).pack(side="left")
        self.combine_qty = ctk.CTkEntry(opts, width=70)
        self.combine_qty.insert(0, "max")
        self.combine_qty.pack(side="left", padx=(4, 12))
        self.combine_gamble = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts, text=tr("combine.gamble"), variable=self.combine_gamble).pack(side="left")
        self.combine_stop_btn = ctk.CTkButton(opts, text=tr("run.stop"), width=110, fg_color=ERROR_COLOR,
                                              hover_color="#da3633", state="disabled",
                                              command=self.combine_cancel.cancel)
        self.combine_stop_btn.pack(side="right", padx=(6, 0))
        self.combine_btn = ctk.CTkButton(opts, text=tr("combine.start"), width=160, fg_color=OK_COLOR,
                                         hover_color="#2ea043", command=self._combine_start)
        self.combine_btn.pack(side="right")
        ctk.CTkLabel(tab, text=tr("combine.hint"), text_color=MUTED, anchor="w", justify="left",
                     wraplength=1100).pack(fill="x")

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Combine.Treeview", background=DARK_BG, fieldbackground=DARK_BG, foreground=TEXT,
                        rowheight=24, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Combine.Treeview.Heading", background=BUTTON_BG, foreground=TEXT, relief="flat",
                        font=("Segoe UI", 10, "bold"))
        style.map("Combine.Treeview", background=[("selected", ACCENT)])
        frame = ctk.CTkFrame(tab, fg_color=DARK_BG)
        frame.pack(fill="both", expand=True, pady=(6, 0))
        cols = ["item"] + [f"n{i}" for i in range(1, 9)] + ["ok"]
        self.combine_tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended",
                                         style="Combine.Treeview")
        self.combine_tree.heading("item", text=tr("combine.col.item"))
        self.combine_tree.column("item", width=300, anchor="w")
        for i in range(1, 9):
            self.combine_tree.heading(f"n{i}", text=f"{tr('combine.col.level')} {i}")
            self.combine_tree.column(f"n{i}", width=80, anchor="e")
        self.combine_tree.heading("ok", text=tr("combine.col.guaranteed"))
        self.combine_tree.column("ok", width=110, anchor="e")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.combine_tree.yview)
        self.combine_tree.configure(yscrollcommand=scroll.set)
        self.combine_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.combine_status = ctk.CTkLabel(tab, text=tr("combine.need_refresh"), text_color=MUTED, anchor="w")
        self.combine_status.pack(fill="x", pady=(4, 0))

    def _combine_category(self) -> str:
        return self.combine_cat_names.get(self.combine_cat.get(), "gemas")

    def _fill_combine(self):
        tree = self.combine_tree
        selected = {tree.item(i, "values")[0] for i in tree.selection()}
        tree.delete(*tree.get_children())
        if not self.chains:
            return
        level = int(self.combine_level.get())
        text = (self.combine_filter.get() or "").lower()
        pool = sorted(self.chains[str(evo.CATEGORIES[self._combine_category()])].values(), key=lambda c: c["pt"])
        for c in pool:
            s = [self.combine_res.get(i, 0) for i in c["ids"]]
            if self.combine_only_stock.get() and not any(s):
                continue
            if text and text not in c["pt"].lower() and text not in c["en"].lower():
                continue
            iid = tree.insert("", "end", values=[c["pt"]] + [f"{x:,}" for x in s] + [evo.guaranteed(s, level)])
            if c["pt"] in selected:
                tree.selection_add(iid)

    def _combine_refresh(self):
        if self.combine_worker and self.combine_worker.is_alive():
            return
        self.combine_status.configure(text=tr("combine.reading"), text_color=MUTED)
        self._bg(self._combine_refresh_work)

    def _combine_refresh_work(self):
        if self.chains is None:
            self.chains = evo.load_chains(self.settings.locale)
        link = GameLink(int(self.settings.get("browser", "cdp_port")))
        try:
            link.start()
            res = Game(link).state()["res"]
        finally:
            link.stop()
        self.ui(self._combine_refreshed, res)

    def _combine_refreshed(self, res):
        self.combine_res = res
        self._fill_combine()
        self.combine_status.configure(text=tr("combine.ready"), text_color=OK_COLOR)

    def _combine_start(self):
        if self.combine_worker and self.combine_worker.is_alive():
            return
        if not self.chains or not self.combine_res:
            messagebox.showinfo(tr("app.title"), tr("combine.need_refresh"))
            return
        names = [self.combine_tree.item(i, "values")[0] for i in self.combine_tree.selection()]
        if not names:
            messagebox.showinfo(tr("app.title"), tr("combine.select"))
            return
        raw = (self.combine_qty.get() or "max").strip().lower()
        try:
            qty = None if raw == "max" else max(1, int(raw))
        except ValueError:
            messagebox.showwarning(tr("app.title"), tr("combine.bad_qty"))
            return
        level = int(self.combine_level.get())
        cat = self._combine_category()
        chains = [self.chains[str(evo.CATEGORIES[cat])][n] for n in names]
        if not messagebox.askyesno(tr("app.title"), tr("combine.confirm", n=len(chains), level=level,
                                                         qty=raw, items=", ".join(names[:12]))):
            return
        self.combine_cancel.reset()
        self.combine_btn.configure(state="disabled")
        self.combine_stop_btn.configure(state="normal")
        self.combine_status.configure(text=tr("combine.running"), text_color=WARN_COLOR)
        self.combine_worker = threading.Thread(target=self._combine_work,
                                               args=(chains, level, qty, bool(self.combine_gamble.get())),
                                               daemon=True)
        self.combine_worker.start()

    def _combine_work(self, chains, level, qty, gamble):
        link = GameLink(int(self.settings.get("browser", "cdp_port")))
        try:
            link.start()
            res = Game(link).state()["res"]
            logger.info(tr("combine.log_start", n=len(chains), level=level))
            ev = evo.Evolver(link, res, log=logger.info, cancel=self.combine_cancel)
            ev.run(chains, level, qty, gamble)
            self.ui(self._combine_refreshed, Game(link).state()["res"])
            logger.info(tr("combine.log_done"))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"{tr('combine.title')}: {exc}")
        finally:
            link.stop()
            self.ui(self._combine_finished)

    def _combine_finished(self):
        self.combine_btn.configure(state="normal")
        self.combine_stop_btn.configure(state="disabled")
        if self.combine_cancel.requested:
            self.combine_status.configure(text=tr("combine.stopped"), text_color=WARN_COLOR)
        else:
            self.combine_status.configure(text=tr("combine.ready"), text_color=OK_COLOR)

    def _set_language(self, label):
        code = next(k for k, v in LANGUAGES.items() if v == label)
        if code != self.settings.language:
            self.settings.language = code
            self.settings.save()
            messagebox.showinfo(tr("app.title"), tr("app.restart_language"))

    # ------------------------------------------------------------- ações
    def _load_catalog(self):
        logger.info(tr("log.loading_catalog"))
        cat = catalog_mod.load(self.settings.locale)
        self.ui(self._catalog_ready, cat)

    def _catalog_ready(self, cat):
        self.cat = cat
        logger.info(tr("log.catalog_ready", n=len(cat["crypts"])))
        self._refresh_lanes()
        self._refresh_status_cards()

    def _open_game(self):
        def work():
            launched = self._browser().open_game()
            logger.info(tr("log.browser_launched") if launched else tr("log.browser_ready"))
        self._bg(work)

    def _connect(self):
        if self.running:
            return
        self._bg(self._connect_work)

    def _connect_work(self):
        if not self.cat:
            self._load_catalog_sync()
        logger.info(tr("log.connecting"))
        link = GameLink(int(self.settings.get("browser", "cdp_port")))
        try:
            link.start()
            g = Game(link)
            g.find_city()
            st = g.state()
            self.ui(self._connected, st)
            found = self._search_with(g, st)
            self.ui(self._show_found, found)
        finally:
            link.stop()

    def _load_catalog_sync(self):
        cat = catalog_mod.load(self.settings.locale)
        self.cat = cat

    def _connected(self, st):
        self.city_state = st
        res = st["res"]
        items = self.cat["items"]
        tar = " · ".join(f"{items.get(t, {}).get('name', t)}: {res.get(t, 0):,}"
                         for t in (catalog_mod.TAR, catalog_mod.RARE_TAR, catalog_mod.EPIC_TAR))
        keys = sum(res.get(k, 0) for k in catalog_mod.KEY_ITEMS)
        home = sum(1 for c in st["captains"].values() if c["home"] and c["id"] != catalog_mod.HERO)
        self.conn_label.configure(
            text=tr("run.connected", pos=f"X:{st['pos'][1]} Y:{st['pos'][2]}", caps=len(st["captains"]) - 1,
                    home=home) + f"\n{tar} · {tr('run.keys')}: {keys:,} · "
                 f"{items.get(catalog_mod.MARCH_SPEEDUP, {}).get('name', 'speedup')}: "
                 f"{res.get(catalog_mod.MARCH_SPEEDUP, 0):,}", text_color=OK_COLOR)
        logger.info(tr("log.connected"))
        self._refresh_lanes()
        self._refresh_status_cards()

    def _types_of_lanes(self) -> set:
        types = set()
        for lc in self.settings.data["lanes"]:
            groups = catalog_mod.groups(self.cat, lc.get("kind") or "epic", int(lc.get("level") or 0))
            for g in groups.values():
                types.update(g)
        return types

    def _search_with(self, g: Game, st) -> dict:
        types = self._types_of_lanes() or set(self.cat["crypts"])
        radius = int(self.settings.get("run", "search_radius"))
        if self.settings.get("run", "search_mode") == "scan":
            rows = g.scan(st["pos"], types, min(radius, 200))
        else:
            rows = g.search(st["pos"], types, radius)
        out = {}
        for c in rows:
            n, d = out.get(c["type"], (0, 1e9))
            out[c["type"]] = (n + 1, min(d, c["dist"]))
        logger.info(tr("log.search_done", n=len(rows), r=radius))
        return out

    def _search_map(self):
        if self.running:
            messagebox.showinfo(tr("app.title"), tr("app.busy"))
            return
        self._bg(self._connect_work)

    def _show_found(self, found):
        self.found_counts = found
        for w in self.lane_widgets:
            self._draw_tiles(w)

    def _refresh_status_cards(self, lanes=None):
        by_index = {x["index"]: x for x in (lanes or [])}
        for i, lbl in enumerate(self.status_labels):
            lc = self._lane_cfg(i)
            if not lc.get("enabled") or not lc.get("captain"):
                lbl.configure(text=f"{i + 1} · {tr('status.off')}", text_color=MUTED)
                continue
            name = (self.cat or {}).get("captains", {}).get(int(lc["captain"]), {}).get("name", f"#{lc['captain']}")
            s = by_index.get(i)
            qty = lc.get("quantity") or "∞"
            head = f"{i + 1} · {name} — {tr('kind.' + (lc.get('kind') or 'epic'))} {lc.get('level')}"
            if s:
                body = f"{s['done']}/{s['quantity'] or '∞'}  {s['status']}"
                color = OK_COLOR if s["finished"] else TEXT
            else:
                body = f"0/{qty}"
                color = TEXT
            lbl.configure(text=f"{head}\n{body}", text_color=color)

    def _start(self):
        if self.running:
            return
        if not self.cat:
            messagebox.showinfo(tr("app.title"), tr("lanes.loading"))
            return
        self._commit_quantities()
        self.settings.save()
        cancellation.reset()
        escape_watcher.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.connect_btn.configure(state="disabled")
        self.tabs.set(tr("tab.run"))
        self.worker = threading.Thread(target=self._run_work, daemon=True)
        self.worker.start()

    def _run_work(self):
        try:
            col = Collector(self.settings, self.cat, self._browser(), cancellation,
                            on_status=lambda lanes: self.ui(self._refresh_status_cards, lanes))
            col.run()
            logger.info(tr("log.finished"))
        except Cancelled:
            logger.info(tr("log.cancelled"))
        except (CollectorError, GameError, BrowserError) as exc:
            logger.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"{exc}")
        finally:
            escape_watcher.stop()
            self.ui(self._run_finished)

    def _run_finished(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.connect_btn.configure(state="normal")

    def _stop(self):
        cancellation.cancel()
        logger.info(tr("log.stopping"))

    def _open_gear(self, i):
        lc = self._lane_cfg(i)
        if not self.cat or not self.city_state:
            messagebox.showinfo(tr("app.title"), tr("gear.need_connect"))
            return
        if not lc.get("captain"):
            messagebox.showinfo(tr("app.title"), tr("gear.need_captain"))
            return
        GearWindow(self, i)

    def _on_close(self):
        if self.running:
            if not messagebox.askyesno(tr("app.title"), tr("app.confirm_close")):
                return
            cancellation.cancel()
        self._commit_quantities()
        self.settings.save()
        self.destroy()


class GearWindow(ctk.CTkToplevel):
    """Armaduras (3 espaços) e artefato de um capitão de uma faixa."""

    def __init__(self, app: App, lane: int):
        super().__init__(app)
        self.app, self.lane = app, lane
        self.cfg = app._lane_cfg(lane)
        self.cid = int(self.cfg["captain"])
        self.cat, self.st = app.cat, app.city_state
        self.gear = [list(g) if g else None for g in (self.cfg.get("gear") or [None, None, None])]
        self.gear += [None] * (3 - len(self.gear))
        self.artifact = self.cfg.get("artifact")
        self.slot = 0                       # 0..2 armadura, 3 artefato
        name = self.cat["captains"].get(self.cid, {}).get("name", self.cid)
        self.title(f"{tr('gear.title')} — {name}")
        self.configure(fg_color=PANEL_BG)
        place(self, 900, 560)
        self.transient(app)
        self.after(100, self.grab_set)
        self._build()
        self._redraw()

    def _build(self):
        left = ctk.CTkFrame(self, fg_color=CARD_BG)
        left.pack(side="left", fill="y", padx=10, pady=10)
        self.slot_btns = []
        for s in range(4):
            b = ctk.CTkButton(left, text="", width=300, anchor="w", fg_color=BUTTON_BG, hover_color=HOVER_BG,
                              command=lambda s=s: self._pick_slot(s))
            b.pack(fill="x", padx=8, pady=4)
            b.bind("<Button-3>", lambda _e, s=s: self._clear_slot(s))
            self.slot_btns.append(b)
        ctk.CTkLabel(left, text=tr("gear.hint"), text_color=MUTED, wraplength=290, justify="left").pack(padx=8, pady=6)
        ctk.CTkButton(left, text=tr("gear.copy"), fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=self._copy).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(left, text=tr("gear.clear"), fg_color=BUTTON_BG, hover_color=HOVER_BG,
                      command=self._clear).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(left, text=tr("gear.ok"), command=self._ok).pack(fill="x", padx=8, pady=(16, 4))
        right = ctk.CTkFrame(self, fg_color=CARD_BG)
        right.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)
        self.filter = ctk.CTkEntry(right, placeholder_text=tr("gear.filter"))
        self.filter.pack(fill="x", padx=8, pady=8)
        self.filter.bind("<KeyRelease>", lambda _e: self._fill_list())
        self.listbox = tk.Listbox(right, bg=DARK_BG, fg=TEXT, selectbackground=ACCENT, borderwidth=0,
                                  highlightthickness=0, font=("Segoe UI", 10), activestyle="none")
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.listbox.bind("<Double-Button-1>", lambda _e: self._assign())
        self.listbox.bind("<Return>", lambda _e: self._assign())
        self.rows: List[tuple] = []

    def _worn_by(self) -> Dict[int, int]:
        return {iid: c for c, v in self.st["captains"].items() for iid in v.get("gear", {}).values()}

    def _other_lanes(self) -> Dict[int, int]:
        out = {}
        for j, lc in enumerate(self.app.settings.data["lanes"]):
            if j == self.lane or not lc.get("enabled"):
                continue
            for g in lc.get("gear") or []:
                if g:
                    out[int(g[0])] = j
            if lc.get("artifact"):
                out[-int(lc["artifact"])] = j
        return out

    def _fill_list(self):
        self.listbox.delete(0, "end")
        self.rows = []
        text = (self.filter.get() or "").lower()
        others = self._other_lanes()
        if self.slot == 3:
            for aid, a in sorted(self.cat["gear"]["artifacts"].items(), key=lambda x: x[1]["name"]):
                if text and text not in a["name"].lower():
                    continue
                note = f"  — {tr('gear.in_lane', n=others[-aid] + 1)}" if -aid in others else ""
                self.listbox.insert("end", f"{a['name']}{note}")
                self.rows.append(("art", aid))
            return
        worn = self._worn_by()
        pieces = self.cat["gear"]["pieces"]
        entries = []
        for iid, it in self.st["items"].items():
            p = pieces.get(it["type"])
            if not p:
                continue
            label = f"{p['name']} · nv {p['tier']} · {tr('gear.durability')} {it['dur']}"
            if text and text not in label.lower():
                continue
            who = worn.get(iid)
            if iid in others:
                label += f"  — {tr('gear.in_lane', n=others[iid] + 1)}"
            elif who == catalog_mod.HERO:
                label += f"  — {tr('gear.hero')}"
            elif who and who != self.cid:
                label += f"  — {self.cat['captains'].get(who, {}).get('name', who)}"
            elif who == self.cid:
                label += f"  — {tr('gear.worn_here')}"
            entries.append((-p["tier"], p["name"], label, iid, it["type"]))
        for _t, _n, label, iid, ptype in sorted(entries):
            self.listbox.insert("end", label)
            self.rows.append(("piece", iid, ptype))

    def _redraw(self):
        for s, b in enumerate(self.slot_btns):
            if s < 3:
                g = self.gear[s]
                txt = gear_mod.piece_name(self.cat, g[1]) if g else tr("gear.empty")
                b.configure(text=f"{tr('gear.slot')} {s + 1}: {txt}")
            else:
                a = self.cat["gear"]["artifacts"].get(int(self.artifact), {}).get("name") if self.artifact else None
                b.configure(text=f"{tr('gear.artifact')}: {a or tr('gear.empty')}")
            b.configure(fg_color=ACCENT if s == self.slot else BUTTON_BG)
        self._fill_list()

    def _pick_slot(self, s):
        self.slot = s
        self._redraw()

    def _clear_slot(self, s):
        if s < 3:
            self.gear[s] = None
        else:
            self.artifact = None
        self._redraw()

    def _assign(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        row = self.rows[sel[0]]
        if row[0] == "art":
            self.artifact = row[1]
        else:
            iid = row[1]
            for s in range(3):
                if self.gear[s] and self.gear[s][0] == iid:
                    self.gear[s] = None
            self.gear[self.slot] = [iid, row[2]]
            self.slot = min(self.slot + 1, 2) if self.slot < 2 else 3
        self._redraw()

    def _copy(self):
        self.gear = gear_mod.from_game(self.st, self.cid)
        self._redraw()

    def _clear(self):
        self.gear, self.artifact = [None, None, None], None
        self._redraw()

    def _ok(self):
        plan = {self.cid: {"gear": self.gear, "artifact": self.artifact}}
        for j, lc in enumerate(self.app.settings.data["lanes"]):
            if j != self.lane and lc.get("enabled") and lc.get("captain"):
                plan[int(lc["captain"])] = {"gear": lc.get("gear") or [], "artifact": lc.get("artifact")}
        if gear_mod.conflicts(plan):
            messagebox.showwarning(tr("app.title"), tr("err.gear_conflict"), parent=self)
            return
        self.cfg["gear"], self.cfg["artifact"] = self.gear, self.artifact
        self.app.settings.save()
        self.app._draw_gear_label(self.app.lane_widgets[self.lane])
        self.destroy()


def launch():
    settings = Settings()
    app = App(settings)
    app.mainloop()
