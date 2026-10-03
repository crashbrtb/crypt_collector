"""Crypt Collector - ponto de entrada. Abre a interface; tudo o mais está no pacote `app`."""

import ctypes
import sys
import traceback


def hide_console():
    """Oculta a janela de console no Windows caso tenha sido iniciado via terminal/python.exe."""
    try:
        if sys.platform == "win32" and "--console" not in sys.argv:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass


def main() -> int:
    from app.logger import configure, logger

    configure()
    try:
        from app.gui.main_window import launch
        from app.version import __version__

        logger.info(f"Crypt Collector {__version__}")
        launch()
        return 0
    except Exception:
        # Um exe windowed com exceção não tratada não mostra nada: o traceback
        # vai para o log, que é o único lugar onde alguém o veria.
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    hide_console()
    sys.exit(main())
