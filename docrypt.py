import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageTk
import os
import configparser
import shutil
import subprocess
import sys
import threading
import queue
import time
import ctypes
import win32gui
import win32con
import win32com.client

def hide_console():
    """Oculta a janela de console no Windows caso tenha sido iniciado via terminal/python.exe."""
    try:
        if sys.platform == "win32":
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0) # 0 = SW_HIDE
    except Exception:
        pass
import timeit
import traceback
import pyautogui
import keyboard
from pynput import mouse

from language import UI, LANGUAGES, LOGS, MESSAGES, get_text, APP_VERSION
import screen_utils

# --- Configurações ---
# Dois diretórios diferentes quando empacotado pelo PyInstaller:
#   APP_DIR    - onde fica o docrypt.exe. É o lugar da config, que a calibração
#                reescreve e que precisa sobreviver a uma reinstalação.
#   BUNDLE_DIR - onde o PyInstaller extrai os 'datas' (a partir da versão 6 é a
#                subpasta _internal). É onde estão as imagens de referência.
# Antes os dois eram o mesmo caminho, e o exe procurava images/ e
# config_crypt.cfg ao lado de si mesmo, onde o PyInstaller 6 não os coloca.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
    SELF_SCRIPT = sys.executable
else:
    APP_DIR = BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    SELF_SCRIPT = os.path.abspath(__file__)

SCRIPT_DIR = APP_DIR  # mantido para o cwd dos subprocessos
CONFIG_FILE = os.path.join(APP_DIR, "config_crypt.cfg")


def ensure_config_file():
    """Na primeira execução do exe, copia a config empacotada para junto dele."""
    if os.path.exists(CONFIG_FILE):
        return
    bundled = os.path.join(BUNDLE_DIR, "config_crypt.cfg")
    if bundled != CONFIG_FILE and os.path.exists(bundled):
        try:
            shutil.copyfile(bundled, CONFIG_FILE)
        except OSError as e:
            print(f"Erro ao criar {CONFIG_FILE}: {e}")


IMAGE_BASE_DIR = os.path.join(BUNDLE_DIR, "images", "cript")
COMMON_DIR = os.path.join(IMAGE_BASE_DIR, "common")
EPIC_DIR = os.path.join(IMAGE_BASE_DIR, "epic")
RARE_DIR = os.path.join(IMAGE_BASE_DIR, "rare")
ICON_SIZE = (64, 64)
scroll_count = 0
# Caminho absoluto: antes era "images\\troopsonthemarch.png." (ponto sobrando).
TROOPS_IMAGE = os.path.join(BUNDLE_DIR, "images", "troopsonthemarch.png")


def get_current_language():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    lang = "pt"
    if config.has_section("Settings") and config.has_option("Settings", "language"):
        lang = config.get("Settings", "language")
    elif config.has_section("PREFERENCES") and config.has_option("PREFERENCES", "language"):
        lang = config.get("PREFERENCES", "language")
    return lang if lang in LANGUAGES else "pt"


# --- Funções Auxiliares ---

def activate_window_by_title(title):
    """Tenta encontrar, restaurar, maximizar e ativar uma janela pelo título usando pywin32."""
    hwnd = None
    try:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            print(get_text(LOGS, "window_found", current_language).format(title, hwnd))

            if win32gui.IsIconic(hwnd):
                print(get_text(LOGS, "window_minimized", current_language).format(title))
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)

            print(get_text(LOGS, "window_maximizing", current_language).format(title))
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.5)

            print(get_text(LOGS, "window_activating_wscript", current_language).format(title))
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.AppActivate(title)
                time.sleep(1.0)

                active_hwnd = win32gui.GetForegroundWindow()
                if active_hwnd == hwnd:
                    print(get_text(LOGS, "window_activated", current_language).format(title))
                    return True
                else:
                    print(
                        get_text(LOGS, "window_activation_failed", current_language).format(
                            win32gui.GetWindowText(active_hwnd), active_hwnd
                        )
                    )

                    print(get_text(LOGS, "trying_setforegroundwindow", current_language))
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.5)
                        active_hwnd = win32gui.GetForegroundWindow()
                        if active_hwnd == hwnd:
                            print(get_text(LOGS, "window_activated_setforegroundwindow", current_language).format(title))
                            return True
                        else:
                            print(get_text(LOGS, "setforeground_failed", current_language))
                            return False
                    except Exception as set_fg_e:
                        print(get_text(LOGS, "setforeground_error", current_language).format(set_fg_e))
                        return False

            except Exception as activate_e:
                print(get_text(LOGS, "wscript_activation_error", current_language).format(activate_e))
                return False

        else:
            print(get_text(LOGS, "window_not_found", current_language).format(title))
            return False
    except Exception as e:
        print(get_text(LOGS, "window_interaction_error", current_language).format(title, e))
        if hwnd:
            print(f"(HWND era: {hwnd})")
        return False


def get_image_files(directory):
    """Lista arquivos de imagem (.png, .jpg, .jpeg) em um diretório."""
    files = []
    if not os.path.isdir(directory):
        print(get_text(LOGS, "dir_not_found", current_language).format(directory))
        return files
    for f in os.listdir(directory):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            files.append(os.path.join(directory, f))
    return files


def get_relative_path(full_path):
    """Converte caminho absoluto para relativo à pasta 'cript'."""
    rel_path = os.path.relpath(full_path, BUNDLE_DIR).replace("\\", "/")
    if not rel_path.startswith("images/cript/"):
        parts = full_path.split(os.sep)
        try:
            cript_index = parts.index("cript")
            rel_path = "/".join(parts[cript_index + 1 :])
        except ValueError:
            print(get_text(LOGS, "rel_path_error", current_language).format(full_path))
            return full_path
    return rel_path


