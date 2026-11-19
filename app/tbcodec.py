"""O protocolo do Total Battle: MessagePack little-endian, frames e cauda de eventos.

Porte em Python de newchestcounter/src/tbcodec.rs. O jogo NAO usa MessagePack padrao:
tamanhos e inteiros multi-byte sao little-endian.

Frame:  [u32 LE total][u32 LE inner][msgpack: [route, seq, ...]][objetos...][cauda]
Rota 2 e lote: depois do cabecalho vem a quantidade de sub-frames e os sub-frames.
Cauda: registros [u32 len (conta os proprios 4 bytes)][msgpack...].

Chaves de mapa: str/int/bool ficam como estao; chaves que sao listas viram texto (repr),
como o leitor original fazia.
"""
from __future__ import annotations

import gzip
import struct
import zlib

ROUTE_BATCH = 2
MAX_DEPTH = 120
MAX_BLOB_DEPTH = 6


class DecodeError(Exception):
    pass


class Ext:
    def __init__(self, code: int, data: bytes):
        self.code, self.data = code, data

    def __repr__(self):
        return f"Ext({self.code}, {self.data.hex()})"


class Unpacker:
    def __init__(self, buf: bytes, pos: int = 0, end: int | None = None):
        self.b = buf
        self.p = pos
        self.end = len(buf) if end is None else end
        self.depth = 0

    def take(self, n: int) -> bytes:
        if self.p + n > self.end:
            raise DecodeError(f"read out of buffer at {self.p}")
        s = self.b[self.p:self.p + n]
        self.p += n
        return s

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def read(self):
        if self.p >= self.end:
            raise DecodeError(f"unexpected end of buffer at {self.p}")
        b = self.b[self.p]
        self.p += 1
        if b <= 0x7f:
            return b
        if b >= 0xe0:
            return b - 256
        if 0x80 <= b <= 0x8f:
            return self._map(b & 0x0f)
        if 0x90 <= b <= 0x9f:
            return self._array(b & 0x0f)
        if 0xa0 <= b <= 0xbf:
            return self._str(b & 0x1f)
        if b == 0xc0:
            return None
        if b == 0xc2:
            return False
        if b == 0xc3:
            return True
        if b == 0xc4:
            return self.take(self.u8())
        if b == 0xc5:
            return self.take(self.u16())
        if b == 0xc6:
            return self.take(self.u32())
        if b == 0xca:
            return struct.unpack("<f", self.take(4))[0]
        if b == 0xcb:
            return struct.unpack("<d", self.take(8))[0]
        if b == 0xcc:
            return self.u8()
        if b == 0xcd:
            return self.u16()
        if b == 0xce:
            return self.u32()
        if b == 0xcf:
            return struct.unpack("<Q", self.take(8))[0]
        if b == 0xd0:
            return struct.unpack("<b", self.take(1))[0]
        if b == 0xd1:
            return struct.unpack("<h", self.take(2))[0]
        if b == 0xd2:
            return struct.unpack("<i", self.take(4))[0]
        if b == 0xd3:
            return struct.unpack("<q", self.take(8))[0]
        if b == 0xd9:
            return self._str(self.u8())
        if b == 0xda:
            return self._str(self.u16())
        if b == 0xdb:
            return self._str(self.u32())
        if b == 0xdc:
            return self._array(self.u16())
        if b == 0xdd:
            return self._array(self.u32())
        if b == 0xde:
            return self._map(self.u16())
        if b == 0xdf:
            return self._map(self.u32())
        if 0xd4 <= b <= 0xd8:
            return self._ext(1 << (b - 0xd4))
        if b == 0xc7:
            return self._ext(self.u8())
        if b == 0xc8:
            return self._ext(self.u16())
        if b == 0xc9:
            return self._ext(self.u32())
        raise DecodeError(f"unknown format byte 0x{b:02x} at {self.p - 1}")

    def _enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise DecodeError(f"nesting above {MAX_DEPTH} at {self.p}")

    def _array(self, n):
        if n > self.end - self.p:
            raise DecodeError(f"impossible array ({n}) at {self.p}")
        self._enter()
        try:
            return [self.read() for _ in range(n)]
        finally:
            self.depth -= 1

    def _map(self, n):
        if 2 * n > self.end - self.p:
            raise DecodeError(f"impossible map ({n}) at {self.p}")
        self._enter()
        try:
            out = {}
            for _ in range(n):
                k = self.read()
                if not isinstance(k, (str, int, float, bool)) and k is not None:
                    k = repr(k)
                out[k] = self.read()
            return out
        finally:
            self.depth -= 1

    def _str(self, n):
        return self.take(n).decode("utf-8", "replace")

    def _ext(self, n):
        code = self.u8()
        return Ext(code, self.take(n))


