"""Imagens do jogo pelo CDN Unity publico (porte de newchestcounter/src/unity.rs).

1. versions.totalbattle.com/config -> unity_catalog_version.webgl: o indice atual;
2. o indice mapeia cada nome de asset (`aod_crow_9_72`...) ao arquivo que o contem;
3. o arquivo e um bundle UnityFS (LZ4) com uma Texture2D RGBA32, linha de baixo primeiro.

As imagens sao guardadas em data/images/<nome>.png.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import lz4.block
import requests
from PIL import Image

from .paths import IMAGES_DIR

VERSIONS_URL = "https://versions.totalbattle.com/config"
ASSETS_URL = "https://assets-unity.totalbattle.dev/webgl"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"}
IMG_DIR = Path(IMAGES_DIR)
TEXTURE_RGBA32 = 4


def _get(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return r.content


def parse_index(data: bytes) -> dict[str, str]:
    out = {}
    i = 8
    while i + 4 <= len(data):
        n = struct.unpack_from("<I", data, i)[0]
        if n == 0 or n > 400 or i + 4 + n + 40 > len(data):
            break
        name = data[i + 4:i + 4 + n].decode("utf-8", "replace")
        j = i + 4 + n
        file_id = data[j + 4 + 16:j + 4 + 32].hex()
        j += 4 + 32
        if j + 4 > len(data):
            break
        count = struct.unpack_from("<I", data, j)[0]
        j += 4
        for _ in range(count):
            m = struct.unpack_from("<I", data, j)[0]
            j += 4 + m
        out[name] = file_id
        i = j
    return out


def _decomp(kind, data, size):
    if kind == 0:
        return data
    if kind in (2, 3):
        return lz4.block.decompress(data, uncompressed_size=size)
    raise ValueError(f"compressao {kind} nao suportada")


def unpack_bundle(d: bytes):
    if not d.startswith(b"UnityFS\0"):
        raise ValueError("nao e um bundle UnityFS")
    i = 8
    version = struct.unpack_from(">I", d, i)[0]
    i += 4
    for _ in range(2):
        i = d.index(b"\0", i) + 1
    compressed, uncompressed, flags = struct.unpack_from(">III", d, i + 8)
    i += 20
    if version >= 7:
        i = (i + 15) & ~15
    if flags & 0x80:
        info_raw = d[len(d) - compressed:]
    else:
        info_raw = d[i:i + compressed]
        i += compressed
    info = _decomp(flags & 0x3F, info_raw, uncompressed)
    k = 16
    blocks = struct.unpack_from(">I", info, k)[0]
    k += 4
    if flags & 0x200:
        i = (i + 15) & ~15
    data = bytearray()
    for _ in range(blocks):
        us, cs = struct.unpack_from(">II", info, k)
        bf = struct.unpack_from(">H", info, k + 8)[0]
        k += 10
        data += _decomp(bf & 0x3F, d[i:i + cs], us)
        i += cs
    nodes = struct.unpack_from(">I", info, k)[0]
    k += 4
    out = []
    for _ in range(nodes):
        off, size = struct.unpack_from(">QQ", info, k)
        k += 20
        end = info.index(b"\0", k)
        path = info[k:end].decode()
        k = end + 1
        out.append((path, bytes(data[off:off + size])))
    return out


def texture_of(files) -> Image.Image:
    main = next(b for p, b in files if not p.endswith(".resS"))
    stream = next((b for p, b in files if p.endswith(".resS")), None)
    le = lambda i: struct.unpack_from("<I", main, i)[0] if i + 4 <= len(main) else None  # noqa: E731
    at = None
    for i in range(0, len(main) - 16, 4):
        w, h, size, fmt = struct.unpack_from("<IIII", main, i)
        if 1 <= w <= 4096 and 1 <= h <= 4096 and fmt == TEXTURE_RGBA32 and size == w * h * 4:
            at = (i, w, h, size)
            break
    if not at:
        raise ValueError("sem textura RGBA32")
    start, w, h, size = at
    pixels = None
    j = start + 16
    while j + 4 <= len(main) and j < start + 400:
        n = le(j)
        if n == size and len(main) >= j + 4 + size:
            pixels = main[j + 4:j + 4 + size]
            break
        if n == 0 and stream is not None:
            off, ln = le(j + 4) or 0, le(j + 8) or 0
            if ln == size and off + size <= len(stream):
                pixels = stream[off:off + size]
                break
        j += 4
    if pixels is None:
        raise ValueError("pixels da textura nao encontrados")
    return Image.frombytes("RGBA", (w, h), pixels).transpose(Image.FLIP_TOP_BOTTOM)


class ImageIndex:
    def __init__(self):
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        cfg = json.loads(_get(VERSIONS_URL))["result"]["config"]
        self.id = cfg["unity_catalog_version"]["webgl"]
        cache = IMG_DIR.parent / f"unity_index_{self.id}.json"
        if cache.exists():
            self.files = json.loads(cache.read_text())
        else:
            self.files = parse_index(_get(f"{ASSETS_URL}/{self.id}"))
            cache.write_text(json.dumps(self.files))

    def find(self, *needles: str) -> list[str]:
        return sorted(n for n in self.files if all(x in n for x in needles))

    def path(self, name: str) -> Path | None:
        """PNG local do asset (baixa uma vez). None se o jogo nao tiver esse nome."""
        p = IMG_DIR / f"{name}.png"
        if p.exists():
            return p
        fid = self.files.get(name)
        if not fid:
            return None
        try:
            texture_of(unpack_bundle(_get(f"{ASSETS_URL}/{fid}"))).save(p)
        except Exception:  # noqa: BLE001
            return None
        return p
