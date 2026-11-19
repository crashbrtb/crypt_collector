"""Evolução de materiais, gemas e encantamentos pela rede (ver app/evolution.py).

Ver o estoque (níveis 1..8) e quanto o estoque garante no nível pedido:
    python evoluir.py gemas --listar
    python evoluir.py encantamentos --listar --nivel 8

Evoluir (vários itens rodam em paralelo; nomes em português ou inglês, parte do nome serve):
    python evoluir.py materiais "Pena da harpia" "Old Shell" --nivel 8 --quantidade 3
    python evoluir.py gemas Ônix Jade --quantidade max
    python evoluir.py encantamentos "Cientista" --quantidade 1 --tentar

  --quantidade N | max   itens no nível final (max = o que o estoque garante)
  --tentar               se o estoque não garante, evolui tudo de baixo para cima contando com os bônus
  --porta 9222           porta CDP do Chrome com o jogo
"""
import argparse
import sys

from app.evolution import CATEGORIES, Evolver, find, guaranteed, load_chains
from app.game import Game
from app.gamelink import GameLink


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Evolução de materiais, gemas e encantamentos")
    ap.add_argument("categoria", choices=list(CATEGORIES))
    ap.add_argument("itens", nargs="*")
    ap.add_argument("--nivel", type=int, default=8)
    ap.add_argument("--quantidade", default="1")
    ap.add_argument("--tentar", action="store_true")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--porta", type=int, default=9222)
    a = ap.parse_args()
    if not 2 <= a.nivel <= 8:
        ap.error("--nivel vai de 2 a 8")

    chains = load_chains()
    link = GameLink(a.porta)
    link.start()
    try:
        res = Game(link).state()["res"]
        if a.listar or not a.itens:
            pool = find(chains, a.categoria, a.itens) if a.itens else \
                list(chains[str(CATEGORIES[a.categoria])].values())
            pool.sort(key=lambda c: c["pt"])
            print(f"{'item':32s} {'níveis 1 → 8':>48s}   garante no nível {a.nivel}")
            for c in pool:
                s = [res.get(i, 0) for i in c["ids"]]
                print(f"{c['pt'][:32]:32s} {' '.join(f'{x:>5}' for x in s)}   {guaranteed(s, a.nivel)}")
            return 0
        targets = find(chains, a.categoria, a.itens)
        qty = None if a.quantidade.lower() == "max" else int(a.quantidade)
        for c in targets:
            s = [res.get(i, 0) for i in c["ids"]]
            print(f"{c['pt']} antes: {s} (garante {guaranteed(s, a.nivel)} no nível {a.nivel})", flush=True)
        ev = Evolver(link, res, log=lambda t: print(t, flush=True))
        ev.run(targets, a.nivel, qty, gamble=a.tentar)
        check = Game(link).state()["res"]
        print("\nconferido no jogo:")
        for c in targets:
            print(f"  {c['pt']}: {[check.get(i, 0) for i in c['ids']]}")
        return 0
    finally:
        link.stop()


if __name__ == "__main__":
    sys.exit(main())