def unpack(buf: bytes, pos: int = 0):
    return Unpacker(buf, pos).read()


def unpack_stream(data: bytes):
    """Objetos msgpack concatenados, sem frame, ocupando o buffer inteiro (WebSocket)."""
    if not data:
        return None
    u = Unpacker(data)
    out = []
    try:
        while u.p < len(data):
            out.append(u.read())
    except DecodeError:
        return None
    if out and isinstance(out[0], (list, dict)):
        return out
    return None


# ------------------------------------------------------------------ escrita

def pack(obj) -> bytes:
    out = bytearray()
    _pack(out, obj)
    return bytes(out)


def _pack(out: bytearray, o):
    if o is None:
        out.append(0xc0)
    elif o is True:
        out.append(0xc3)
    elif o is False:
        out.append(0xc2)
    elif isinstance(o, int):
        if 0 <= o <= 0x7f:
            out.append(o)
        elif -32 <= o < 0:
            out.append(o & 0xff)
        elif 0 <= o <= 0xff:
            out += b"\xcc" + struct.pack("<B", o)
        elif 0 <= o <= 0xffff:
            out += b"\xcd" + struct.pack("<H", o)
        elif 0 <= o <= 0xffffffff:
            out += b"\xce" + struct.pack("<I", o)
        elif o >= 0:
            out += b"\xcf" + struct.pack("<Q", o)
        elif o >= -0x80:
            out += b"\xd0" + struct.pack("<b", o)
        elif o >= -0x8000:
            out += b"\xd1" + struct.pack("<h", o)
        elif o >= -0x80000000:
            out += b"\xd2" + struct.pack("<i", o)
        else:
            out += b"\xd3" + struct.pack("<q", o)
    elif isinstance(o, float):
        out += b"\xcb" + struct.pack("<d", o)
    elif isinstance(o, str):
        raw = o.encode()
        n = len(raw)
        if n < 32:
            out.append(0xa0 | n)
        elif n <= 0xff:
            out += b"\xd9" + struct.pack("<B", n)
        elif n <= 0xffff:
            out += b"\xda" + struct.pack("<H", n)
        else:
            out += b"\xdb" + struct.pack("<I", n)
        out += raw
    elif isinstance(o, (bytes, bytearray)):
        n = len(o)
        if n <= 0xff:
            out += b"\xc4" + struct.pack("<B", n)
        else:
            out += b"\xc6" + struct.pack("<I", n)
        out += o
    elif isinstance(o, (list, tuple)):
        n = len(o)
        if n < 16:
            out.append(0x90 | n)
        elif n <= 0xffff:
            out += b"\xdc" + struct.pack("<H", n)
        else:
            out += b"\xdd" + struct.pack("<I", n)
        for i in o:
            _pack(out, i)
    elif isinstance(o, dict):
        n = len(o)
        if n < 16:
            out.append(0x80 | n)
        elif n <= 0xffff:
            out += b"\xde" + struct.pack("<H", n)
        else:
            out += b"\xdf" + struct.pack("<I", n)
        for k, v in o.items():
            _pack(out, k)
            _pack(out, v)
    else:
        raise TypeError(f"cannot pack {type(o)}")


def build_request(route: int, seq: int, auth, objects, tail: bytes = b"") -> bytes:
    """Pedido do cliente: [u32 total][u32 inner][[route, seq, auth, ""]][objects][tail]."""
    body = pack([route, seq, auth, ""]) + pack(objects)
    inner = 8 + len(body)
    return struct.pack("<II", inner + len(tail), inner) + body + tail


def parse_request(data: bytes):
    """(route, seq, auth, objects, tail) de um pedido do jogo, ou None."""
    if len(data) < 8:
        return None
    total, inner = struct.unpack_from("<II", data, 0)
    if total != len(data) or not (8 <= inner <= total):
        return None
    try:
        u = Unpacker(data, 8, inner)
        h = u.read()
        objs = []
        while u.p < inner:
            objs.append(u.read())
    except DecodeError:
        return None
    if not isinstance(h, list) or len(h) != 4 or not isinstance(h[2], list):
        return None
    return h[0], h[1], h[2], objs, data[inner:]


