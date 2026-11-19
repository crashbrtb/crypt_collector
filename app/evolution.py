"""
Evolução de materiais, gemas e encantamentos pela rede (rota 1008).

Captura de 18/11/2026: o objeto é `[item, 0]`; a resposta é
`[[{item: 4}, {}, 1], [{próximo: 1}, ...], ...]`: gasta 4 do nível e devolve 1 do nível seguinte.
Às vezes vem um bônus (`{item: 1, próximo: 1}`), que devolve 1 dos 4 gastos (~14% das vezes).
Não gasta mais nada. O "evoluir tudo" do jogo é premium: aqui é uma chamada por evolução.

Cadeias (tabela 8 de itens): `r[1]` categoria (7 materiais, 8 gemas, 9 encantamentos),
`r[3]` nome, `r[10]` nível (1..8 na tela do jogo). Uma cadeia = mesma categoria e mesmo nome,
um item por nível; o passo entre os ids varia de família para família.
"""
from __future__ import annotations

import json
import os
import threading
import time
import unicodedata

from .gamelink import GameError, GameLink, LinkDown
from .paths import DATA_DIR

R_EVOLVE = 1008
COST = 4
CATEGORIES = {"materiais": 7, "gemas": 8, "encantamentos": 9}
TOP_LEVEL = 8


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def build_chains(sd) -> dict:
    """{categoria: {nome: {"pt", "en", "ids": [id do nível 1..8]}}} (só cadeias completas e sem ambiguidade)."""
    items = sd.all_tables()[8]
    en = sd.en_translations
    raw: dict = {}
    for iid, r in items.items():
        if not (isinstance(iid, int) and isinstance(r, list) and len(r) > 10):
            continue
        if r[1] not in CATEGORIES.values() or not isinstance(r[10], int) or not 1 <= r[10] <= TOP_LEVEL:
            continue
        pt = sd.vector_text(r[3])
        if not pt:
            continue
        key = (r[1], pt)
        c = raw.setdefault(key, {"pt": pt, "en": en.get(sd.vector_key(r[3]), pt), "tiers": {}})
        c["tiers"].setdefault(r[10], []).append(iid)
    out: dict = {str(cat): {} for cat in CATEGORIES.values()}
    for (cat, pt), c in raw.items():
        tiers = c["tiers"]
        if all(len(tiers.get(t, [])) == 1 for t in range(1, TOP_LEVEL + 1)):
            out[str(cat)][pt] = {"pt": pt, "en": c["en"],
                                 "ids": [tiers[t][0] for t in range(1, TOP_LEVEL + 1)]}
    return out


def load_chains(locale: str = "pt_BR") -> dict:
    from .static import StaticData
    sd = StaticData(locale)
    path = os.path.join(DATA_DIR, f"evolution_{sd.hashes['no_duplicates'][:16]}_{sd.locale}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    chains = build_chains(sd)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(chains, fh, ensure_ascii=False)
    return chains


def find(chains: dict, category: str, names: list[str]) -> list[dict]:
    """As cadeias da categoria cujo nome (português ou inglês) contém cada texto pedido."""
    pool = chains[str(CATEGORIES[category])].values()
    out = []
    for want in names:
        w = _norm(want.strip())
        hits = [c for c in pool if w == _norm(c["pt"]) or w == _norm(c["en"])] or \
               [c for c in pool if w in _norm(c["pt"]) or w in _norm(c["en"])]
        if len(hits) != 1:
            opts = ", ".join(sorted(c["pt"] for c in hits)[:8])
            raise ValueError(f"'{want}': {'nenhum item' if not hits else 'mais de um: ' + opts}")
        out.append(hits[0])
    return out


def guaranteed(stock: list[int], level: int) -> int:
    """Quantos itens do nível (1..8) existem depois de evoluir tudo abaixo, sem contar bônus."""
    s = stock[:]
    for t in range(level - 1):
        s[t + 1] += s[t] // COST
        s[t] %= COST
    return s[level - 1]


class Evolver:
    """Evolui cadeias até ter `quantity` itens no nível pedido. Várias cadeias rodam em paralelo."""

    def __init__(self, link: GameLink, res: dict, log=print, pause: float = 0.15, cancel=None):
        self.link, self.res, self.log, self.pause = link, res, log, pause
        self.cancel = cancel
        self.lock = threading.Lock()
        self.stats: dict = {}

    def stock(self, chain) -> list[int]:
        return [self.res.get(i, 0) for i in chain["ids"]]

    def _evolve(self, chain, t: int):
        """Uma evolução do nível t+1 para t+2 (t é o índice 0..6)."""
        if self.cancel is not None:
            self.cancel.check()
        for attempt in range(3):
            try:
                f = self.link.call(R_EVOLVE, [chain["ids"][t], 0])[0]
                break
            except LinkDown:
                if attempt == 2:
                    raise
                time.sleep(5)
        spent, gained = f.objects[0][0][0], f.objects[0][1][0]
        with self.lock:
            for k, v in spent.items():
                self.res[int(k)] = self.res.get(int(k), 0) - v
            for k, v in gained.items():
                self.res[int(k)] = self.res.get(int(k), 0) + v
            st = self.stats.setdefault(chain["pt"], [0, 0])
            st[0] += 1
            st[1] += len(gained) > 1
        time.sleep(self.pause)

    def _make(self, chain, t: int):
        """Mais 1 item no índice t, gastando só o necessário (de cima para baixo)."""
        if t == 0:
            raise GameError("faltou material do nível 1")
        while self.res.get(chain["ids"][t - 1], 0) < COST:
            self._make(chain, t - 1)
        self._evolve(chain, t - 1)

    def _cascade(self, chain, top: int, quantity: int) -> bool:
        """Evolui tudo de baixo para cima até ter `quantity` no topo (conta com a sorte dos bônus)."""
        while self.stock(chain)[top] < quantity:
            moved = False
            for t in range(top):
                while self.stock(chain)[t] >= COST and self.stock(chain)[top] < quantity:
                    self._evolve(chain, t)
                    moved = True
            if not moved:
                return False
        return True

    def run_one(self, chain, level: int, quantity: int | None, gamble: bool) -> str:
        """quantity None = o máximo possível. gamble = tentar além do garantido, com os bônus."""
        top = level - 1
        start = self.stock(chain)[top]
        goal = guaranteed(self.stock(chain), level) if quantity is None else quantity
        # 1) o que o estoque garante: gasta só o necessário, de cima para baixo
        while self.stock(chain)[top] < goal and guaranteed(self.stock(chain), level) > self.stock(chain)[top]:
            self._make(chain, top)
        # 2) o resto, só se pedido: tudo de baixo para cima, contando com os bônus
        if gamble:
            self._cascade(chain, top, 10 ** 9 if quantity is None else quantity)
        have = self.stock(chain)[top]
        n, b = self.stats.get(chain["pt"], [0, 0])
        return f"{chain['pt']}: {have} no nível {level} (+{have - start}) · {n} evoluções, {b} bônus"

    def run(self, chains: list[dict], level: int, quantity: int | None, gamble: bool = False) -> list[str]:
        results: dict = {}

        def work(c):
            try:
                results[c["pt"]] = self.run_one(c, level, quantity, gamble)
            except Exception as e:  # noqa: BLE001
                results[c["pt"]] = f"{c['pt']}: parou ({e})"
            self.log(results[c["pt"]])

        threads = [threading.Thread(target=work, args=(c,), daemon=True) for c in chains]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        return [results[c["pt"]] for c in chains]
