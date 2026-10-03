"""
Versão do aplicativo.

A fonte é o arquivo VERSION na raiz do projeto. Ele acompanha o git sozinho: o
hook .githooks/post-commit grava nele a versão sempre que a mensagem do commit
começa com um número de versão (o padrão deste repositório: "2.0.1",
"2.1.0 - feat: ..."), então o arquivo, o commit e o executável empacotado
sempre dizem a mesma coisa.
"""

import os
import re
import subprocess

from .paths import BUNDLE_DIR, VERSION_FILE

VERSION_PATTERN = re.compile(r"^v?(\d+\.\d+\.\d+)")
UNKNOWN_VERSION = "0.0.0"


def _from_file() -> str:
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as fh:
            match = VERSION_PATTERN.match(fh.read().strip())
    except OSError:
        return ""
    return match.group(1) if match else ""


def _from_git() -> str:
    """Versão do commit mais recente cuja mensagem começa com um número de versão."""
    try:
        output = subprocess.run(
            ["git", "log", "-50", "--pretty=%s"],
            cwd=BUNDLE_DIR, capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    for subject in output.splitlines():
        match = VERSION_PATTERN.match(subject.strip())
        if match:
            return match.group(1)
    return ""


def get_version() -> str:
    # O git só é consultado se o arquivo sumir (um clone antigo, por exemplo).
    return _from_file() or (_from_git() if os.path.isdir(os.path.join(BUNDLE_DIR, ".git")) else "") \
        or UNKNOWN_VERSION


__version__ = get_version()
