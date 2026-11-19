"""
Leituras e ações de uma cidade pelo protocolo do jogo (ver PROTOCOLO.md).

Tudo aqui é um pedido de rede feito de dentro da aba do jogo (GameLink). Nada é lido
da tela.
"""
from __future__ import annotations

import math
import time

from .catalog import CRYPT_HEALTH
from .gamelink import GameError, GameLink

R_PLAYER = 402
R_OBJECTS = 601
R_SEARCH = 26001        # a luneta
R_MAP_BLOCK = 312       # objetos de um bloco 20x20 do mapa
R_MARCH = 701
R_OPEN_CRYPT = 14004    # abrir cripta rara (gasta a chave)
R_USE_ITEM = 300053     # usar item numa marcha (aceleração)
R_EQUIP, R_UNEQUIP, R_ARTIFACT, R_REPAIR = 901, 910, 61002, 906
R_CAPTAIN_SLOT = 905   # [[[posição, capitão]]]; capitão 0 esvazia (captura do Autoattack de 08/11)

FULL_MASK = 2147483647
CITY_MASK = 66102

MARCH_OBJECT = 1        # tipo de objeto do mapa: marcha
MARCH_GOING, MARCH_RETURNING, MARCH_STAYING = 7, 5, 6   # row[19] do objeto de marcha
EXPLORE_MARCH = 7       # primeiro campo do 701: explorar cripta
EXPLORE_TAIL = 4        # último campo do 701 para cripta (2 no ataque a monstro)

BLOCK = 20
BLOCK_COLUMNS = 50


