"""
O jogo dentro do Chrome, operado por CDP (Chrome DevTools Protocol).

Por que o navegador substituiu o cliente instalado
--------------------------------------------------
O cliente instalado só podia ser operado pela tela física: a janela tinha que
estar na frente, e cada clique era um movimento real do mouse que qualquer outra
janela podia roubar. Pelo CDP:

* as coordenadas são pixels CSS da página, não do monitor - a janela pode ser
  movida, e outra janela pode ficar por cima, sem quebrar nada;
* as capturas vêm de `Page.captureScreenshot`, sempre da página e só dela;
* o mouse e o teclado do usuário continuam livres durante a execução.

Quem faz o login é o usuário. Este módulo só abre o Chrome com a porta de
depuração (ou reaproveita um que já esteja aberto) e encontra a aba do jogo.
Ele nunca fecha o navegador.

Tudo aqui fala em pixels CSS relativos ao canto superior esquerdo da página.
"""

import base64
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import websocket

from .logger import logger

CHROME_PATHS = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
]

Region = Tuple[int, int, int, int]      # (left, top, width, height)


class BrowserError(RuntimeError):
    pass


class BrowserNotOpen(BrowserError):
    """Nenhum navegador escutando na porta CDP."""


class GameTabNotFound(BrowserError):
    """O navegador está aberto, mas nenhuma aba mostra o jogo."""


