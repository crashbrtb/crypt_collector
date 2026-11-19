"""
O Chrome com o jogo: abrir, recarregar a página (F5) e reiniciar o navegador.

O coletor não clica nem lê a tela: o navegador só hospeda o jogo, de onde os pedidos
de rede saem (ver gamelink.py). Quem faz o login é o usuário, uma vez; o perfil próprio
do aplicativo guarda o login.

Quando o jogo trava (o erro do Unity que congela a página), o coletor primeiro recarrega
a aba; se o jogo não voltar, fecha esse Chrome (só o do perfil do aplicativo) e abre de novo.
"""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional

import websocket

from .logger import logger

CHROME_PATHS = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class BrowserError(RuntimeError):
    pass


class Browser:
    def __init__(self, config: dict, default_profile: str):
        self.port = int(config.get("cdp_port", 9222))
        self.game_url = config.get("game_url") or "https://totalbattle.com/"
        self.url_filter = (config.get("url_filter") or "totalbattle").lower()
        self.executable_path = config.get("executable_path", "")
        self.profile = config.get("profile_dir") or default_profile

    # ------------------------------------------------------------------ http
    def _http(self, path: str, timeout: float = 2.0, method: str = "GET"):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except ValueError:
            return body

    def is_ready(self) -> bool:
        try:
            self._http("/json/version", timeout=1.5)
            return True
        except (OSError, urllib.error.URLError, ValueError):
            return False

    def game_tab(self) -> Optional[dict]:
        try:
            tabs = self._http("/json/list")
        except (OSError, urllib.error.URLError, ValueError):
            return None
        pages = [t for t in tabs if isinstance(t, dict) and t.get("type") == "page"]
        return next((t for t in pages if self.url_filter in (t.get("url") or "").lower()), None)

    # ---------------------------------------------------------------- abrir
    def find_executable(self) -> Optional[str]:
        if self.executable_path and os.path.exists(self.executable_path):
            return self.executable_path
        for path in CHROME_PATHS:
            p = os.path.expandvars(path)
            if os.path.exists(p):
                return p
        return None

    def launch(self):
        exe = self.find_executable()
        if not exe:
            raise BrowserError("Chrome/Edge/Brave not found.")
        os.makedirs(self.profile, exist_ok=True)
        cmd = [
            exe,
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--disable-popup-blocking",
            # O jogo precisa continuar rodando com outra janela por cima.
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-features=CalculateNativeWinOcclusion,Translate,TranslateUI",
            "--start-maximized",
            self.game_url,
        ]
        logger.info(f"Abrindo {os.path.basename(exe)} (porta CDP {self.port})")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.is_ready():
                return
            time.sleep(0.5)
        raise BrowserError(f"O navegador não respondeu na porta {self.port} em 30 s.")

    def open_game(self) -> bool:
        """Garante o navegador e uma aba do jogo. True quando o navegador foi aberto agora."""
        launched = False
        if not self.is_ready():
            self.launch()
            launched = True
        if not self.game_tab():
            try:
                self._http(f"/json/new?{self.game_url}", timeout=5.0, method="PUT")
            except (OSError, urllib.error.URLError):
                pass
            deadline = time.time() + 20
            while time.time() < deadline and not self.game_tab():
                time.sleep(0.5)
        return launched

    # ------------------------------------------------------------ recuperar
    def reload(self) -> bool:
        """F5 na aba do jogo por uma conexão própria (a do coletor pode estar presa)."""
        tab = self.game_tab()
        if not tab or not tab.get("webSocketDebuggerUrl"):
            return False
        try:
            ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
            ws.send(json.dumps({"id": 1, "method": "Page.reload", "params": {"ignoreCache": False}}))
            ws.close()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"reload: {exc}")
            return False

    def close(self):
        """Fecha o Chrome que está na porta CDP: pelo CDP e, se não fechar, pelo processo.

        Antes de fechar, guarda o perfil (--user-data-dir) com que ele foi aberto, para abrir
        de novo com o mesmo login (o Chrome pode ter sido aberto pelo .exe, com outro perfil)."""
        pid, profile = self._listener()
        if profile:
            self.profile = profile
        try:
            info = self._http("/json/version", timeout=2.0)
            ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=5, suppress_origin=True)
            ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            ws.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Browser.close: {exc}")
        deadline = time.time() + 15
        while time.time() < deadline and self.is_ready():
            time.sleep(0.5)
        pids = ([pid] if pid and self.is_ready() else []) + self._profile_pids()
        for p in dict.fromkeys(pids):
            subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        if pids:
            logger.info(f"Navegador encerrado à força ({len(pids)} processo(s))")
            time.sleep(2)

    def _ps(self, script: str) -> str:
        try:
            return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                                  timeout=30, creationflags=NO_WINDOW).stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    def _listener(self) -> tuple:
        """(pid, perfil) do navegador que escuta na porta CDP."""
        out = self._ps(f"$c = Get-NetTCPConnection -LocalPort {self.port} -State Listen -ErrorAction SilentlyContinue "
                       "| Select-Object -First 1; if ($c) { $p = Get-CimInstance Win32_Process -Filter "
                       "\"ProcessId=$($c.OwningProcess)\"; \"$($c.OwningProcess)`n$($p.CommandLine)\" }")
        lines = out.strip().splitlines()
        if not lines or not lines[0].strip().isdigit():
            return None, None
        # "--user-data-dir=C:\com espaço" (aspas em volta do argumento todo) ou --user-data-dir=C:\sem_espaco
        m = re.search(r'"--user-data-dir=([^"]+)"|--user-data-dir="([^"]+)"|--user-data-dir=(\S+)',
                      lines[1] if len(lines) > 1 else "")
        return int(lines[0].strip()), next((g for g in m.groups() if g), None) if m else None

    def _profile_pids(self) -> list:
        """Processos do navegador abertos com este perfil (linha de comando com o --user-data-dir)."""
        needle = os.path.normcase(os.path.abspath(self.profile)).replace("'", "''").lower()
        out = self._ps("Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and "
                       r"$_.Name -match '^(chrome|msedge|brave)\.exe$' -and $_.CommandLine -and "
                       f"$_.CommandLine.ToLower().Contains('{needle}') }} | ForEach-Object {{ $_.ProcessId }}")
        return [int(x) for x in out.split() if x.strip().isdigit()]

    def restart(self):
        self.close()
        self.open_game()