def block_of(x: int, y: int) -> int:
    return (y // BLOCK) * BLOCK_COLUMNS + x // BLOCK


def distance(a, b) -> float:
    return math.hypot(a[1] - b[1], a[2] - b[2])


def first_id(o):
    """Primeiro [id] (lista de um inteiro grande) dentro de uma estrutura."""
    if isinstance(o, list):
        if len(o) == 1 and isinstance(o[0], int) and o[0] > 10 ** 9:
            return o[0]
        for x in o:
            r = first_id(x)
            if r:
                return r
    return None


class Game:
    def __init__(self, link: GameLink):
        self.link = link
        self.player = link.player_id
        self.city = None
        self.clock_offset = 0.0     # horário do servidor - horário local
        self.pos = None

    def now(self) -> float:
        return time.time() + self.clock_offset

    # ---------------------------------------------------------------- leituras
    def find_city(self) -> int:
        rec = self.link.call(R_PLAYER, [[[self.player]]])[0].objects[0][0][0]
        self.city = rec[16][0]
        return self.city

    def objects(self, ids, mask: int = FULL_MASK) -> dict:
        out = {}
        ids = list(ids)
        for i in range(0, len(ids), 50):
            f = self.link.call(R_OBJECTS, [[[[oid], 0, mask] for oid in ids[i:i + 50]]])[0]
            for rec in (f.objects[0][0] if f.objects and f.objects[0] else []):
                if isinstance(rec, list) and rec and isinstance(rec[0], list) and rec[0]:
                    out[rec[0][0]] = rec
        return out

    def state(self) -> dict:
        """A cidade: posição, recursos, capitães (onde estão e o que vestem) e peças."""
        if not self.city:
            self.find_city()
        rec = self.objects([self.city], CITY_MASK).get(self.city)
        if not rec:
            raise GameError(f"a cidade {self.city} não veio na rota 601")
        res = {int(k): v[1] for k, v in (rec[5] or {}).items() if isinstance(v, list) and len(v) > 1}
        caps = {}
        for c in rec[9] or []:
            if not (isinstance(c, list) and len(c) > 12):
                continue
            where = c[3][0] if isinstance(c[3], list) and c[3] else None
            gear = {(e[1] - 1) % 16 + 1: e[2] for e in (c[12] or [])
                    if isinstance(e, list) and len(e) > 2 and e[2]}
            caps[c[0]] = {"id": c[0], "slot": c[1], "where": where, "home": where == self.city,
                          "level": c[10], "gear": gear}
        items = {it[0]: {"type": it[1], "dur": it[5]} for it in (rec[10] or [])
                 if isinstance(it, list) and len(it) > 6}
        self.pos = rec[1][13]
        return {"pos": rec[1][13], "res": res, "captains": caps, "items": items}

    # ---------------------------------------------------------------- criptas
    def search(self, pos, types, radius: int) -> list[dict]:
        """Luneta: as criptas dos tipos dados num raio da cidade, da mais perto para a mais longe."""
        f = self.link.call(R_SEARCH, [pos, [radius, [[]], [[]], sorted(types), [[True] * 7], True], 0, False])[0]
        rows = f.objects[0][0] if f.objects and f.objects[0] else []
        out = [{"id": r[0][0], "type": r[1], "pos": r[2], "dist": distance(pos, r[2])}
               for r in rows if isinstance(r, list) and len(r) > 2]
        return sorted(out, key=lambda c: c["dist"])

    def blocks(self, block_ids) -> tuple[list[list], list[list]]:
        """Os blocos do mapa pedidos (rota 312, versão 0 = tudo): (objetos, entidades).

        b[4] objetos completos (cidades, marchas: tipo 1, origem r[17], destino r[18], estado r[19]);
        b[5] entidades de 12 campos (criptas, monstros): [[id], tipo, 0, ?, 0, nível, 0, 0, pos, [dono], ?, ?]."""
        objects, entities = [], []
        block_ids = list(block_ids)
        for i in range(0, len(block_ids), 9):
            part = block_ids[i:i + 9]
            for f in self.link.call(R_MAP_BLOCK, [part, [0] * len(part), [], []]):
                for b in (f.objects[0][0] if f.objects and f.objects[0] else []):
                    if not isinstance(b, list):
                        continue
                    if len(b) > 4 and isinstance(b[4], list):
                        objects.extend(r for r in b[4] if isinstance(r, list) and len(r) > 20)
                    if len(b) > 5 and isinstance(b[5], list):
                        entities.extend(r for r in b[5] if isinstance(r, list) and len(r) > 8)
        return objects, entities

    def scan(self, pos, types, radius: int) -> list[dict]:
        """Varredura do mapa: lê os blocos em volta da cidade e separa as criptas dos tipos dados."""
        x0, y0 = pos[1], pos[2]
        ids = sorted({block_of(x, y) for x in range(max(0, x0 - radius), x0 + radius + BLOCK, BLOCK)
                      for y in range(max(0, y0 - radius), y0 + radius + BLOCK, BLOCK)})
        out, seen = [], set()
        for r in self.blocks(ids)[1]:
            oid = r[0][0] if isinstance(r[0], list) and r[0] else None
            if r[1] in types and oid not in seen and isinstance(r[8], list):
                seen.add(oid)
                d = distance(pos, r[8])
                if d <= radius:
                    out.append({"id": oid, "type": r[1], "pos": r[8], "dist": d})
        return sorted(out, key=lambda c: c["dist"])

    def crypt_info(self, ids) -> dict:
        """Estado de cada cripta: saúde, validade, se está fechada (rara) e quantas explorações teve."""
        out = {}
        for oid, rec in self.objects(ids).items():
            h = rec[1]
            try:
                health = (rec[5] or {}).get(CRYPT_HEALTH, [0, 0])[1]
            except (AttributeError, IndexError, TypeError):
                health = 0
            out[oid] = {"type": h[2], "ends": h[4], "pos": h[13], "health": health,
                        "explored": rec[25] if len(rec) > 25 and isinstance(rec[25], int) else 0,
                        "closed": bool(rec[32]) if len(rec) > 32 else False}
        return out

    def marches_to(self, crypt_id: int, pos) -> list[list]:
        """Marchas de qualquer jogador indo para a cripta ou paradas nela (bloco da cripta).
        Uma marcha em movimento aparece no bloco de origem e no de destino (conferido em 18/11)."""
        found = []
        for r in self.blocks([block_of(pos[1], pos[2])])[0]:
            if r[3] != MARCH_OBJECT:
                continue
            target = r[1][0] if isinstance(r[1], list) and r[1] else 0
            going = r[19] == MARCH_GOING and r[18] == pos
            staying = target == crypt_id or (r[19] == MARCH_STAYING and r[17] == pos)
            if going or staying:
                found.append(r)
        return found

    # ---------------------------------------------------------------- ações
    def open_crypt(self, crypt_id: int):
        return self.link.call(R_OPEN_CRYPT, [[crypt_id]])

    def explore(self, crypt: dict, captain: int, tar: dict) -> int:
        """Manda o capitão explorar a cripta. Devolve o id da marcha."""
        req = [EXPLORE_MARCH, 1, 0, 0, [self.city], [self.city], crypt["pos"], None, [captain], crypt["type"],
               None, 0, [], 0, {int(k): int(v) for k, v in tar.items()}, [], EXPLORE_TAIL]
        sent = time.time()
        f = self.link.call(R_MARCH, req)[0]
        march = first_id(f.objects)
        if not march:
            raise GameError(f"a marcha não voltou na resposta do 701: {str(f.objects)[:200]}")
        try:
            header = f.objects[0][0][0][1]
            if isinstance(header[3], int) and header[3] > 10 ** 9:
                self.clock_offset = header[3] - sent
        except (IndexError, TypeError):
            pass
        return march

    def speedup(self, march: int, item: int) -> bool:
        """Usa 1 aceleração na marcha. False quando o jogo não usou (marcha perto do fim)."""
        f = self.link.call(R_USE_ITEM, [[march], [[item, 1]]])[0]
        try:
            return bool(f.objects[0][1])
        except (IndexError, TypeError):
            return False

    def march(self, march: int) -> dict | None:
        """A marcha: origem e destino da perna atual, fim da perna e o que ela carrega. None = acabou.
        Voltando = o destino é a cidade (h[13] origem, h[14] destino; h[12] não distingue: vale 5
        nas duas pernas depois das acelerações, conferido em 18/11)."""
        rec = self.objects([march]).get(march)
        if not rec or not rec[1]:
            return None
        h = rec[1]
        carried = {int(k): v[1] for k, v in (rec[5] or {}).items() if isinstance(v, list) and len(v) > 1}
        return {"origin": h[13], "dest": h[14], "returning": bool(self.pos) and h[14] == self.pos,
                "start": h[15], "end": h[16], "carried": carried}

    def put_captain(self, pos: int, captain: int):
        """Põe o capitão numa das 3 posições da lista de marcha, como o jogo faz: esvazia e coloca.
        Só os capitães dessa lista podem explorar ("hero N not available" fora dela)."""
        self.link.call(R_CAPTAIN_SLOT, [[[pos, 0]]])
        self.link.call(R_CAPTAIN_SLOT, [[[pos, captain]]])

    def equip(self, captain: int, pos: int, item_id: int):
        return self.link.call(R_EQUIP, [captain, pos, item_id])

    def unequip(self, captain: int, pos: int):
        return self.link.call(R_UNEQUIP, [captain, pos])

    def set_artifact(self, captain: int, artifact: int):
        return self.link.call(R_ARTIFACT, [[captain, 1], [artifact]])

    def repair(self, item_id: int):
        return self.link.call(R_REPAIR, [item_id, [self.city]])