class ImageSelectorApp:
    def __init__(self, master):
        global current_language
        self.master = master
        master.title(f"{get_text(UI, 'main_title', current_language)} {APP_VERSION}")

        self.selected_paths = set()
        self.image_widgets = {}
        self.current_directory = None
        self.is_any_mode = False
        self.any_mode_label = None
        self.cripting_process = None
        self.output_queue = queue.Queue()
        self.status_window = None
        self.status_text_widget = None

        type_frame = ttk.Frame(master)
        type_frame.pack(pady=10)

        lang_frame = ttk.Frame(master)
        lang_frame.pack(pady=(10, 0), anchor="e", padx=10)

        ttk.Label(lang_frame, text=get_text(UI, "language", current_language)).pack(side=tk.LEFT, padx=(0, 5))
        self.language_label = lang_frame.winfo_children()[0]

        self.language_var = tk.StringVar()
        language_names = {code: name for code, name in LANGUAGES.items()}
        self.language_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.language_var,
            values=list(language_names.values()),
            state="readonly",
            width=10,
        )
        self.language_combo.pack(side=tk.LEFT)
        self.language_var.set(language_names.get(current_language, "Português"))
        self.language_combo.bind("<<ComboboxSelected>>", self.change_language)

        self.common_button = ttk.Button(
            type_frame,
            text=get_text(UI, "btn_common", current_language),
            command=lambda: self.load_images(COMMON_DIR),
        )
        self.common_button.pack(side=tk.LEFT, padx=5)
        self.epic_button = ttk.Button(
            type_frame,
            text=get_text(UI, "btn_epic", current_language),
            command=lambda: self.load_images(EPIC_DIR),
        )
        self.epic_button.pack(side=tk.LEFT, padx=5)
        self.rare_button = ttk.Button(
            type_frame,
            text=get_text(UI, "btn_rare", current_language),
            command=lambda: self.load_images(RARE_DIR),
        )
        self.rare_button.pack(side=tk.LEFT, padx=5)
        self.any_button = ttk.Button(
            type_frame,
            text=get_text(UI, "btn_any", current_language),
            command=self.select_any_mode,
        )
        self.any_button.pack(side=tk.LEFT, padx=5)
        self.calibrate_button = ttk.Button(
            type_frame, text=get_text(UI, "btn_calibrate", current_language), command=self.run_calibration
        )
        self.calibrate_button.pack(side=tk.LEFT, padx=5)

        self.icon_canvas = tk.Canvas(master, borderwidth=0, background="#ffffff")
        self.icon_frame = ttk.Frame(self.icon_canvas, style="My.TFrame")
        self.scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.icon_canvas.yview)
        self.icon_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.icon_canvas.pack(side="left", fill="both", expand=True)
        self.icon_canvas.create_window((4, 4), window=self.icon_frame, anchor="nw", tags="self.icon_frame")

        self.icon_frame.bind("<Configure>", self.on_frame_configure)

        footer_frame = ttk.Frame(master)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 2))
        footer_label = ttk.Label(footer_frame, text=get_text(UI, "developed_by", current_language))
        footer_label.pack(side=tk.LEFT)
        email_label = ttk.Label(footer_frame, text="Crash BR", foreground="blue", cursor="hand2")
        email_label.pack(side=tk.LEFT)
        email_label.bind("<Button-1>", lambda e: self.open_email())

        style = ttk.Style()
        style.configure("My.TFrame", background="white")

        self.play_button = ttk.Button(master, text=get_text(UI, "btn_play", current_language), command=self.run_script)
        self.play_button.pack(pady=(0, 5), side=tk.BOTTOM)

        self.select_all_button = ttk.Button(
            master, text=get_text(UI, "btn_select_all", current_language), command=self.select_all_visible
        )
        self.select_all_button.pack(pady=(0, 10), side=tk.BOTTOM)

        qty_frame = ttk.Frame(master)
        qty_frame.pack(pady=(0, 10), side=tk.BOTTOM)

        self.qty_label = ttk.Label(qty_frame, text=get_text(UI, "lbl_crypt_qty", current_language))
        self.qty_label.pack(side=tk.LEFT, padx=(0, 5))

        self.how_many_cripts_var = tk.StringVar()
        vcmd = (master.register(self.validate_numeric_input), "%P")

        self.how_many_cripts_entry = ttk.Entry(
            qty_frame, width=4, textvariable=self.how_many_cripts_var, validate="key", validatecommand=vcmd
        )
        self.how_many_cripts_entry.pack(side=tk.LEFT)

        self.load_initial_how_many_cripts()
        self.load_images(EPIC_DIR)

        master.protocol("WM_DELETE_WINDOW", self.on_main_window_close)

    def open_email(self):
        """Abre o cliente de e-mail padrão com o endereço de e-mail."""
        import webbrowser

        webbrowser.open("mailto:crashbrtb@gmail.com")

    def change_language(self, event=None):
        global current_language
        selected_lang_name = self.language_var.get()
        for code, name in LANGUAGES.items():
            if name == selected_lang_name:
                current_language = code
                break
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        if not config.has_section("Settings"):
            config.add_section("Settings")
        config.set("Settings", "language", current_language)
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        self.update_ui_language()

    def update_ui_language(self):
        self.master.title(f"{get_text(UI, 'main_title', current_language)} {APP_VERSION}")
        self.language_label.config(text=get_text(UI, "language", current_language))
        self.language_combo.set(get_text(UI, "language", current_language))
        self.play_button.config(text=get_text(UI, "btn_play", current_language))
        self.select_all_button.config(text=get_text(UI, "btn_select_all", current_language))
        self.qty_label.config(text=get_text(UI, "lbl_crypt_qty", current_language))
        self.common_button.config(text=get_text(UI, "btn_common", current_language))
        self.epic_button.config(text=get_text(UI, "btn_epic", current_language))
        self.rare_button.config(text=get_text(UI, "btn_rare", current_language))
        self.any_button.config(text=get_text(UI, "btn_any", current_language))
        self.calibrate_button.config(text=get_text(UI, "btn_calibrate", current_language))
        if self.is_any_mode and self.any_mode_label and self.any_mode_label.winfo_exists():
            self.any_mode_label.config(text=get_text(UI, "any_mode_active", current_language))

    def validate_numeric_input(self, value):
        """Valida se a entrada contém apenas números e tem no máximo 3 dígitos."""
        if value == "":
            return True
        if not value.isdigit():
            return False
        if len(value) > 3:
            return False
        return True

    def load_initial_how_many_cripts(self):
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            if "COORDINATES" in config and "how_many_cripts" in config["COORDINATES"]:
                value = config["COORDINATES"]["how_many_cripts"]
                self.how_many_cripts_var.set(value)
            else:
                self.how_many_cripts_var.set("5")
        except Exception as e:
            print(get_text(LOGS, "config_load_error", current_language).format(e))
            self.how_many_cripts_var.set("5")

    def on_frame_configure(self, event):
        """Reseta a scroll region para abranger o frame interno."""
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))

    def create_status_window(self):
        """Cria e configura a janela de status."""
        if self.status_window and self.status_window.winfo_exists():
            self.status_window.lift()
            return

        self.status_window = tk.Toplevel(self.master)
        self.status_window.title(get_text(UI, "status_title", current_language))
        self.status_window.geometry("400x250")

        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x_pos = screen_width - 410
        y_pos = screen_height - 240
        self.status_window.geometry(f"+{x_pos}+{y_pos}")

        self.status_window.attributes("-topmost", True)

        self.status_text_widget = scrolledtext.ScrolledText(self.status_window, wrap=tk.WORD, state="disabled")
        self.status_text_widget.pack(expand=True, fill="both", padx=5, pady=5)

        self.status_window.protocol("WM_DELETE_WINDOW", self.on_status_window_close)

    def update_status_window(self):
        """Verifica a fila e atualiza o widget de texto."""
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line is None:
                    self.append_to_status(get_text(LOGS, "script_finished", current_language))
                    self.cripting_process = None
                    return
                else:
                    self.append_to_status(line)
        except queue.Empty:
            pass

        if self.status_window and self.status_window.winfo_exists():
            self.master.after(100, self.update_status_window)

    def append_to_status(self, text):
        """Adiciona texto ao widget de status."""
        if self.status_text_widget and self.status_text_widget.winfo_exists():
            self.status_text_widget.config(state="normal")
            self.status_text_widget.insert(tk.END, text)
            self.status_text_widget.see(tk.END)
            self.status_text_widget.config(state="disabled")

    def read_process_output(self, process):
        """Lê a saída do processo em uma thread separada.

        Blindado de propósito: se esta thread morrer com uma exceção, ninguém
        fica sabendo (ela roda em background) e a janela de status congela para
        sempre sem nunca mostrar o fim do script. O finally garante que o sinal
        de fim seja enviado aconteça o que acontecer.
        """
        try:
            for line in iter(process.stdout.readline, ""):
                self.output_queue.put(line)
        except Exception as e:
            self.output_queue.put(f"\n[erro ao ler a saida do processo: {e!r}]\n")
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass
            self.output_queue.put(None)

    def on_main_window_close(self):
        """Chamado ao fechar a janela principal."""
        print(get_text(LOGS, "closing_main", current_language))
        if self.cripting_process:
            print(get_text(LOGS, "terminating_process", current_language))
            try:
                self.cripting_process.kill()
                self.cripting_process.wait(timeout=1)
                print(get_text(LOGS, "child_process_terminated", current_language))
            except Exception as e:
                print(get_text(LOGS, "child_process_error", current_language).format(e))
            finally:
                self.cripting_process = None

        if self.status_window and self.status_window.winfo_exists():
            print(get_text(LOGS, "destroying_status", current_language))
            self.status_window.destroy()
            self.status_window = None
            self.status_text_widget = None

        print(get_text(LOGS, "destroying_main", current_language))
        self.master.destroy()

        print(get_text(LOGS, "exiting_script", current_language))
        os._exit(0)

    def on_status_window_close(self):
        """Chamado ao fechar a janela de status."""
        print(get_text(LOGS, "closing_status", current_language))
        if self.cripting_process:
            print(get_text(LOGS, "trying_terminate_process", current_language))
            try:
                print(get_text(LOGS, "sending_kill", current_language))
                self.cripting_process.kill()
                self.cripting_process.wait(timeout=3)
                print(get_text(LOGS, "process_killed", current_language))
            except subprocess.TimeoutExpired:
                print(get_text(LOGS, "process_not_killed_timeout", current_language))
            except Exception as e:
                print(get_text(LOGS, "error_killing_process", current_language).format(e))
            finally:
                self.cripting_process = None
                print(get_text(LOGS, "process_ref_cleared", current_language))
                try:
                    if (
                        self.status_window
                        and self.status_window.winfo_exists()
                        and self.status_text_widget
                        and self.status_text_widget.winfo_exists()
                    ):
                        self.append_to_status("\n" + get_text(LOGS, "process_interrupted_by_user", current_language))
                except tk.TclError:
                    print(get_text(LOGS, "status_window_update_error", current_language))
        if self.status_window and self.status_window.winfo_exists():
            print(get_text(LOGS, "destroying_status_window", current_language))
            self.status_window.destroy()
        self.status_window = None
        self.status_text_widget = None
        print(get_text(LOGS, "status_window_closed", current_language))
        if self.master and self.master.winfo_exists():
            self.master.deiconify()

    def toggle_selection(self, path):
        """Adiciona ou remove um caminho da seleção."""
        widget_info = self.image_widgets.get(path)
        if not widget_info:
            return

        checkbutton = widget_info["checkbutton"]
        if path in self.selected_paths:
            self.selected_paths.remove(path)
            checkbutton.deselect()
            widget_info["label"].config(relief=tk.FLAT, background="white")
        else:
            self.selected_paths.add(path)
            checkbutton.select()
            widget_info["label"].config(relief=tk.SOLID, background="lightblue")

        print("Selecteds:", [get_relative_path(p) for p in self.selected_paths])

    def load_images(self, directory):
        """Carrega e exibe imagens do diretório especificado."""
        self.is_any_mode = False
        self.any_mode_label = None
        for widget in self.icon_frame.winfo_children():
            widget.destroy()
        self.image_widgets.clear()
        self.selected_paths.clear()
        self.current_directory = directory

        image_files = get_image_files(directory)
        if not image_files:
            messagebox.showinfo(
                get_text(UI, "info_title", current_language),
                get_text(UI, "no_images_found", current_language).format(os.path.basename(directory)),
            )
            return

        self.master.update_idletasks()
        canvas_width = self.icon_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 550

        item_width_estimate = ICON_SIZE[0] + 15
        cols = max(1, canvas_width // item_width_estimate)

        for i, img_path in enumerate(image_files):
            try:
                img = Image.open(img_path)
                img.thumbnail(ICON_SIZE)
                photo = ImageTk.PhotoImage(img)

                item_frame = ttk.Frame(self.icon_frame, style="My.TFrame")
                label = tk.Label(item_frame, image=photo, borderwidth=2, background="white")
                label.image = photo
                label.pack()
                label.bind("<Button-1>", lambda e, p=img_path: self.toggle_selection(p))

                var = tk.IntVar(value=0)
                chk = ttk.Checkbutton(item_frame, variable=var, command=lambda p=img_path: self.toggle_selection(p))
                chk.pack()

                row, col = divmod(i, cols)
                item_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nw")

                self.image_widgets[img_path] = {"label": label, "checkbutton": chk, "var": var}

            except Exception as e:
                print(get_text(LOGS, "image_load_error", current_language).format(img_path, e))

        self.master.update_idletasks()
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))

    def select_any_mode(self):
        """Ativa o modo 'Any', limpando a grade de imagens e marcando a flag is_any_mode."""
        self.is_any_mode = True
        self.current_directory = None
        self.selected_paths.clear()
        for widget in self.icon_frame.winfo_children():
            widget.destroy()
        self.image_widgets.clear()

        self.any_mode_label = ttk.Label(
            self.icon_frame,
            text=get_text(UI, "any_mode_active", current_language),
            font=("Segoe UI", 10, "italic"),
            wraplength=450,
            justify="center",
            padding=20,
        )
        self.any_mode_label.pack(expand=True, fill="both", pady=30, padx=10)
        self.master.update_idletasks()
        self.icon_canvas.configure(scrollregion=self.icon_canvas.bbox("all"))

    def select_all_visible(self):
        """Seleciona todas as imagens atualmente visíveis."""
        if not self.current_directory:
            print(get_text(LOGS, "no_directory_loaded", current_language))
            return

        print(get_text(LOGS, "selecting_all_in", current_language).format(os.path.basename(self.current_directory)))
        all_paths_in_current_dir = get_image_files(self.current_directory)

        for path in all_paths_in_current_dir:
            if path not in self.selected_paths:
                self.selected_paths.add(path)
            widget_info = self.image_widgets.get(path)
            if widget_info:
                widget_info["var"].set(1)
                widget_info["label"].config(relief=tk.SOLID, background="lightblue")

        print("Selecteds:", [get_relative_path(p) for p in self.selected_paths])

    def run_calibration(self):
        """Executa o script de calibração e fecha a janela principal."""
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--calibration"]
            else:
                cmd = [sys.executable, SELF_SCRIPT, "--calibration"]
            subprocess.Popen(cmd, cwd=SCRIPT_DIR, creationflags=creationflags)

            print(get_text(LOGS, "closing_main_for_calibration", current_language))
            self.master.destroy()

        except Exception as e:
            messagebox.showerror(
                get_text(UI, "error_title", current_language),
                get_text(UI, "calibration_script_error", current_language).format(e),
            )

    def run_script(self):
        """Salva a config, ativa a janela do jogo, executa o modo de cripta e mostra a saída."""
        if self.cripting_process:
            messagebox.showwarning(
                get_text(UI, "warning_title", current_language), get_text(UI, "script_already_running", current_language)
            )
            return
        if not self.is_any_mode and not self.selected_paths:
            messagebox.showwarning(
                get_text(UI, "warning_title", current_language), get_text(UI, "no_images_selected", current_language)
            )
            return

        how_many_value = self.how_many_cripts_var.get().strip()
        if not how_many_value:
            messagebox.showwarning(
                get_text(UI, "warning_title", current_language),
                get_text(UI, "enter_crypt_quantity", current_language),
            )
            return

        try:
            config = configparser.ConfigParser()
            config.optionxform = str
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
            if "COORDINATES" not in config:
                config["COORDINATES"] = {}
            if "Settings" not in config:
                config["Settings"] = {}

            config["COORDINATES"]["how_many_cripts"] = how_many_value

            if self.is_any_mode:
                config["COORDINATES"]["any_cript"] = "True"
                config["COORDINATES"]["search_cript"] = "['any']"
                config["Settings"]["selected_images"] = "any"
            else:
                config["COORDINATES"]["any_cript"] = "False"
                relative_paths = [get_relative_path(p) for p in self.selected_paths]
                config["COORDINATES"]["search_cript"] = str(relative_paths)
                config["Settings"]["selected_images"] = ",".join(relative_paths)

            with open(CONFIG_FILE, "w") as f:
                config.write(f)

            print(f"Configuração salva. Quantidade de criptas: {how_many_value}, modo Any: {self.is_any_mode}")
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")
            messagebox.showerror(
                get_text(UI, "error_title", current_language),
                get_text(UI, "save_config_fail", current_language).format(e),
            )
            return

        game_window_title = "Total Battle"
        print(get_text(LOGS, "trying_activate_window", current_language).format(game_window_title))
        if not activate_window_by_title(game_window_title):
            messagebox.showwarning(
                get_text(UI, "warning_title", current_language),
                get_text(UI, "game_window_not_found", current_language).format(game_window_title),
            )
            exit()

        self.create_status_window()
        self.append_to_status(get_text(LOGS, "starting_script", current_language))

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--crypting"]
        else:
            cmd = [sys.executable, "-u", SELF_SCRIPT, "--crypting"]

        # PYTHONUNBUFFERED: sem isso o filho usa buffer de bloco de 8 KB no pipe
        # e a janela de status fica parada em "Iniciando script...".
        child_env = os.environ.copy()
        child_env["PYTHONUNBUFFERED"] = "1"

        self.cripting_process = subprocess.Popen(
            cmd,
            cwd=SCRIPT_DIR,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # Tem que casar com o reconfigure do filho (screen_utils
            # .enable_line_buffering). Com o cp1252 padrão, um caractere fora
            # da tabela derrubava o filho ou a thread leitora, e a janela de
            # status congelava sem dizer nada.
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
            creationflags=creationflags,
        )

        self.output_reader_thread = threading.Thread(
            target=self.read_process_output, args=(self.cripting_process,), daemon=True
        )
        self.output_reader_thread.start()

        self.update_status_window()
        self.master.withdraw()


