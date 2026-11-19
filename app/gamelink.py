"""
Fala com o servidor do jogo de dentro da própria aba (mesma técnica do Autoattack).

A sessão, o jogador, o endereço do reino e a cauda de cursores são aprendidos dos
pedidos que o próprio jogo manda a cada segundo (Network.requestWillBeSent pelo
CDP). Os nossos pedidos saem por um fetch dentro da aba, com a mesma sessão. A
sessão fica só na memória: nunca é gravada nem escrita no log.

O horário do último pedido do jogo (`last_game_request`) é o sinal de vida usado
pelo vigia: um jogo travado (o erro do Unity/Java) para de mandar o heartbeat.
"""
from __future__ import annotations

import base64
import json
import re
import threading
import time
import urllib.request

import websocket

from . import tbcodec as tc

GAME_URL = re.compile(r"/rubens-realm", re.I)
B64_CHARS = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
REFUSED_ROUTE = 0xFFFE0000


class GameError(Exception):
    """O jogo recusou um pedido, ou respondeu algo inesperado."""


class LinkDown(GameError):
    """A aba não responde: CDP fechado, página travada ou recarregando."""


def _unwrap(raw: bytes) -> bytes:
    if tc.parse_request(raw) is None and raw and set(raw) <= B64_CHARS:
        try:
            return base64.b64decode(raw)
        except ValueError:
            pass
    return raw


