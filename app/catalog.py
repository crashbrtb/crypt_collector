"""
Catálogo compacto tirado dos dados estáticos do jogo, gerado uma vez por versão do jogo
em data/catalog_<hash>.json.

Tabelas de `_no_duplicates` (medidas em 18/11/2026):
  7    objetos do mapa. Criptas: r[1] == 7. r[3] nome (vector), r[5] JSON {"icon", "visual"}
       (texto ou {"1": ...}), r[6][0] {69: saúde da cripta}, r[14][0] {chave: qtd} (raras),
       r[15] nível.
  8    itens: r[3] nome, r[5] ícone. 28/29/32/34 alcatrões, 69 saúde da cripta,
       80..84 Chave do Dragão, 2102 aceleração de marcha.
  11   peças de equipamento: r[1] tipo, r[2] ícone, r[3] nome, r[5] nível.
  75   capitães: r[5] nome, r[7] JSON visual (animationLinkage battler_<alias>_unit).
  110  artefatos (chave "[13]"): r[8] nome, r[7] JSON com o ícone.
"""
from __future__ import annotations

import json
import os
import re

from .paths import DATA_DIR

FORMAT = 4

# Nome inglês do tipo do mapa -> família da cripta. O resto ("Test Crypt", arenas,
# Tártaro, que tem várias etapas) fica de fora.
KINDS = {
    "Crypt": "common",
    "Rare Crypt": "rare",
    "Epic Crypt": "epic",
    "Abandoned Crypt": "abandoned",
    "Treasure Hunt Crypt": "th_common",
    "Rare Treasure Hunt Crypt": "th_rare",
    "Epic Treasure Hunt Crypt": "th_epic",
}
KIND_ORDER = ["common", "rare", "epic", "abandoned", "th_common", "th_rare", "th_epic"]

# Alcatrão que cada família leva na marcha (raro e épico conferidos na captura de 18/11/2026;
# comum com o "Alcatrão" (item 13, conferido no estoque em 18/11/2026); abandonada pela descrição do item).
TAR, COAL_TAR, BLOODY_TAR, EPIC_TAR, RARE_TAR = 13, 28, 29, 32, 34
TAR_BY_KIND = {"common": TAR, "th_common": TAR, "rare": RARE_TAR, "th_rare": RARE_TAR, "epic": EPIC_TAR, "th_epic": EPIC_TAR,
               "abandoned": BLOODY_TAR}
CRYPT_HEALTH = 69
KEY_ITEMS = (80, 81, 82, 83, 84)
MARCH_SPEEDUP = 2102
HERO = 1

GEAR_KINDS = {2: "weapon", 5: "head", 6: "torso", 7: "legs", 8: "trinket"}


def _icon(js: str, field: str) -> str:
    try:
        v = json.loads(js).get(field)
    except (ValueError, AttributeError, TypeError):
        return ""
    if isinstance(v, dict):
        v = next(iter(v.values()), "")
        if isinstance(v, dict):
            v = next(iter(v.values()), "")
    return v if isinstance(v, str) else ""


def build_crypts(sd) -> dict:
    t7 = sd.all_tables()[7]
    en = sd.en_translations
    out = {}
    for tid, r in t7.items():
        if not (isinstance(tid, int) and isinstance(r, list) and len(r) > 15 and r[1] == 7):
            continue
        kind = KINDS.get(en.get(sd.vector_key(r[3]), ""))
        if not kind:
            continue
        js = sd.text(r[5])
        try:
            health = int((r[6][0] or {}).get(CRYPT_HEALTH, 0))
        except (IndexError, AttributeError, TypeError, ValueError):
            health = 0
        key = {}
        try:
            key = {int(k): int(v) for k, v in (r[14][0] or {}).items()}
        except (IndexError, AttributeError, TypeError, ValueError):
            pass
        out[tid] = {"kind": kind, "level": r[15] if isinstance(r[15], int) else 0,
                    "name": sd.vector_text(r[3]), "icon": _icon(js, "icon"), "visual": _icon(js, "visual"),
                    "health": health, "key": key, "tar": TAR_BY_KIND.get(kind)}
    return out