# --- Lógica de cripta ---
interrupted = False

# --- Diagnóstico ---
# O robô passa a maior parte do tempo dentro de chamadas que não imprimem nada.
# Quando ele "trava", sem isto não dá para saber em que passo parou. O watchdog
# roda numa thread separada e reporta o passo atual a cada intervalo: se o log
# para de sair mas o heartbeat continua, o processo está preso naquele passo;
# se o heartbeat também some, o processo morreu.
_run_start = time.time()
_step_lock = threading.Lock()
_current_step = "iniciando"
_step_since = time.time()


def log(msg):
    print("[%7.1fs] %s" % (time.time() - _run_start, msg), flush=True)


def set_step(name):
    global _current_step, _step_since
    with _step_lock:
        _current_step = name
        _step_since = time.time()


def start_watchdog(interval=15.0):
    def beat():
        while True:
            time.sleep(interval)
            with _step_lock:
                step, since = _current_step, _step_since
            log("heartbeat: parado em '%s' ha %.0fs" % (step, time.time() - since))

    threading.Thread(target=beat, daemon=True).start()


def find_image_on_screen(path_image, area, show=False, threshold=0.8):
    """
    Procura a imagem dentro da área e devolve o centro em coordenadas de tela.

    A busca é feita em várias escalas (screen_utils.locate), porque os PNGs de
    referência foram capturados em 1920x1080 e o cv2.matchTemplate não encontra
    a mesma imagem em outro tamanho.
    """
    set_step("procurando %s em %s" % (os.path.basename(path_image), area))
    started = time.time()
    result = screen_utils.locate(path_image, area, show=show, threshold=threshold)
    elapsed = time.time() - started
    if elapsed > 2.0:
        log("ATENCAO: busca de %s levou %.1fs" % (os.path.basename(path_image), elapsed))
    return result


