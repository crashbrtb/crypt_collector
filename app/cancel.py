"""
Interromper uma execução com a tecla Esc ou com o botão Parar.

Toda espera longa passa por `cancellation.sleep()` em vez de `time.sleep()`,
então o cancelamento é percebido na hora e não depois dos minutos que uma marcha
leva.

A tecla é lida com GetAsyncKeyState, que informa o teclado físico seja qual for
a janela em foco. Os Esc que o próprio coletor envia para fechar janelas do jogo
vão pelo CDP e nunca tocam o teclado físico, então não cancelam a execução.
"""

import ctypes
import sys
import threading
import time
from typing import Optional

VK_ESCAPE = 0x1B
HOLD_SECONDS = 0.35     # um toque deliberado, não um esbarrão na tecla


class Cancelled(RuntimeError):
    """Levantada no primeiro ponto seguro depois de um pedido de cancelamento."""


class CancelToken:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    def reset(self):
        self._event.clear()

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def check(self):
        if self._event.is_set():
            raise Cancelled()

    def sleep(self, seconds: float):
        """Espera que termina antes da hora quando há cancelamento - e então levanta."""
        if seconds > 0 and self._event.wait(seconds):
            raise Cancelled()
        self.check()


class EscapeWatcher:
    """Observa o Esc físico e cancela o token quando ele é mantido pressionado."""

    def __init__(self, token: CancelToken, poll_interval: float = 0.1):
        self.token = token
        self.poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def _pressed() -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)

    def _watch(self, stop: threading.Event):
        while not stop.is_set():
            if self._pressed():
                held = time.time()
                while self._pressed() and not stop.is_set():
                    if time.time() - held >= HOLD_SECONDS:
                        self.token.cancel()
                        return
                    time.sleep(0.05)
            time.sleep(self.poll_interval)

    def start(self):
        if sys.platform != "win32" or (self._thread and self._thread.is_alive()):
            return
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, args=(self._stop,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread = None


cancellation = CancelToken()
escape_watcher = EscapeWatcher(cancellation)
