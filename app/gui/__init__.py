"""Interface gráfica (customtkinter)."""

# Paleta compartilhada pelas janelas.
PANEL_BG = "#16181d"
CARD_BG = "#1c2029"
DARK_BG = "#0d1117"
BUTTON_BG = "#21262d"
HOVER_BG = "#30363d"
ACCENT = "#58a6ff"
OK_COLOR = "#3fb950"
WARN_COLOR = "#d29922"
ERROR_COLOR = "#f85149"
MUTED = "#8b949e"
TEXT = "#c9d1d9"


def place(window, width: int, height: int):
    """Dá à janela o tamanho pedido, limitado ao que cabe na tela, e a centraliza."""
    import customtkinter as ctk

    scaling = ctk.ScalingTracker.get_window_scaling(window) or 1.0
    screen_w = window.winfo_screenwidth() / scaling
    screen_h = window.winfo_screenheight() / scaling
    width = int(min(width, screen_w * 0.95))
    height = int(min(height, screen_h * 0.85))
    # A posição, ao contrário do tamanho, o customtkinter não converte.
    left = int((screen_w - width) / 2 * scaling)
    top = int(max(0, (screen_h - height) / 2 - 20) * scaling)
    window.geometry(f"{width}x{height}+{left}+{top}")