def click(x, y):
    set_step("click(%s,%s)" % (x, y))
    pyautogui.click(x, y)
    time.sleep(2.0)


def move(x, y):
    pyautogui.moveTo(x, y)
    time.sleep(1.0)


def verify_store_screen():
    image_path = os.path.join(os_dir, "images\\bonussale.png")
    result = find_image_on_screen(image_path, screen_area)
    if result is None:
        return False
    image_path = os.path.join(os_dir, "images\\x.png")
    posx = find_image_on_screen(image_path, screen_area)
    if posx is None:
        return False
    click(posx[0], posx[1])
    return True


def search_for_x():
    set_step("search_for_x")
    image_path = os.path.join(os_dir, "images\\x.png")
    posx = find_image_on_screen(image_path, screen_area)
    if posx is None:
        return False
    log("x.png encontrado em %s, fechando a janela" % (posx,))
    click(posx[0], posx[1])
    return True


def list_files(directorys):
    files = []
    for directory in directorys:
        for raiz, _, files_directory in os.walk(directory):
            for file in files_directory:
                full_path = os.path.join(raiz, file)
                files.append((file, full_path))
    return files


def on_esc_press():
    global interrupted
    print(get_text(LOGS, "esc_pressed_interrupting", current_language))
    interrupted = True


