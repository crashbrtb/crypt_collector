"""Dados estaticos do cliente do jogo (porte de newchestcounter static_data.rs / mo.rs).

versions.totalbattle.com/config diz os hashes atuais de `strings`, `vectors` e `no_duplicates`
(MessagePack LE do jogo) e o catalogo de traducoes (.mo gettext por idioma). Tudo e guardado
em data/static/<hash> (paths.STATIC_DIR) e so e baixado de novo quando o jogo publica uma versao nova.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import requests

from . import tbcodec as tc
from .paths import STATIC_DIR

VERSIONS_URL = "https://versions.totalbattle.com/config"
STATIC_CDN = "https://assets-client-static.totalbattle.dev"
TRANSLATIONS_CDN = "https://assets-translations.totalbattle.dev"
CACHE = Path(STATIC_DIR)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"}


def _get(url: str) -> bytes:
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    return r.content


def _cached(name: str, url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / name
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes()
    data = _get(url)
    p.write_bytes(data)
    return data


def versions() -> dict:
    return json.loads(_get(VERSIONS_URL))["result"]["config"]


def parse_mo(data: bytes) -> dict[str, str]:
    magic = struct.unpack_from("<I", data, 0)[0]
    fmt = "<" if magic == 0x950412DE else ">"
    _, count, orig, trans = struct.unpack_from(fmt + "4I", data, 4)
    out = {}
    for i in range(count):
        olen, ooff = struct.unpack_from(fmt + "2I", data, orig + i * 8)
        tlen, toff = struct.unpack_from(fmt + "2I", data, trans + i * 8)
        k = data[ooff:ooff + olen]
        if b"\0" in k:
            continue
        out[k.decode("utf-8", "replace")] = data[toff:toff + tlen].decode("utf-8", "replace")
    return out


class StaticData:
    def __init__(self, locale: str = "pt_BR"):
        cfg = versions()
        prod = cfg["client_static_version"]["production"]
        self.hashes = {k: prod[k] for k in ("strings", "vectors", "no_duplicates")}
        catalog = json.loads(_get(f"{TRANSLATIONS_CDN}/{cfg['client_translations_catalog_version']}"))
        files = {f["name"]: f["md5"] for f in catalog["files"]}
        self.locale = locale if locale in files else "en_US"
        self.mo_md5 = files[self.locale]
        self.en_md5 = files.get("en_US")
        self._strings = self._vectors = None
        self._nodup_raw = None
        self._tables: dict[int, object] = {}
        self._tr = None

    # ------------------------------------------------------------ arquivos
    def raw(self, kind: str) -> bytes:
        return _cached(f"{self.hashes[kind]}_{kind}", f"{STATIC_CDN}/{self.hashes[kind]}")

    @property
    def strings(self) -> list:
        if self._strings is None:
            self._strings = tc.unpack(tc.decompress(self.raw("strings")))[0]
        return self._strings

    @property
    def vectors(self) -> list:
        if self._vectors is None:
            self._vectors = tc.unpack(tc.decompress(self.raw("vectors")))[0]
        return self._vectors

    @property
    def translations(self) -> dict:
        if self._tr is None:
            mo = tc.decompress(_cached(f"{self.mo_md5}_{self.locale}.mo", f"{TRANSLATIONS_CDN}/{self.mo_md5}"))
            self._tr = parse_mo(mo)
        return self._tr

    @property
    def en_translations(self) -> dict:
        if getattr(self, "_en", None) is None:
            self._en = parse_mo(tc.decompress(_cached(f"{self.en_md5}_en_US.mo", f"{TRANSLATIONS_CDN}/{self.en_md5}")))
        return self._en

    def vector_key(self, i) -> str:
        if not isinstance(i, int) or not (0 <= i < len(self.vectors)):
            return ""
        vec = self.vectors[i]
        return self.text(vec[0]) if isinstance(vec, list) and vec else ""

    def table_count(self) -> int:
        data = self._nodup()
        b = data[0]
        if 0x90 <= b <= 0x9F:
            return b & 0x0F
        return struct.unpack_from("<H" if b == 0xDC else "<I", data, 1)[0]

    def _nodup(self) -> bytes:
        if self._nodup_raw is None:
            self._nodup_raw = tc.decompress(self.raw("no_duplicates"))
        return self._nodup_raw

    def tables(self, wanted: list[int]) -> dict[int, object]:
        missing = [w for w in wanted if w not in self._tables]
        if missing:
            data = self._nodup()
            b = data[0]
            pos = 1 if 0x90 <= b <= 0x9F else (3 if b == 0xDC else 5)
            u = tc.Unpacker(data, pos)
            for idx in range(max(missing) + 1):
                t = u.read()
                if idx in missing or idx in wanted:
                    self._tables[idx] = t
        return {w: self._tables[w] for w in wanted}

    def all_tables(self) -> list:
        """Todas as tabelas numa passada; guardadas em pickle (a decodificacao em Python e lenta)."""
        import pickle
        p = CACHE / f"{self.hashes['no_duplicates']}.pickle"
        if p.exists():
            tabs = pickle.loads(p.read_bytes())
        else:
            n = self.table_count()
            tabs = list(self.tables(list(range(n))).values())
            p.write_bytes(pickle.dumps(tabs, protocol=pickle.HIGHEST_PROTOCOL))
        self._tables = dict(enumerate(tabs))
        return tabs

    # ------------------------------------------------------------ textos
    def text(self, i) -> str:
        if isinstance(i, int) and 0 <= i < len(self.strings):
            s = self.strings[i]
            return s if isinstance(s, str) else ""
        return ""

    def vector_text(self, i) -> str:
        """Um campo de texto da tabela: indice de vector -> [chave, placeholder, valor, ...]."""
        if not isinstance(i, int) or not (0 <= i < len(self.vectors)):
            return ""
        vec = self.vectors[i]
        if not isinstance(vec, list) or not vec:
            return ""
        key = self.text(vec[0])
        if not key:
            return ""
        tr = self.translations
        text = tr.get(key, key)
        for j in range(1, len(vec) - 1, 2):
            ph, vk = self.text(vec[j]), self.text(vec[j + 1])
            if ph:
                text = text.replace(ph, tr.get(vk, vk) if vk else "")
        return text