def find_game_tab(port: int, url_filter: str = "totalbattle") -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as r:
            tabs = json.loads(r.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    pages = [t for t in tabs if t.get("type") == "page"]
    return next((t for t in pages if url_filter in (t.get("url") or "").lower()), None)


class GameLink:
    def __init__(self, port: int = 9222, url_filter: str = "totalbattle"):
        self.port = port
        self.url_filter = url_filter
        self.ws = None
        self.tab_id = None
        self.id = 0
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.waiters: dict[int, list] = {}
        self.bodies: dict[int, str] = {}
        self.address = None
        self.auth = None
        self.tail = b""
        self.seq = 0
        self.learned = threading.Event()
        self.running = False
        self.last_game_request = 0.0

    # ------------------------------------------------------------- CDP
    def _send(self, method, params=None, session=None, wait=False, timeout=30.0):
        with self.lock:
            self.id += 1
            i = self.id
            box = None
            if wait:
                box = [threading.Event(), None]
                self.waiters[i] = box
        msg = {"id": i, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        try:
            with self.send_lock:
                self.ws.send(json.dumps(msg))
        except Exception as exc:  # noqa: BLE001
            self.waiters.pop(i, None)
            self.running = False
            raise LinkDown(f"a conexão com a aba caiu ({exc})")
        if not wait:
            return i
        if not box[0].wait(timeout):
            self.waiters.pop(i, None)
            raise LinkDown(f"a aba não respondeu {method} em {timeout:.0f}s")
        return box[1]

    def start(self, wait: float = 30.0):
        tab = find_game_tab(self.port, self.url_filter)
        if not tab or not tab.get("webSocketDebuggerUrl"):
            raise LinkDown(f"nenhuma aba do Total Battle no navegador da porta {self.port}")
        self.tab_id = tab.get("id")
        try:
            self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
        except Exception as exc:  # noqa: BLE001
            raise LinkDown(f"não consegui conectar à aba do jogo ({exc})")
        self.ws.settimeout(0.5)
        self.running = True
        threading.Thread(target=self._reader, daemon=True, name="gamelink").start()
        self._send("Network.enable", {"maxPostDataSize": 1 << 20})
        if not self.learned.wait(wait):
            raise LinkDown("o jogo não mandou nenhum pedido para aprender a sessão (está logado e com o mapa aberto?)")

    def stop(self):
        self.running = False
        try:
            self._send("Network.disable")
        except Exception:  # noqa: BLE001
            pass
        try:
            self.ws.close()
        except Exception:  # noqa: BLE001
            pass

    def forget_session(self):
        """Depois de recarregar a página: a sessão e os cursores antigos não valem mais."""
        with self.lock:
            self.learned.clear()
            self.tail = b""
            self.address = None

    def reload_page(self):
        """F5 na aba do jogo, pela mesma conexão."""
        self.forget_session()
        self._send("Page.reload", {"ignoreCache": False}, wait=True, timeout=15)

    @property
    def alive(self) -> bool:
        return self.running and self.ws is not None

    def _reader(self):
        while self.running:
            try:
                raw = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:  # noqa: BLE001
                self.running = False
                break
            if not raw:
                continue
            head = raw[:90]
            if '"Network.' in head and "requestWillBeSent" not in head:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("method") == "Network.requestWillBeSent":
                req = d["params"].get("request") or {}
                url = req.get("url", "")
                if req.get("method") != "POST" or not GAME_URL.search(url):
                    continue
                entries = req.get("postDataEntries") or []
                if entries and entries[0].get("bytes"):
                    body = base64.b64decode("".join(e.get("bytes", "") for e in entries))
                    self._learn(url, body)
                elif req.get("hasPostData"):
                    try:
                        i = self._send("Network.getRequestPostData", {"requestId": d["params"]["requestId"]},
                                       d.get("sessionId"))
                    except LinkDown:
                        break
                    self.bodies[i] = url
            elif "id" in d:
                url = self.bodies.pop(d["id"], None)
                if url is not None:
                    pd = (d.get("result") or {}).get("postData")
                    if pd:
                        self._learn(url, bytes(ord(c) & 0xff for c in pd))
                    continue
                box = self.waiters.pop(d["id"], None)
                if box:
                    box[1] = d
                    box[0].set()
        # quem estiver esperando resposta não vai receber: libera já
        for box in list(self.waiters.values()):
            box[0].set()
        self.waiters.clear()

    def _learn(self, url: str, body: bytes):
        p = tc.parse_request(_unwrap(body))
        if not p:
            return
        route, seq, auth, _objs, tail = p
        with self.lock:
            self.last_game_request = time.time()
            if self.address and url != self.address and not tail:
                return
            self.seq = max(self.seq, seq)
            self.address = url
            self.auth = auth
            if route != tc.ROUTE_BATCH and tail:
                self.tail = tail
            if self.tail:
                self.learned.set()

    # ------------------------------------------------------------- pedidos
    @property
    def player_id(self):
        return self.auth[0][0] if self.auth else None

    def call(self, route: int, objects, timeout: float = 25.0):
        """Manda um pedido e devolve os frames que respondem a ele (objetos de cada um)."""
        if not self.alive:
            raise LinkDown("sem conexão com a aba do jogo")
        if not self.learned.wait(timeout):
            raise LinkDown("o jogo ainda não mandou a sessão (página recarregando?)")
        with self.lock:
            self.seq += 1
            body = tc.build_request(route, self.seq, self.auth, objects, self.tail)
            address = self.address
        script = (
            "(async()=>{const f=window.__TB_ORIG_FETCH__||window.fetch;"
            f"const r=await f.call(window,{json.dumps(address)},{{method:'POST',"
            "headers:{'Content-Type':'application/octet-stream'},"
            f"signal:AbortSignal.timeout({int(timeout * 1000)}),"
            f"body:Uint8Array.from(atob({json.dumps(base64.b64encode(body).decode())}),c=>c.charCodeAt(0))}});"
            "if(!r.ok)throw new Error('HTTP '+r.status);"
            "const b=new Uint8Array(await r.arrayBuffer());let s='';"
            "for(let i=0;i<b.length;i+=8192)s+=String.fromCharCode.apply(null,b.subarray(i,i+8192));"
            "return btoa(s);})()"
        )
        d = self._send("Runtime.evaluate", {"expression": script, "awaitPromise": True, "returnByValue": True},
                       wait=True, timeout=timeout + 5)
        if d is None:
            raise LinkDown(f"a aba fechou durante o pedido {route}")
        res = d.get("result") or {}
        if "exceptionDetails" in res or not isinstance((res.get("result") or {}).get("value"), str):
            raise LinkDown(f"o pedido {route} não saiu da aba: {json.dumps(res)[:300]}")
        data = tc.decompress(base64.b64decode(res["result"]["value"]))
        frames = tc.iter_frames(data)
        for f in frames:
            if f.route is not None and f.route >= REFUSED_ROUTE:
                raise GameError(f"o jogo recusou a rota {route}: {tc.jsonable(f.objects)}")
        mine = [f for f in frames if f.route == route and not f.error]
        if not mine:
            raise GameError(f"o jogo não respondeu a rota {route} (frames: {[f.route for f in frames]})")
        return mine