def sleep_with_countdown(s):
    global interrupted
    s = int(s)
    for i in reversed(range(s + 1)):
        if interrupted:
            break
        print(i, end=" ")
        time.sleep(1)
    if not interrupted:
        print(get_text(LOGS, "time_is_over", current_language))


def open_cript_menu():
    log("abrindo menu de criptas: watchtower=%s cripts=%s centro=%s"
        % (cord_click_watchtower, cord_click_cripts, center_of_screen[0]))
    click(cord_click_watchtower[0], cord_click_watchtower[1])
    click(cord_click_cripts[0], cord_click_cripts[1])
    click(center_of_screen[0][0], center_of_screen[0][1])
    log("menu de criptas aberto")


def search_for_cripts(icons):
    mouse_scroll_counter = 0
    max_scroll = 500
    # Antes o contador voltava a zero e o while nunca terminava: em telas onde
    # nenhuma imagem casava, o script rolava a lista para sempre.
    max_restarts = 3
    restarts = 0
    log("procurando criptas: %d imagem(ns) na area %s" % (len(icons), area_cript_icons))
    if not icons:
        log("ATENCAO: nenhuma imagem selecionada para procurar")
    while mouse_scroll_counter <= max_scroll:
        if interrupted:
            break
        founded_cript = None
        best_icon, best_score = None, -1.0
        for icon in icons:
            image_path = os.path.join(os_dir, icon)
            # normaliza a barra: com o separador do Windows este teste nunca batia
            if "rare/2.png" in image_path.replace("\\", "/"):
                result = find_image_on_screen(image_path, area_cript_icons, False, 0.6)
            else:
                result = find_image_on_screen(image_path, area_cript_icons)
            if screen_utils.last_match["score"] > best_score:
                best_score = screen_utils.last_match["score"]
                best_icon = icon
            if result:
                founded_cript = icon
                break
        if founded_cript:
            log("cripta encontrada: %s (score %.3f)" % (founded_cript, best_score))
            click(cord_click_go_cript[0], cord_click_go_cript[1])
            return founded_cript
        # Sem isto era impossivel saber se o robo estava "quase" acertando.
        log("nenhuma cripta bateu o limiar; melhor palpite %s com score %.3f (escala %s)"
            % (best_icon, best_score, screen_utils.last_match["scale"]))
        set_step("rolando a lista de criptas")
        for _ in range(2):
            pyautogui.scroll(-20)
            mouse_scroll_counter = mouse_scroll_counter + 1
            time.sleep(0.2)
        log("rolagem acumulada: %d" % mouse_scroll_counter)
        if mouse_scroll_counter >= max_scroll:
            restarts = restarts + 1
            if restarts > max_restarts:
                print(get_text(LOGS, "error_serch_cript", current_language))
                return None
            if search_for_x():
                print(get_text(LOGS, "wrong_windows_opened", current_language))
            open_cript_menu()
            for _ in range(max_scroll):
                pyautogui.scroll(+20)
            mouse_scroll_counter = 0
    return None


def do_cript(founded_cript):
    click(center_of_screen[0][0], center_of_screen[0][1])
    if "rare" in founded_cript:
        click(open_button[0], open_button[1])
    image_path = os.path.join(os_dir, "images\\explore.png")
    result = find_image_on_screen(image_path, cord_explore_button)
    if result is None:
        print(get_text(LOGS, "explore_button_not_found", current_language))
        center_control = 1
        while center_control < 9:
            if interrupted:
                break
            if center_control > 0:
                search_for_x()
            if center_control > 2:
                pyautogui.press("esc")
            click(center_of_screen[center_control][0], center_of_screen[center_control][1])
            click(open_button[0], open_button[1])
            image_path = os.path.join(os_dir, "images\\explore.png")
            result = find_image_on_screen(image_path, cord_explore_button)
            if result is None:
                print(get_text(LOGS, "explorer_button_after_store_not_found", current_language))
                center_control = center_control + 1
            else:
                click(result[0], result[1])
                time.sleep(2.0)
                return True
    else:
        print(get_text(LOGS, "cripta_encontrada", current_language))
        click(result[0], result[1])
        time.sleep(2.0)
        return True


