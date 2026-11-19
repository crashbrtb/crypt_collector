"""
Armaduras e artefato de cada capitão (porte do aa_gear do Autoattack, só capitães).

Cada capitão tem 3 espaços de armadura (posições 4, 5 e 6 da tela de equipamento; qualquer
peça, pode repetir o tipo) e 1 espaço de artefato.

Na cidade (rota 601): rec[10] = peças [id, tipo, [cidade], 1000, raridade, durabilidade, ...] e
rec[9] c[12] = o que cada capitão veste [capitão, espaço, id_da_peça, 100]; o espaço é global
(16 por capitão): posição = (espaço - 1) % 16 + 1.

Rotas (captura do Autoattack de 14/11/2026):
  910 [capitão, posição]            tira a peça
  901 [capitão, posição, id_peça]   veste a peça
  61002 [[capitão, 1], [artefato]]  põe o artefato no capitão; responde parte do mapa
                                    {"[artefato]": [capitão, 1], ...}

Equipamento salvo de um capitão: {"gear": [[id_da_peça, tipo] | None] * 3, "artifact": id | None}.
"""
from __future__ import annotations

import re

from .gamelink import GameError

POSITIONS = [4, 5, 6]


def parse_artifact_map(objects) -> dict[int, list]:
    """O primeiro dicionário {"[13]": [3, 1], ...} da resposta da 61002."""
    stack = [objects]
    while stack:
        x = stack.pop(0)
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                if isinstance(k, (list, tuple)) and k:
                    k = k[0]
                m = re.search(r"\d+", str(k))
                if m and isinstance(v, list):
                    out[int(m.group())] = list(v)
            return out
        if isinstance(x, (list, tuple)):
            stack.extend(x)
    return {}


def piece_name(cat: dict, ptype) -> str:
    p = cat["gear"]["pieces"].get(ptype)
    return f"{p['name']} (nv {p['tier']})" if p else f"peça {ptype}"


def from_game(st: dict, captain: int) -> list:
    """O que o capitão veste agora no jogo, no formato salvo."""
    have = (st["captains"].get(captain) or {}).get("gear", {})
    items = st["items"]
    out = []
    for pos in POSITIONS:
        iid = have.get(pos)
        out.append([iid, items[iid]["type"]] if iid and iid in items else None)
    return out


def substitute(st: dict, cat: dict, ptype: int, taken: set) -> tuple[int, int] | None:
    """Outra peça igual (mesmo tipo) não quebrada e fora de quem vai explorar."""
    cands = [(-it["dur"], iid) for iid, it in st["items"].items()
             if it["type"] == ptype and iid not in taken and it["dur"] > 0]
    return (min(cands)[1], ptype) if cands else None


def apply(game, cat: dict, st: dict, plan: dict[int, dict], log, cap_name, art_map: dict) -> int:
    """Veste no jogo as armaduras e os artefatos de `plan` {capitão: equipamento salvo}.

    Só mexe nos espaços com peça escolhida. Uma peça que está com outro capitão é tirada dele
    antes. Peça que sumiu ou quebrou (durabilidade 0) e não pôde ser reparada é trocada por
    outra do mesmo tipo, também no equipamento salvo. Devolve quantas trocas fez."""
    items = st["items"]
    have = {c: dict(v.get("gear", {})) for c, v in st["captains"].items()}
    worn = {iid: (c, pos) for c, m in have.items() for pos, iid in m.items()}
    taken = {w[0] for p in plan.values() for w in (p.get("gear") or []) if w}
    changed = 0
    for cid, saved in plan.items():
        want = saved.setdefault("gear", [None, None, None])
        mine = have.setdefault(cid, {})
        for i, pos in enumerate(POSITIONS):
            w = want[i] if i < len(want) else None
            if not w:
                continue
            iid, ptype = int(w[0]), int(w[1])
            it = items.get(iid)
            if it is not None and it["dur"] <= 0:
                log(f"{cap_name(cid)}: {piece_name(cat, ptype)} quebrada; reparando")
                try:
                    game.repair(iid)
                    it["dur"] = 1
                except GameError as e:
                    log(f"⚠ reparo recusado: {e}")
            if it is None or it["dur"] <= 0:
                sub = substitute(st, cat, ptype, taken - {iid})
                if not sub:
                    raise GameError(f"{cap_name(cid)}: {piece_name(cat, ptype)} não está disponível "
                                    "e não há outra igual")
                log(f"⚠ {cap_name(cid)}: {piece_name(cat, ptype)} trocada por outra igual")
                taken.discard(iid)
                taken.add(sub[0])
                want[i] = [sub[0], sub[1]]
                iid = sub[0]
            if mine.get(pos) == iid:
                continue
            if iid in worn:
                oc, op = worn.pop(iid)
                game.unequip(oc, op)
                have.get(oc, {}).pop(op, None)
            if mine.get(pos):
                game.unequip(cid, pos)
                worn.pop(mine.pop(pos), None)
            game.equip(cid, pos, iid)
            mine[pos] = iid
            worn[iid] = (cid, pos)
            changed += 1
            log(f"{cap_name(cid)} posição {pos}: {piece_name(cat, ptype)}")
    for cid, saved in plan.items():
        art = saved.get("artifact")
        if not art or list(art_map.get(int(art)) or []) == [cid, 1]:
            continue
        name = cat["gear"]["artifacts"].get(int(art), {}).get("name", f"artefato {art}")
        try:
            frames = game.set_artifact(cid, int(art))
        except GameError as e:
            log(f"⚠ não consegui pôr {name} em {cap_name(cid)}: {e}")
            continue
        new = parse_artifact_map([f.objects for f in frames])
        for a, v in list(art_map.items()):
            if list(v) == [cid, 1] and a != int(art):
                del art_map[a]
        art_map.update(new)
        art_map[int(art)] = [cid, 1]
        changed += 1
        log(f"{cap_name(cid)}: artefato {name}")
    return changed


def conflicts(plan: dict[int, dict]) -> list[str]:
    """Peças ou artefatos escolhidos para mais de um capitão."""
    out, pieces, arts = [], {}, {}
    for cid, saved in plan.items():
        for w in saved.get("gear") or []:
            if w:
                if w[0] in pieces and pieces[w[0]] != cid:
                    out.append(f"piece:{w[0]}")
                pieces[w[0]] = cid
        art = saved.get("artifact")
        if art:
            if art in arts and arts[art] != cid:
                out.append(f"artifact:{art}")
            arts[art] = cid
    return out