def build_captains(sd) -> dict:
    tr = sd.translations
    out = {}
    for cid, r in sd.all_tables()[75].items():
        if not isinstance(cid, int) or not (1 <= cid < 1000) or not isinstance(r, list) or len(r) < 8:
            continue
        js = sd.text(r[7])
        m = re.search(r'"animationLinkage":"battler_(\w+?)_unit"', js)
        alias = m.group(1) if m else ""
        name = tr.get(f"battler_unit.name.{alias}") or sd.vector_text(r[5]) or f"#{cid}"
        battle = re.search(r'"battleIcon":"(\w+)"', js)
        icons = [f"{alias}_icon"] if alias else []
        if battle:
            icons.append(battle.group(1))
        out[cid] = {"name": name, "icon": "|".join(icons)}
    return out


def build_items(sd) -> dict:
    items = sd.all_tables()[8]
    out = {}
    for iid in (TAR, COAL_TAR, BLOODY_TAR, EPIC_TAR, RARE_TAR, CRYPT_HEALTH, MARCH_SPEEDUP, 2) + KEY_ITEMS:
        r = items.get(iid)
        if isinstance(r, list) and len(r) > 5:
            out[iid] = {"name": sd.vector_text(r[3]), "icon": sd.text(r[5])}
    return out


def build_gear(sd) -> dict:
    pieces = {}
    for tid, r in sd.all_tables()[11].items():
        if not isinstance(tid, int) or not isinstance(r, list) or len(r) < 6 or r[1] not in GEAR_KINDS:
            continue
        pieces[tid] = {"name": sd.vector_text(r[3]) or str(tid), "kind": GEAR_KINDS[r[1]],
                       "tier": r[5] if isinstance(r[5], int) else 0, "icon": sd.text(r[2])}
    arts = {}
    for k, r in sd.all_tables()[110].items():
        m = re.match(r"\[(\d+)\]$", str(k))
        if not m or not isinstance(r, list) or len(r) < 9:
            continue
        icon = re.search(r'"icon":"(\w+)"', sd.text(r[7]))
        arts[int(m.group(1))] = {"name": sd.vector_text(r[8]) or str(k), "icon": icon.group(1) if icon else ""}
    return {"pieces": pieces, "artifacts": arts}


def build(sd) -> dict:
    return {"format": FORMAT, "version": sd.hashes["no_duplicates"], "crypts": build_crypts(sd),
            "captains": build_captains(sd), "items": build_items(sd), "gear": build_gear(sd)}


def _ints(d: dict) -> dict:
    return {int(k): v for k, v in d.items()}


def load(locale: str = "pt_BR", refresh: bool = False) -> dict:
    """Catálogo da versão atual do jogo (gera e guarda se preciso). Chaves numéricas viram int."""
    from .static import StaticData
    sd = StaticData(locale)
    path = os.path.join(DATA_DIR, f"catalog_{sd.hashes['no_duplicates'][:16]}_{sd.locale}.json")
    raw = None
    if os.path.exists(path) and not refresh:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            raw = None
    if not raw or raw.get("format") != FORMAT:
        raw = json.loads(json.dumps(build(sd), ensure_ascii=False))
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False)
    for k in ("crypts", "captains", "items"):
        raw[k] = _ints(raw[k])
    for c in raw["crypts"].values():
        c["key"] = _ints(c.get("key") or {})
    raw["gear"]["pieces"] = _ints(raw["gear"]["pieces"])
    raw["gear"]["artifacts"] = _ints(raw["gear"]["artifacts"])
    return raw


# ---------------------------------------------------------------- consultas
def levels(cat: dict, kind: str) -> list[int]:
    return sorted({c["level"] for c in cat["crypts"].values() if c["kind"] == kind and c["level"]})


def groups(cat: dict, kind: str, level: int) -> dict[str, list[int]]:
    """Os tipos de uma família e nível agrupados pela imagem: {ícone: [tipos]}.
    O jogo tem tipos diferentes com a mesma cara (ex. variantes de evento)."""
    out: dict[str, list[int]] = {}
    for tid, c in sorted(cat["crypts"].items()):
        if c["kind"] == kind and c["level"] == level:
            out.setdefault(c["icon"] or c["visual"] or str(tid), []).append(tid)
    return out