def speedup_march():
    click(cord_speedup_march[0], cord_speedup_march[1])
    if interrupted:
        return False

    result = find_image_on_screen(TROOPS_IMAGE, cord_click_use_speedups_screen)
    if interrupted:
        return False

    if result is None:
        print(get_text(LOGS, "error_in_speedy_march", current_language))
        time.sleep(1.0)
        return False
    for _ in range(how_many_speedups):
        if interrupted:
            break
        click(cord_click_use_speedups[0], cord_click_use_speedups[1])
    if interrupted:
        return False

    start = timeit.default_timer()
    while True:
        if interrupted:
            break
        result = find_image_on_screen(TROOPS_IMAGE, cord_click_use_speedups_screen)
        if result is None:
            print(get_text(LOGS, "troops_screen_close", current_language))
            break
        print(get_text(LOGS, "waiting_acceleration_screen_close", current_language))
        for _ in range(5):
            if interrupted:
                break
            time.sleep(1.0)
        if interrupted:
            break
    if interrupted:
        return False

    end = timeit.default_timer()
    print("Duration: %f" % (end - start))
    if not interrupted:
        sleep_with_countdown(end - start)

    return not interrupted


class CustomAlert:
    def __init__(self, title, text, button_text=None):
        self.result = None
        self.root = tk.Tk()
        self.root.title(title)

        window_width = 400
        window_height = 200
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        label = tk.Label(self.root, text=text, wraplength=380, pady=20)
        label.pack(expand=True)

        button = tk.Button(
            self.root, text=button_text or get_text(UI, "ok_button", current_language), command=self.on_button_click
        )
        button.pack(pady=20)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.grab_set()
        self.root.focus_set()
        self.root.mainloop()

    def on_button_click(self):
        self.result = True
        self.root.destroy()

    def on_close(self):
        self.result = None
        self.root.destroy()
        sys.exit(0)


def custom_alert(title, text, button="OK"):
    alert = CustomAlert(title, text, button)
    return alert.result


def capture_area():
    def start_selection(event):
        global start_x, start_y
        start_x, start_y = event.x, event.y
        canvas.create_rectangle(start_x, start_y, start_x, start_y, outline="red", tag="selection")

    def update_selection(event):
        canvas.coords("selection", start_x, start_y, event.x, event.y)

    def end_selection(event):
        global area
        # Grava em (left, top, width, height), que é o formato esperado por
        # pyautogui.screenshot(region=...). Antes gravava os cantos
        # (x1, y1, x2, y2) e a região de busca saía muito maior que a escolhida.
        area = screen_utils.corners_to_region((start_x, start_y, event.x, event.y))
        window.destroy()

    def on_closing():
        window.destroy()
        sys.exit(0)

    window = tk.Tk()
    window.title(get_text(UI, "mouse_selection_title", current_language))
    window.attributes("-fullscreen", True)
    window.attributes("-alpha", 0.3)

    canvas = tk.Canvas(
        window, width=window.winfo_screenwidth(), height=window.winfo_screenheight(), bg="white"
    )
    canvas.pack()

    canvas.bind("<Button-1>", start_selection)
    canvas.bind("<B1-Motion>", update_selection)
    canvas.bind("<ButtonRelease-1>", end_selection)

    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()
    return area


def get_click_postition():
    with mouse.Events() as events:
        for event in events:
            try:
                if event.button == mouse.Button.left:
                    return (event.x, event.y)
            except Exception:
                pass


def scroll_capture():
    custom_alert(
        get_text(UI, "scroll_capture_title", current_language),
        get_text(UI, "scroll_capture_msg", current_language),
    )

    def on_scroll(x, y, dx, dy):
        global scroll_count
        scroll_count += dy

    def on_click(x, y, button, pressed):
        if button == mouse.Button.left:
            return False

    with mouse.Listener(on_scroll=on_scroll, on_click=on_click) as listener:
        listener.join()

    return scroll_count


def get_monitor_resolution():
    # Mesma fonte que o run_crypting usa para reescalar as coordenadas, e o
    # mesmo monitor primário que o PIL captura.
    width, height = screen_utils.get_screen_size()
    res = (0, 0, width, height)
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if not config.has_section("COORDINATES"):
        config.add_section("COORDINATES")
    if not config.has_section("Settings"):
        config.add_section("Settings")

    # Converte de uma vez as áreas que ainda estejam no formato de cantos, para
    # que o config fique consistente mesmo se a calibração for abortada no meio.
    if screen_utils.get_config_version(config) < screen_utils.CONFIG_VERSION:
        for key in screen_utils.LEGACY_CORNER_KEYS:
            if config.has_option("COORDINATES", key):
                legacy = screen_utils.parse_value(config.get("COORDINATES", key))
                if legacy and len(legacy) == 4:
                    config.set("COORDINATES", key, str(screen_utils.corners_to_region(legacy)))

    config.set("COORDINATES", "screen_area", str(res))
    # Marca que as áreas deste config estão em (left, top, width, height).
    config.set("Settings", "config_version", str(screen_utils.CONFIG_VERSION))

    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    return width, height


def get_window_size(window_title):
    try:
        hwnd = win32gui.FindWindow(None, window_title)

        if hwnd:
            rect = win32gui.GetWindowRect(hwnd)
            x = rect[0]
            y = rect[1]
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            # Devolve também a origem: antes só o tamanho era retornado e o
            # chamador tratava largura/altura como coordenadas de tela.
            return (x, y, width, height)
        else:
            print(get_text(LOGS, "window_not_found", current_language).format(window_title))
            return None
    except Exception as e:
        print(get_text(LOGS, "window_size_error", current_language).format(e))
        return None