# ------------------------------------------------------------------ frames

class Frame:
    __slots__ = ("route", "seq", "header", "objects", "offset", "length", "error", "tail")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        return f"Frame(route={self.route}, seq={self.seq}, objects={len(self.objects or [])}, error={self.error})"


def iter_frames(buf: bytes) -> list[Frame]:
    out: list[Frame] = []
    _frames(buf, 0, len(buf), 0, out)
    return out


def _frames(buf, pos, end, depth, out):
    while pos + 8 <= end:
        total, inner = struct.unpack_from("<II", buf, pos)
        if total < 8 or pos + total > end:
            total = end - pos
        frame_end = pos + total
        content_end = pos + inner if 8 <= inner <= total else frame_end
        u = Unpacker(buf, pos + 8, frame_end)
        error = None
        header = None
        try:
            header = u.read()
        except DecodeError as e:
            error = str(e)
        route = seq = None
        if isinstance(header, list) and len(header) >= 2 and isinstance(header[0], int):
            route, seq = header[0], header[1]
        if route == ROUTE_BATCH and error is None and depth < 4:
            try:
                u.read()  # quantidade de sub-frames
                _frames(buf, u.p, frame_end, depth + 1, out)
            except DecodeError as e:
                out.append(Frame(route=route, seq=seq, header=header, objects=[], offset=pos,
                                 length=total, error=str(e), tail=b""))
        else:
            objects = []
            if error is None:
                c = Unpacker(buf, u.p, max(content_end, u.p))
                while c.p < content_end:
                    try:
                        objects.append(c.read())
                    except DecodeError as e:
                        error = str(e)
                        break
            out.append(Frame(route=route, seq=seq, header=header, objects=objects, offset=pos,
                             length=total, error=error, tail=buf[content_end:frame_end]))
        pos = frame_end


def tail_events(tail: bytes) -> list[list]:
    events = []
    pos = 0
    while pos + 4 <= len(tail):
        n = struct.unpack_from("<I", tail, pos)[0]
        if n <= 4 or pos + n > len(tail):
            break
        chunk = tail[pos + 4:pos + n]
        pos += n
        u = Unpacker(chunk)
        objs = []
        try:
            while u.p < len(chunk):
                objs.append(u.read())
        except DecodeError:
            continue
        if objs:
            events.append(objs)
    return events


def decompress(data: bytes) -> bytes:
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except Exception:
            return data
    if data[:4] == b"\x28\xb5\x2f\xfd":
        try:
            import zstandard
            return zstandard.ZstdDecompressor().decompressobj().decompress(data)
        except Exception:
            return data
    if len(data) > 2 and data[0] == 0x78 and data[1] in (0x01, 0x5E, 0x9C, 0xDA):
        try:
            return zlib.decompress(data)
        except Exception:
            return data
    return data


def expand_blobs(node, depth: int = 0):
    """Troca blobs binarios que sao msgpack por {"blob": [objetos]}."""
    if isinstance(node, (bytes, bytearray)):
        if depth < MAX_BLOB_DEPTH and len(node) >= 4:
            inner = unpack_stream(bytes(node))
            if inner is not None:
                return {"blob": [expand_blobs(x, depth + 1) for x in inner]}
        return node
    if isinstance(node, list):
        return [expand_blobs(x, depth) for x in node]
    if isinstance(node, dict):
        return {k: expand_blobs(v, depth) for k, v in node.items()}
    return node


def jsonable(o):
    """Para json.dumps: bytes viram {"hex": ...} (ou texto se for ASCII legivel)."""
    if isinstance(o, (bytes, bytearray)):
        b = bytes(o)
        if b and all(32 <= c < 127 for c in b):
            return {"bytes": b.decode()}
        return {"hex": b.hex()} if len(b) <= 256 else {"hex": b[:256].hex() + "...", "len": len(b)}
    if isinstance(o, Ext):
        return {"ext": o.code, "hex": o.data.hex()}
    if isinstance(o, list):
        return [jsonable(x) for x in o]
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, float) and o != o:
        return "NaN"
    return o
