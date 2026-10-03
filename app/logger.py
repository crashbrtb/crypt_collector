"""Log único do aplicativo: arquivo em logs/ e, quando a interface está aberta, a caixa de log."""

import logging
import os
import queue
from logging.handlers import RotatingFileHandler

from .paths import LOG_DIR

logger = logging.getLogger("crypt_collector")
logger.setLevel(logging.DEBUG)
logger.propagate = False

LOG_FILE = os.path.join(LOG_DIR, "crypt_collector.log")
_configured = False


def configure():
    """Liga o log em arquivo. Uma pasta sem permissão de escrita não impede o uso."""
    global _configured
    if _configured:
        return
    _configured = True
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s"))
    logger.addHandler(handler)


class QueueHandler(logging.Handler):
    """Entrega o log à interface sem bloquear a thread que está trabalhando."""

    def __init__(self, sink: queue.Queue):
        super().__init__(level=logging.INFO)
        self.sink = sink
        self.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S"))

    def emit(self, record):
        try:
            self.sink.put_nowait((record.levelno, self.format(record)))
        except Exception:
            pass