def calibration(opt, msg, title, type_cap):
    cord_click = []
    howmany = int

    if type_cap == 3:
        result = pyautogui.prompt(text=msg, title=title, default="")

        if result is None:
            sys.exit(0)
        howmany = int(result)
    else:
        result = custom_alert(title, msg, "OK")
        if result is None:
            sys.exit(0)

    if type_cap == 2:
        scroll_capture()
    if type_cap == 1:
        cord_click = get_click_postition()
    if type_cap == 0:
        cord_click = capture_area()
        pyautogui.click(cord_click[0] + 50, cord_click[1] + 20)

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if not config.has_section("COORDINATES"):
        config.add_section("COORDINATES")
    if type_cap == 2:
        config.set("COORDINATES", opt, str(scroll_count * -1))
    elif type_cap == 3:
        config.set("COORDINATES", opt, str(howmany))
    else:
        if opt == "center_of_screen":
            center_position = []
            rect = get_window_size("Total Battle")
            if rect is None:
                # Sem a janela do jogo, usa a tela inteira como referência.
                rect = (0, 0) + screen_utils.get_screen_size()
            origin_x, origin_y, window_width, window_height = rect
            width_square_distance = int(window_width / 9)
            height_square_distance = int(window_height / 9)
            center_x = origin_x + int(window_width / 2)
            center_y = origin_y + int(window_height / 2)
            posicao = center_x, center_y
            center_position.append(posicao)
            pyautogui.click(posicao)
            posicao = center_x, int(center_y + height_square_distance)
            center_position.append(posicao)
            posicao = center_x, int(center_y - height_square_distance)
            center_position.append(posicao)
            posicao = int(center_x + width_square_distance), center_y
            center_position.append(posicao)
            posicao = int(center_x - width_square_distance), center_y
            center_position.append(posicao)
            posicao = int(center_x + width_square_distance / 2), int(center_y + height_square_distance / 2)
            center_position.append(posicao)
            posicao = int(center_x - width_square_distance / 2), int(center_y - height_square_distance / 2)
            center_position.append(posicao)
            posicao = int(center_x + width_square_distance / 2), int(center_y - height_square_distance / 2)
            center_position.append(posicao)
            posicao = int(center_x - width_square_distance / 2), int(center_y + height_square_distance / 2)
            center_position.append(posicao)
            config.set("COORDINATES", opt, str(center_position))
            print(opt, "->", center_position)
        else:
            config.set("COORDINATES", opt, str(cord_click))
            print(opt, "-", cord_click)
            # A área do botão Explorar era gravada só em
            # verify_if_open_explorer_button, mas o crypting lê cord_explore_button:
            # o valor de Full HD ficava preso lá e o botão nunca era achado.
            if opt == "verify_if_open_explorer_button":
                config.set("COORDINATES", "cord_explore_button", str(cord_click))
                print("cord_explore_button -", cord_click)
            # cord_click_go_cript nunca era calibrado. Deriva do centro da área
            # do botão Go, que acabou de ser capturada.
            if opt == "area_menu_button_go_cript" and len(cord_click) == 4:
                go_click = (cord_click[0] + cord_click[2] // 2, cord_click[1] + cord_click[3] // 2)
                config.set("COORDINATES", "cord_click_go_cript", str(go_click))
                print("cord_click_go_cript -", go_click)

    with open(CONFIG_FILE, "w") as f:
        config.write(f)

    if type_cap != 3 and opt != "cord_click_use_speedups":
        custom_alert(
            get_text(UI, "calibration_title", current_language),
            get_text(UI, "position_captured", current_language).format(title),
        )
    if opt == "cord_click_use_speedups":
        custom_alert(
            get_text(UI, "calibration_title", current_language),
            get_text(UI, "position_captured_finished", current_language).format(title),
        )


def run_calibration_mode():
    try:
        result = custom_alert(
            get_text(UI, "calibration_title", current_language),
            get_text(MESSAGES, "calibration_instructions", current_language),
            get_text(UI, "start_button", current_language),
        )

        if result is None:
            sys.exit(0)
        game_window_title = "Total Battle"
        print(get_text(LOGS, "activating_window", current_language).format(game_window_title))
        if not activate_window_by_title(game_window_title):
            messagebox.showwarning(
                get_text(UI, "warning_title", current_language),
                get_text(MESSAGES, "window_not_found", current_language).format(game_window_title),
            )
            exit()

        get_monitor_resolution()

        calibration("cord_click_watchtower", get_text(MESSAGES, "click_watchtower_icon", current_language), "Watchtower", 1)
        calibration("cord_click_cripts", get_text(MESSAGES, "click_cripts_menu", current_language), "Cript Menu", 1)
        calibration(
            "area_cript_icons", get_text(MESSAGES, "select_cript_icon_area", current_language), "Cript icon", 0
        )
        calibration(
            "area_menu_button_go_cript",
            get_text(MESSAGES, "select_go_button_area", current_language),
            "Cript go button",
            0,
        )
        calibration("center_of_screen", get_text(MESSAGES, "click_cript_on_map", current_language), "Cript in map", 1)
        calibration("open_button", get_text(MESSAGES, "click_open_button", current_language), "Open Button", 1)
        calibration(
            "verify_if_open_explorer_button",
            get_text(MESSAGES, "select_explorer_button_area", current_language),
            "Explorer button icon",
            0,
        )
        calibration(
            "cord_speedup_march", get_text(MESSAGES, "click_speedup_button", current_language), "Speedup march", 1
        )
        calibration(
            "cord_click_use_speedups_screen",
            get_text(MESSAGES, "select_speedup_icon_area", current_language),
            "Speedup icon",
            0,
        )
        calibration("cord_click_use_speedups", get_text(MESSAGES, "click_use_button", current_language), "Use Speedup", 1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def run_crypting():
    global interrupted
    global os_dir
    global how_many_cripts
    global cord_click_watchtower
    global cord_click_cripts
    global area_menu_button_go_cript
    global cord_speedup_march
    global center_of_screen
    global cord_click_use_speedups_screen
    global cord_click_use_speedups
    global how_many_speedups
    global screen_area
    global open_button
    global test
    global area_cript_icons
    global cord_click_go_cript
    global search_cript
    global rare_cript
    global cord_explore_button

    interrupted = False
    # Sem isto os prints ficam presos no buffer do pipe e a janela de status
    # nunca sai de "Iniciando script...".
    screen_utils.enable_line_buffering()
    keyboard.add_hotkey("esc", on_esc_press)

    os_dir = BUNDLE_DIR
    config_path = CONFIG_FILE
    config = configparser.ConfigParser()
    config.read(config_path)
    if "COORDINATES" not in config:
        print(f"Error: Could not find [COORDINATES] section in {config_path}")
        return

    # Converte o formato antigo das áreas e reescala tudo da resolução usada na
    # calibração para a resolução atual. Em um monitor igual ao da calibração o
    # fator é 1.0 e nada muda.
    try:
        coords = screen_utils.load_coordinates(config)
    except Exception:
        print(f"Error: invalid [COORDINATES] section in {config_path}", flush=True)
        print(traceback.format_exc(), flush=True)
        return
    missing = [
        k
        for k in (
            "cord_click_watchtower",
            "cord_click_cripts",
            "center_of_screen",
            "open_button",
            "cord_speedup_march",
            "cord_click_use_speedups",
            "cord_click_use_speedups_screen",
            "area_cript_icons",
            "cord_click_go_cript",
        )
        if k not in coords
    ]
    if missing:
        print("Error: missing calibration keys: %s" % ", ".join(missing), flush=True)
        return

    how_many_cripts = coords["how_many_cripts"]
    cord_click_watchtower = coords["cord_click_watchtower"]
    cord_click_cripts = coords["cord_click_cripts"]
    area_menu_button_go_cript = coords.get("area_menu_button_go_cript")
    cord_speedup_march = coords["cord_speedup_march"]
    center_of_screen = coords["center_of_screen"]
    cord_click_use_speedups_screen = coords["cord_click_use_speedups_screen"]
    cord_click_use_speedups = coords["cord_click_use_speedups"]
    how_many_speedups = coords["how_many_speedups"]
    screen_area = coords["screen_area"]
    open_button = coords["open_button"]
    test = coords["test"]
    area_cript_icons = coords["area_cript_icons"]
    cord_click_go_cript = coords["cord_click_go_cript"]
    search_cript = coords["search_cript"]
    rare_cript = coords["rare_cript"]
    any_cript = coords["any_cript"]
    cord_explore_button = coords["cord_explore_button"]
    counter = 0
    errors = 0

    log("modo Any: %s | criptas alvo: %s | imagens: %s"
        % (any_cript, how_many_cripts, len(search_cript) if search_cript else 0))
    start_watchdog()

    try:
        for volta in range(how_many_cripts):
            if interrupted:
                break
            log("--- volta %d/%d ---" % (volta + 1, how_many_cripts))
            if search_for_x():
                print(get_text(LOGS, "store_screen_close", current_language))
            open_cript_menu()

            if any_cript:
                print(get_text(LOGS, "any_cript_selected", current_language))
                click(cord_click_go_cript[0], cord_click_go_cript[1])
                if search_for_x():
                    print(get_text(LOGS, "store_screen_close", current_language))
                if do_cript("any"):
                    print(get_text(LOGS, "Invading_crypt", current_language))
                    if speedup_march():
                        if interrupted:
                            break
                        print(get_text(LOGS, "cript_speedup", current_language))
                        counter += 1
                        print(counter, "/", how_many_cripts, " ", get_text(LOGS, "explored_cripts", current_language))
                    elif not interrupted:
                        print(get_text(LOGS, "error_in_speedup_march", current_language))
                        errors = errors + 1
                        print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))
                elif not interrupted:
                    print(get_text(LOGS, "error_in_cript", current_language))
                    errors = errors + 1
                    print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))
            else:
                founded_cript = search_for_cripts(search_cript)
                if founded_cript:
                    print("Cript found")
                    if search_for_x():
                        print(get_text(LOGS, "store_screen_close", current_language))
                    if do_cript(founded_cript):
                        print(get_text(LOGS, "Invading_crypt", current_language))
                        if speedup_march():
                            if interrupted:
                                break
                            print(get_text(LOGS, "cript_speedup", current_language))
                            counter += 1
                            print(counter, "/", how_many_cripts, " ", get_text(LOGS, "explored_cripts", current_language))
                        elif not interrupted:
                            print(get_text(LOGS, "error_in_speedup_march", current_language))
                            errors = errors + 1
                            print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))

                        elif not interrupted:
                            print(get_text(LOGS, "error_in_cript", current_language))
                            errors = errors + 1
                            print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))
                    elif not interrupted:
                        print(get_text(LOGS, "error_serch_cript", current_language))
                        errors = errors + 1
                        print(errors, " ", get_text(LOGS, "errors_was_detected", current_language))

            if interrupted:
                break

    except Exception:
        # Sem isto o sys.exit() do finally substituía a exceção em voo por
        # SystemExit e o traceback nunca chegava à janela de status.
        print("\n------------------------------------", flush=True)
        print(traceback.format_exc(), flush=True)
        print("------------------------------------", flush=True)
    finally:
        if interrupted:
            print("\n------------------------------------")
            print(get_text(LOGS, "cripting_interrupted", current_language))
            print("------------------------------------")

        if "keyboard" in sys.modules:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception as e:
                print(f"Erro ao remover hotkeys: {e}", flush=True)

        print(get_text(LOGS, "script_finish", current_language), flush=True)
        # Sem sys.exit() aqui: dentro de um finally ele substituía qualquer
        # exceção em voo por SystemExit. Quem encerra é o chamador.