class Browser:
    """Uma aba do Chrome mostrando o Total Battle, com a entrada e a captura que ela aceita."""

    def __init__(self, config: Dict[str, Any], user_data_dir: str):
        self.host = "127.0.0.1"
        self.port = int(config.get("cdp_port", 9222))
        self.game_url = config.get("game_url") or "https://totalbattle.com/"
        self.url_filter = (config.get("url_filter") or "totalbattle.com").lower()
        self.executable_path = config.get("executable_path", "")
        self.user_data_dir = user_data_dir

        self.ws = None
        self.tab_id: Optional[str] = None
        # Escala do Windows: as capturas voltam multiplicadas por ela (ver capture()).
        self.dpr = 1.0
        self._msg_id = 0
        # Um socket, uma conversa por vez (ver send()).
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ http
    def _http(self, path: str, timeout: float = 2.0, method: str = "GET") -> Any:
        request = urllib.request.Request(f"http://{self.host}:{self.port}{path}", method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except ValueError:
            return body

    def is_cdp_ready(self) -> bool:
        try:
            self._http("/json/version", timeout=1.0)
            return True
        except (OSError, urllib.error.URLError, ValueError):
            return False

    @property
    def connected(self) -> bool:
        return self.ws is not None

    # ---------------------------------------------------------------- abertura
    def find_executable(self) -> Optional[str]:
        if self.executable_path and os.path.exists(self.executable_path):
            return self.executable_path
        for path in CHROME_PATHS:
            expanded = os.path.expandvars(path)
            if os.path.exists(expanded):
                return expanded
        return None

    def launch(self):
        """Abre o Chrome com depuração remota, em um perfil próprio do aplicativo."""
        executable = self.find_executable()
        if not executable:
            raise BrowserError("Chrome/Edge/Brave not found.")

        os.makedirs(self.user_data_dir, exist_ok=True)
        command = [
            executable,
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            # O Chrome recusa a depuração remota no perfil padrão; e um perfil
            # próprio guarda o login do jogo de uma execução para a outra.
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            # O jogo precisa continuar desenhando com outra janela por cima -
            # a deste aplicativo, por exemplo.
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-features=CalculateNativeWinOcclusion,Translate,TranslateUI",
            "--start-maximized",
            self.game_url,
        ]
        logger.info(f"Launching {os.path.basename(executable)} (CDP port {self.port})")
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        deadline = time.time() + 30
        while time.time() < deadline:
            if self.is_cdp_ready():
                return
            time.sleep(0.3)
        raise BrowserError(f"The browser did not answer on CDP port {self.port} within 30s.")

    def open_game(self) -> bool:
        """
        Garante um navegador com CDP e uma aba do jogo, e conecta a ela.

        Devolve True quando o navegador teve que ser aberto agora - é o caso em
        que o usuário ainda precisa fazer o login.
        """
        launched = False
        if not self.is_cdp_ready():
            self.launch()
            launched = True

        if not self.find_game_tab():
            try:
                # As versões recentes do Chrome exigem PUT aqui.
                self._http(f"/json/new?{self.game_url}", timeout=5.0, method="PUT")
            except (OSError, urllib.error.URLError):
                pass
            deadline = time.time() + 15
            while time.time() < deadline and not self.find_game_tab():
                time.sleep(0.5)

        self.attach()
        return launched

    def attach(self):
        """Conecta à aba do jogo de um navegador que já está aberto."""
        if not self.is_cdp_ready():
            raise BrowserNotOpen(f"No browser is listening on CDP port {self.port}.")
        tab = self.find_game_tab()
        if not tab or not tab.get("webSocketDebuggerUrl"):
            raise GameTabNotFound("No tab with the game was found in the browser.")

        self.disconnect()
        try:
            self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30,
                                                  suppress_origin=True)
        except Exception as exc:
            self.ws = None
            raise BrowserError(f"CDP websocket failed: {exc}")

        self.tab_id = tab.get("id")
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.make_visible()
        self.refresh_dpr()
        logger.info(f"Connected to tab: {(tab.get('url') or '')[:90]}")

    def reload(self):
        """Recarrega a página do jogo (F5). O jogo volta logado, pelo perfil do navegador."""
        self.send("Page.reload", {"ignoreCache": False})

    def reopen_game(self):
        """
        Abre o jogo de novo quando a aba não responde mais: aba nova, e a antiga fechada.

        Uma aba travada não atende nem ao pedido de recarregar, que passa por
        ela; abrir e fechar abas passa pelo navegador. A aba nova vem antes de
        fechar a antiga porque fechar a última aba encerra o Chrome. Se o
        navegador inteiro foi fechado, ele é aberto de novo.
        """
        self.disconnect()
        if self.is_cdp_ready():
            old = self.find_game_tab()
            try:
                self._http(f"/json/new?{self.game_url}", timeout=5.0, method="PUT")
                if old and old.get("id"):
                    self._http(f"/json/close/{old['id']}", timeout=5.0)
                    time.sleep(1.0)
            except (OSError, urllib.error.URLError, ValueError) as exc:
                logger.debug(f"reopen_game: {exc}")
        self.open_game()

    def ensure_attached(self):
        """Reconecta se a conexão caiu (aba recarregada, navegador reaberto)."""
        if self.ws is None:
            self.attach()

    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None

    # -------------------------------------------------------------------- abas
    def tabs(self) -> List[dict]:
        try:
            result = self._http("/json/list")
        except (OSError, urllib.error.URLError, ValueError):
            return []
        return result if isinstance(result, list) else []

    def find_game_tab(self) -> Optional[dict]:
        pages = [t for t in self.tabs() if t.get("type") == "page"]
        for tab in pages:
            if self.url_filter in (tab.get("url") or "").lower():
                return tab
        for tab in pages:
            if "total battle" in (tab.get("title") or "").lower():
                return tab
        return None

    def make_visible(self):
        """
        Deixa a aba do jogo em condição de desenhar.

        Uma aba em segundo plano ou uma janela minimizada não renderiza: as
        capturas voltariam congeladas e os cliques cairiam em uma tela que não
        se atualiza.
        """
        try:
            self._http(f"/json/activate/{self.tab_id}", timeout=2.0)
        except (OSError, urllib.error.URLError, ValueError):
            pass
        try:
            window = self.send("Browser.getWindowForTarget", {"targetId": self.tab_id})
            if window.get("bounds", {}).get("windowState") == "minimized":
                self.send("Browser.setWindowBounds",
                          {"windowId": window["windowId"], "bounds": {"windowState": "normal"}})
        except BrowserError as exc:
            logger.debug(f"make_visible: {exc}")
        try:
            # O jogo não deve pausar por achar que perdeu o foco.
            self.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        except BrowserError as exc:
            logger.debug(f"setFocusEmulationEnabled: {exc}")

    # --------------------------------------------------------------- protocolo
    def send(self, method: str, params: Optional[dict] = None, timeout: float = 30.0) -> dict:
        """
        Envia um comando e devolve o resultado.

        Serializado por um lock, porque é uma conversa de pergunta e resposta em
        um único socket: quem chama envia um id e lê até esse id voltar. Duas
        threads fazendo isso ao mesmo tempo engolem a resposta uma da outra.
        """
        with self._lock:
            if self.ws is None:
                raise BrowserError("No active CDP connection.")

            self._msg_id += 1
            msg_id = self._msg_id
            try:
                self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            except Exception as exc:
                self.disconnect()
                raise BrowserError(f"Failed to send {method}: {exc}")

            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    raw = self.ws.recv()
                except Exception as exc:
                    # Um socket lido pela metade não serve para o próximo comando.
                    self.disconnect()
                    raise BrowserError(f"CDP connection lost during {method}: {exc}")
                if not raw:
                    continue
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                if message.get("id") != msg_id:
                    continue        # eventos e respostas antigas
                if "error" in message:
                    raise BrowserError(f"{method}: {message['error'].get('message', message['error'])}")
                return message.get("result", {})

            self.disconnect()
            raise BrowserError(f"Timed out waiting for {method}.")

    def evaluate(self, expression: str, default: Any = None) -> Any:
        """Executa JavaScript na página e devolve o valor (default em caso de erro)."""
        result = self.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if result.get("exceptionDetails"):
            return default
        return result.get("result", {}).get("value", default)

    # ------------------------------------------------------------------ janela
    def refresh_dpr(self) -> float:
        value = self.evaluate("window.devicePixelRatio")
        self.dpr = float(value) if isinstance(value, (int, float)) and value > 0 else 1.0
        return self.dpr

    def viewport(self) -> Tuple[int, int]:
        size = self.evaluate("[window.innerWidth, window.innerHeight]") or [0, 0]
        return int(size[0]), int(size[1])

    def set_viewport(self, width: int, height: int, tolerance: int = 2, attempts: int = 4) -> bool:
        """
        Redimensiona a janela até a área da página ficar com `width` x `height`.

        As posições calibradas são coordenadas da página. Em uma página de outro
        tamanho todas teriam que ser reescaladas - e a interface de um jogo não
        escala de forma linear: um ponto reescalado escorrega para fora de um
        botão pequeno. Devolver a página ao tamanho calibrado elimina a reescala
        em vez de tentar compensá-la.
        """
        if width <= 0 or height <= 0:
            return False
        try:
            window = self.send("Browser.getWindowForTarget", {"targetId": self.tab_id})
            window_id = window["windowId"]
            bounds = window.get("bounds", {})

            for _ in range(attempts):
                inner_w, inner_h = self.viewport()
                if abs(inner_w - width) <= tolerance and abs(inner_h - height) <= tolerance:
                    return True
                if not inner_w or not inner_h:
                    return False
                # Largura e altura só podem ser definidas com a janela em estado normal.
                if bounds.get("windowState", "normal") != "normal":
                    self.send("Browser.setWindowBounds",
                              {"windowId": window_id, "bounds": {"windowState": "normal"}})
                    time.sleep(0.4)
                    bounds = self.send("Browser.getWindowForTarget",
                                       {"targetId": self.tab_id}).get("bounds", {})
                    inner_w, inner_h = self.viewport()
                self.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": {
                    "width": int(bounds.get("width") or inner_w) + (width - inner_w),
                    "height": int(bounds.get("height") or inner_h) + (height - inner_h),
                }})
                time.sleep(0.4)
                bounds = self.send("Browser.getWindowForTarget",
                                   {"targetId": self.tab_id}).get("bounds", {})
        except (BrowserError, KeyError) as exc:
            logger.debug(f"set_viewport: {exc}")
            return False

        self.refresh_dpr()
        inner_w, inner_h = self.viewport()
        return abs(inner_w - width) <= tolerance and abs(inner_h - height) <= tolerance

    # ----------------------------------------------------------------- entrada
    def move(self, x: float, y: float):
        self.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": float(x), "y": float(y), "button": "none", "buttons": 0,
        })

    def click(self, x: float, y: float):
        """
        Um clique que a página não distingue de um real.

        O movimento antes de pressionar não é enfeite: o canvas do jogo acompanha
        o hover, e botões que só reagem com o ponteiro em cima ignoram um clique
        que chega do nada.
        """
        self.move(x, y)
        time.sleep(0.05)
        common = {"x": float(x), "y": float(y), "button": "left", "clickCount": 1}
        self.send("Input.dispatchMouseEvent", dict(common, type="mousePressed", buttons=1))
        time.sleep(0.05)
        self.send("Input.dispatchMouseEvent", dict(common, type="mouseReleased", buttons=0))

    def scroll(self, x: float, y: float, delta_y: int):
        """Gira a roda do mouse sobre (x, y). Positivo rola para BAIXO."""
        self.move(x, y)
        time.sleep(0.03)
        self.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": float(x), "y": float(y),
            "deltaX": 0, "deltaY": int(delta_y), "button": "none", "buttons": 0,
        })

    def press_escape(self):
        for event_type in ("keyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", {
                "type": event_type, "key": "Escape", "code": "Escape",
                "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27,
            })

    # ----------------------------------------------------------------- captura
    def capture(self, region: Optional[Region] = None) -> Optional[np.ndarray]:
        """
        Uma imagem BGR da página, ou de uma região dela, em pixels CSS.

        O Chrome renderiza a captura na escala do monitor: com o Windows em 125%
        uma página de 1536 de largura volta com 1920. Como toda coordenada deste
        aplicativo é pixel CSS - é o que o clique recebe - a captura é pedida já
        dividida por essa escala.
        """
        view_w, view_h = self.viewport()
        if region:
            left, top = max(0, int(region[0])), max(0, int(region[1]))
            width = min(int(region[0] + region[2]), view_w) - left
            height = min(int(region[1] + region[3]), view_h) - top
        else:
            left, top, width, height = 0, 0, view_w, view_h
        if width <= 0 or height <= 0:
            return None

        result = self.send("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": False,
            "clip": {"x": float(left), "y": float(top), "width": float(width),
                     "height": float(height), "scale": 1.0 / (self.dpr or 1.0)},
        })
        data = result.get("data")
        if not data:
            return None
        image = cv2.imdecode(np.frombuffer(base64.b64decode(data), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None

        # O Chrome arredonda o recorte; um pixel de diferença aqui vira um
        # deslocamento nas contas de coordenadas.
        if (image.shape[1], image.shape[0]) != (width, height):
            image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
        return image