def run_guarded(entry):
    """
    Executa um modo do app garantindo que o processo sempre termine.

    Medido neste projeto: um exe PyInstaller windowed (console=False) que sofre
    uma exceção não tratada NÃO encerra - fica vivo indefinidamente segurando o
    pipe. O launcher então nunca recebe o fim da saída, a janela de status
    congela na última linha e o robô parece ter travado do nada. Isso acontece
    tanto com disable_windowed_traceback=True quanto False; a flag não resolve.

    Aqui nenhuma exceção escapa, o traceback vai para a janela de status, e o
    os._exit() encerra na hora sem depender de threads pendentes.
    """
    code = 0
    try:
        entry()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
    except BaseException:
        screen_utils.enable_line_buffering()
        print("\n=== ERRO NAO TRATADO ===", flush=True)
        print(traceback.format_exc(), flush=True)
        code = 1
    try:
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(code)


# --- Execução Principal ---
if __name__ == "__main__":
    hide_console()
    # Antes de ler o idioma: na primeira execução do exe a config ainda não
    # existe ao lado dele.
    ensure_config_file()
    current_language = get_current_language()

    # Só os modos que trabalham com coordenadas de tela precisam ser DPI aware.
    # A janela principal fica de fora para não encolher a interface em telas
    # com escala do Windows acima de 100%.
    if "--crypting" in sys.argv:
        screen_utils.enable_dpi_awareness()
        run_guarded(run_crypting)
    elif "--calibration" in sys.argv:
        screen_utils.enable_dpi_awareness()
        run_guarded(run_calibration_mode)
    else:
        if not os.path.isdir(COMMON_DIR):
            print(f"Criando diretório ausente: {COMMON_DIR}")
            os.makedirs(COMMON_DIR, exist_ok=True)
        if not os.path.isdir(EPIC_DIR):
            print(f"Criando diretório ausente: {EPIC_DIR}")
            os.makedirs(EPIC_DIR, exist_ok=True)
        if not os.path.isdir(RARE_DIR):
            print(f"Criando diretório ausente: {RARE_DIR}")
            os.makedirs(RARE_DIR, exist_ok=True)

        def _gui():
            root = tk.Tk()
            app = ImageSelectorApp(root)
            root.mainloop()

        run_guarded(_gui)
