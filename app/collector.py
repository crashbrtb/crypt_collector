"""
O laço do coletor: até 3 capitães explorando criptas ao mesmo tempo, tudo pela rede.

Cada "faixa" é um capitão com uma família e um nível de cripta (ex. Épica 35) e um ou mais
tipos desse nível. A cada volta do laço, para cada faixa:

  capitão em casa e faltando criptas -> escolhe a cripta livre mais perto da cidade,
      confere que ela ainda existe, não vence antes da marcha chegar e não tem marcha de
      ninguém indo para ela (bloco do mapa), reserva, abre (rara, com a chave), manda o
      capitão com o alcatrão e acelera a marcha;
  capitão fora numa marcha nossa -> acompanha: acelera a volta se der e, quando ele chega,
      confere se a cripta acabou e aprende quanto alcatrão o capitão gasta.

Duas faixas nunca escolhem a mesma cripta (reserva) e uma cripta com marcha de outro
jogador a caminho fica de fora.

Vigia: se a aba do jogo parar de mandar pedidos (o erro do Unity que trava o jogo) ou
parar de responder, a página é recarregada (F5); se o jogo não voltar, o Chrome é fechado
e aberto de novo. As marchas continuam no servidor e o laço retoma de onde estava.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from . import catalog as catalog_mod
from . import gear as gear_mod
from .cancel import Cancelled, CancelToken
from .game import Game
from .gamelink import GameError, GameLink, LinkDown
from .i18n import tr
from .logger import logger

# Dano por alcatrão quando o capitão ainda não foi medido: o que o próprio jogo usou na captura
# (Carter: 850.000 / 44.800 ≈ 19 com Alcatrão raro; 1.450.000 / 53.200 ≈ 27,3 com o épico).
# O que sobra volta para a cidade com o capitão, então errar para mais é seguro.
DEFAULT_DAMAGE_PER_TAR = {catalog_mod.TAR: 19.0, catalog_mod.RARE_TAR: 19.0, catalog_mod.EPIC_TAR: 27.0,
                          catalog_mod.BLOODY_TAR: 19.0, catalog_mod.COAL_TAR: 19.0}


class CollectorError(RuntimeError):
    pass


class OutOfSupply(GameError):
    """Acabou o alcatrão ou a chave da faixa: ela para ou passa a ajudar outra faixa."""


@dataclass
class Lane:
    index: int
    captain: int
    kind: str
    level: int
    types: set
    quantity: int
    equip: dict
    done: int = 0
    finished: bool = False
    geared: bool = False
    march: int | None = None
    crypt: dict | None = None
    tar_item: int | None = None
    tar_sent: int = 0
    tar_left: int | None = None
    speedups: int = 0
    sent_at: float = 0.0
    checked_at: float = 0.0
    status: str = ""
    errors: int = 0
    fallback: int | None = None          # faixa a ajudar quando acabar o alcatrão/chave
    helping: "Lane | None" = None
    stats: dict = field(default_factory=lambda: {"tar": 0, "speedups": 0, "keys": 0})

    @property
    def label(self) -> str:
        return f"[{self.index + 1}]"


class Collector:
    def __init__(self, settings, cat: dict, browser, cancel: CancelToken, on_status=None):
        self.settings = settings
        self.cat = cat
        self.browser = browser
        self.cancel = cancel
        self.on_status = on_status or (lambda lanes: None)
        self.run_cfg = settings.section("run")
        self.link: GameLink | None = None
        self.game: Game | None = None
        self.lanes: list[Lane] = []
        self.reserved: dict[int, int] = {}       # cripta -> faixa
        self.skip: dict[int, float] = {}         # cripta -> até quando fica de fora
        self.found: list[dict] = []
        self.search_at = 0.0
        self.recoveries = 0
        self.last_recovery = 0.0

    # ------------------------------------------------------------------ util
    def log(self, text: str, level: str = "info"):
        getattr(logger, level)(text)

    def cap_name(self, cid) -> str:
        return (self.cat["captains"].get(int(cid)) or {}).get("name", f"#{cid}")

    def crypt_name(self, ctype) -> str:
        c = self.cat["crypts"].get(ctype) or {}
        return f"{tr('kind.' + c.get('kind', 'common'))} {c.get('level', '?')} ({c.get('icon') or ctype})"

    def cfg(self, key, default=None):
        v = self.run_cfg.get(key)
        return default if v is None else v

    def _status(self):
        try:
            self.on_status([{"index": ln.index, "captain": ln.captain, "done": ln.done, "quantity": ln.quantity,
                             "status": ln.status, "finished": ln.finished} for ln in self.lanes])
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ início
    def build_lanes(self) -> list[Lane]:
        lanes = []
        used_caps = set()
        for i, lc in enumerate(self.settings.data.get("lanes") or []):
            if not lc.get("enabled") or not lc.get("captain"):
                continue
            cap = int(lc["captain"])
            if cap in used_caps:
                raise CollectorError(tr("err.same_captain", name=self.cap_name(cap)))
            used_caps.add(cap)
            groups = catalog_mod.groups(self.cat, lc.get("kind"), int(lc.get("level") or 0))
            types = {t for g in (lc.get("groups") or []) for t in groups.get(g, [])}
            if not types:
                raise CollectorError(tr("err.no_types", lane=i + 1))
            lanes.append(Lane(index=i, captain=cap, kind=lc["kind"], level=int(lc["level"]), types=types,
                              quantity=int(lc.get("quantity") or 0),
                              equip={"gear": list(lc.get("gear") or [None, None, None]),
                                     "artifact": lc.get("artifact")},
                              fallback=lc.get("fallback") if isinstance(lc.get("fallback"), int) else None))
        if not lanes:
            raise CollectorError(tr("err.no_lanes"))
        plan = {ln.captain: ln.equip for ln in lanes}
        if gear_mod.conflicts(plan):
            raise CollectorError(tr("err.gear_conflict"))
        return lanes

    def connect(self, wait: float = 30.0):
        if self.link:
            try:
                self.link.stop()
            except Exception:  # noqa: BLE001
                pass
        port = int(self.settings.get("browser", "cdp_port"))
        self.link = GameLink(port, (self.settings.get("browser", "url_filter") or "totalbattle").lower())
        self.link.start(wait=wait)
        city = self.game.city if self.game else None
        offset = self.game.clock_offset if self.game else 0.0
        self.game = Game(self.link)
        self.game.city, self.game.clock_offset = city, offset
        if not self.game.city:
            self.game.find_city()

    def run(self):
        self.lanes = self.build_lanes()
        self.log(tr("log.connecting"))
        self.with_recovery(self.connect)
        st = self.with_recovery(lambda: self.game.state())
        for ln in self.lanes:
            if ln.captain not in st["captains"]:
                raise CollectorError(tr("err.captain_missing", name=self.cap_name(ln.captain)))
            self.log(f"{ln.label} {self.cap_name(ln.captain)}: {tr('kind.' + ln.kind)} {ln.level} · "
                     f"{len(ln.types)} {tr('log.types')} · {tr('log.quantity')} {ln.quantity or '∞'}")
            where = st["captains"][ln.captain]["where"]
            if not st["captains"][ln.captain]["home"] and where:
                ln.march, ln.sent_at = where, time.time()
                ln.status = tr("status.away")
        try:
            while not all(ln.finished and not ln.march for ln in self.lanes):
                try:
                    self.loop_once()
                except LinkDown as e:
                    self.recover(str(e))
        finally:
            self.settings.save()
        self.summary()

    def loop_once(self):
        self.cancel.check()
        self.watchdog()
        st = self.game.state()
        for ln in self.lanes:
            self.cancel.check()
            try:
                self.step(ln, st)
                ln.errors = 0
            except LinkDown:
                raise
            except GameError as e:
                ln.errors += 1
                self.release(ln)
                self.log(f"{ln.label} {self.cap_name(ln.captain)}: {e}", "warning")
                if ln.errors >= int(self.cfg("max_errors", 5)):
                    ln.finished = True
                    ln.status = tr("status.stopped_errors")
                    self.log(f"{ln.label} {tr('log.lane_stopped')}", "error")
        self._status()
        self.cancel.sleep(float(self.cfg("tick", 2.0)))

    # ------------------------------------------------------------------ faixas
    def step(self, ln: Lane, st: dict):
        cap = st["captains"].get(ln.captain) or {}
        if ln.march:
            if cap.get("home"):
                self.finish_march(ln)
            else:
                self.track(ln)
            return
        if ln.finished:
            return
        if not cap.get("home"):
            ln.status = tr("status.away")
            return
        if ln.helping:
            target = ln.helping
            if target.finished or (target.quantity and target.done >= target.quantity):
                ln.finished = True
                ln.status = tr("status.done")
                self.log(f"{ln.label} {self.cap_name(ln.captain)}: {tr('log.help_done', n=target.index + 1)}")
                return
        elif ln.quantity and ln.done >= ln.quantity:
            ln.finished = True
            ln.status = tr("status.done")
            self.log(f"{ln.label} {self.cap_name(ln.captain)}: {tr('log.lane_done', n=ln.done)}")
            return
        if not 1 <= int(cap.get("slot") or 0) <= 3:
            self.lineup(ln, st)
        if not ln.geared:
            self.apply_gear(ln, st)
        self.dispatch(ln, st)

    def lineup(self, ln: Lane, st: dict):
        """Põe o capitão da faixa na lista de 3 capitães da marcha: numa posição vazia ou no lugar
        de um capitão que está em casa e não é de nenhuma faixa."""
        ours = {x.captain for x in self.lanes}
        slots = {c["slot"]: cid for cid, c in st["captains"].items() if 1 <= int(c.get("slot") or 0) <= 3}
        free = [p for p in (1, 2, 3) if p not in slots]
        idle = [p for p, cid in slots.items() if cid not in ours and st["captains"][cid]["home"]]
        if not free and not idle:
            raise GameError(tr("log.no_slot"))
        pos = (free or idle)[0]
        out = slots.get(pos)
        self.game.put_captain(pos, ln.captain)
        st.update(self.game.state())
        if st["captains"].get(ln.captain, {}).get("slot") != pos:
            raise GameError(tr("log.no_slot"))
        self.log(f"{ln.label} {tr('log.slot', name=self.cap_name(ln.captain), pos=pos)}"
                 + (f" ({tr('log.slot_out', name=self.cap_name(out))})" if out else ""))

    def apply_gear(self, ln: Lane, st: dict):
        ln.geared = True
        if not any(ln.equip.get("gear") or []) and not ln.equip.get("artifact"):
            return
        art_map = {int(k): v for k, v in (self.settings.data.get("artifact_map") or {}).items()}
        n = gear_mod.apply(self.game, self.cat, st, {ln.captain: ln.equip}, self.log, self.cap_name, art_map)
        self.settings.data["artifact_map"] = {str(k): v for k, v in art_map.items()}
        # a troca por peça igual também fica no equipamento salvo
        lanes_cfg = self.settings.data.get("lanes") or []
        if ln.index < len(lanes_cfg):
            lanes_cfg[ln.index]["gear"] = ln.equip.get("gear")
        if n:
            self.log(f"{ln.label} {self.cap_name(ln.captain)}: {tr('log.gear_applied', n=n)}")
            st.update(self.game.state())

    def candidates(self, pos, ln: Lane) -> list[dict]:
        now = time.time()
        every = float(self.cfg("search_every", 30))
        mine = [c for c in self.found if c["type"] in ln.types]
        if now - self.search_at > every or (not mine and now - self.search_at > 8):
            types = set().union(*(x.types for x in self.lanes if not x.finished)) or ln.types
            radius = int(self.cfg("search_radius", 150))
            if self.cfg("search_mode", "spyglass") == "scan":
                self.found = self.game.scan(pos, types, min(radius, 200))
            else:
                self.found = self.game.search(pos, types, radius)
            self.search_at = now
            mine = [c for c in self.found if c["type"] in ln.types]
        for k in [k for k, until in self.skip.items() if until < now]:
            del self.skip[k]
        return [c for c in mine if c["id"] not in self.reserved and c["id"] not in self.skip]

    def dispatch(self, ln: Lane, st: dict):
        cands = self.candidates(st["pos"], ln)
        if not cands:
            ln.status = tr("status.no_crypt")
            return
        chosen = info = None
        check = cands[: int(self.cfg("max_checks", 8))]
        infos = self.game.crypt_info([c["id"] for c in check])
        min_left = float(self.cfg("min_time_left", 180))
        for c in check:
            i = infos.get(c["id"])
            if not i or i["health"] <= 0:
                self.forget(c["id"])
                continue
            if i["ends"] - self.game.now() < min_left:
                self.skip[c["id"]] = time.time() + 3600
                continue
            if self.cfg("check_marches", True):
                others = self.game.marches_to(c["id"], c["pos"])
                if others:
                    self.log(f"{ln.label} {tr('log.someone_going', pos=self.fmt_pos(c['pos']))}")
                    self.skip[c["id"]] = time.time() + 300
                    continue
            chosen, info = c, i
            break
        if not chosen:
            ln.status = tr("status.no_crypt")
            return
        cdef = self.cat["crypts"].get(chosen["type"]) or {}
        self.reserved[chosen["id"]] = ln.index
        try:
            tar = self.tar_for(ln, cdef, info, st)      # antes da chave: sem alcatrão, a chave não é gasta
            if info["closed"]:
                self.open_rare(ln, chosen, cdef, st)
            march = self.game.explore(chosen, ln.captain, tar)
        except OutOfSupply as e:
            self.reserved.pop(chosen["id"], None)
            self.out_of_supply(ln, str(e))
            return
        except GameError:
            self.reserved.pop(chosen["id"], None)
            self.skip[chosen["id"]] = time.time() + 120
            raise
        ln.march, ln.sent_at, ln.speedups, ln.tar_left = march, time.time(), 0, None
        ln.crypt = dict(chosen, health=info["health"], level=cdef.get("level"), kind=cdef.get("kind"))
        if tar:
            ln.tar_item, ln.tar_sent = next(iter(tar.items()))
            st["res"][ln.tar_item] = st["res"].get(ln.tar_item, 0) - ln.tar_sent
        else:
            ln.tar_item, ln.tar_sent = None, 0
        ln.status = tr("status.marching", pos=self.fmt_pos(chosen["pos"]))
        tar_txt = f" · {ln.tar_sent:,} {self.item_name(ln.tar_item)}" if ln.tar_item else ""
        self.log(f"{ln.label} {self.cap_name(ln.captain)} → {self.crypt_name(chosen['type'])} "
                 f"{self.fmt_pos(chosen['pos'])} ({chosen['dist']:.0f}){tar_txt}")
        self.speed(ln, st)

    def open_rare(self, ln: Lane, crypt: dict, cdef: dict, st: dict):
        for item, qty in (cdef.get("key") or {}).items():
            if st["res"].get(item, 0) < qty:
                raise OutOfSupply(tr("log.no_key", name=self.item_name(item)))
        self.game.open_crypt(crypt["id"])
        for item, qty in (cdef.get("key") or {}).items():
            st["res"][item] = st["res"].get(item, 0) - qty
        ln.stats["keys"] += 1
        self.log(f"{ln.label} {tr('log.opened')}")

    def tar_for(self, ln: Lane, cdef: dict, info: dict, st: dict) -> dict:
        item = (self.settings.data.get("tar_items") or {}).get(cdef.get("kind")) or catalog_mod.TAR_BY_KIND.get(cdef.get("kind"))
        if not item:
            return {}
        item = int(item)
        health = info["health"] or cdef.get("health") or 0
        learned = (self.settings.data.get("tar_learned") or {}).get(f"{ln.captain}:{item}")
        if learned:
            dpt = float(learned) / float(self.cfg("tar_margin", 1.25))
        else:
            dpt = DEFAULT_DAMAGE_PER_TAR.get(item, 19.0)
        qty = int(math.ceil(health / max(dpt, 1.0) / 100.0) * 100)
        have = st["res"].get(item, 0)
        if have < qty:
            raise OutOfSupply(tr("log.no_tar", name=self.item_name(item), need=f"{qty:,}", have=f"{have:,}"))
        return {item: qty}

    def out_of_supply(self, ln: Lane, why: str):
        """Sem alcatrão/chave: passa a fazer as criptas da faixa escolhida (uma vez), senão para."""
        target = next((x for x in self.lanes if x.index == ln.fallback and x is not ln), None)
        if ln.helping is None and target and not target.finished:
            ln.helping = target
            ln.kind, ln.level, ln.types = target.kind, target.level, set(target.types)
            ln.status = tr("status.helping", n=target.index + 1)
            self.log(f"{ln.label} {self.cap_name(ln.captain)}: {why} → "
                     f"{tr('log.helping', n=target.index + 1, name=self.cap_name(target.captain), kind=tr('kind.' + target.kind), level=target.level)}",
                     "warning")
            return
        ln.finished = True
        ln.status = tr("status.no_supply")
        self.log(f"{ln.label} {self.cap_name(ln.captain)}: {why}; {tr('log.lane_no_supply')}", "warning")

    def speed(self, ln: Lane, st: dict | None = None):
        if not self.cfg("speedup", True):
            return
        item = int(self.cfg("speedup_item", catalog_mod.MARCH_SPEEDUP))
        limit = int(self.cfg("speedups_per_march", 5))
        while ln.speedups < limit:
            if st is not None and st["res"].get(item, 0) <= 0:
                self.log(f"{ln.label} {tr('log.no_speedups')}", "warning")
                return
            if not self.game.speedup(ln.march, item):
                return
            ln.speedups += 1
            ln.stats["speedups"] += 1
            if st is not None:
                st["res"][item] = st["res"].get(item, 0) - 1
            self.cancel.sleep(0.4)

    def track(self, ln: Lane):
        now = time.time()
        if now - ln.checked_at < float(self.cfg("track_every", 4)):
            return
        ln.checked_at = now
        m = self.game.march(ln.march)
        if not m:
            return
        if m["returning"] and ln.tar_item:
            ln.tar_left = int(m["carried"].get(ln.tar_item, 0))
        left = (m["end"] or 0) - self.game.now()
        if left > float(self.cfg("speedup_min_left", 25)) and ln.speedups < int(self.cfg("speedups_per_march", 5)):
            self.speed(ln)
        timeout = float(self.cfg("march_timeout", 1800))
        if now - ln.sent_at > timeout and ln.status != tr("status.slow"):
            ln.status = tr("status.slow")
            self.log(f"{ln.label} {tr('log.slow', s=int(now - ln.sent_at))}", "warning")

    def finish_march(self, ln: Lane):
        crypt = ln.crypt
        ln.status = ""
        if crypt:
            info = self.game.crypt_info([crypt["id"]]).get(crypt["id"])
            used = None if ln.tar_left is None else max(0, ln.tar_sent - ln.tar_left)
            if used is not None:
                ln.stats["tar"] += used
            gone = info is None or info["health"] <= 0
            # gasto 0 só é certeza de "não foi nossa" se a volta foi vista; sem ela, cripta sumida
            # depois da nossa chegada conta como feita
            if gone and used != 0:
                ln.done += 1
                owner = ln.helping or ln                # ajudando: conta na faixa ajudada
                if ln.helping:
                    owner.done += 1
                self.learn(ln, crypt["health"], used)
                self.log(f"{ln.label} {self.cap_name(ln.captain)}: {tr('log.crypt_done')} "
                         + (f"[{owner.index + 1}] " if ln.helping else "")
                         + f"({owner.done}/{owner.quantity or '∞'})"
                         + (f" · {used:,} {self.item_name(ln.tar_item)}" if used else ""))
            elif not gone:
                hit = crypt["health"] - info["health"]
                if used:
                    self.learn(ln, hit, used)
                left = f"{info['health']:,}"
                self.log(f"{ln.label} {tr('log.partial', left=left)}", "warning")
            else:
                self.log(f"{ln.label} {tr('log.taken')}", "warning")
            self.forget(crypt["id"])
        ln.march = ln.crypt = None
        ln.tar_item, ln.tar_sent, ln.tar_left = None, 0, None
        self.reserved = {k: v for k, v in self.reserved.items() if v != ln.index}

    def learn(self, ln: Lane, damage: int, used: int | None):
        """Guarda o dano por alcatrão do capitão (média com a medida anterior)."""
        if not used or not ln.tar_item or damage <= 0:
            return
        key = f"{ln.captain}:{ln.tar_item}"
        table = self.settings.data.setdefault("tar_learned", {})
        dpt = damage / used
        old = table.get(key)
        table[key] = round(dpt if not old else (old * 0.6 + dpt * 0.4), 3)

    def release(self, ln: Lane):
        if not ln.march:
            self.reserved = {k: v for k, v in self.reserved.items() if v != ln.index}

    def forget(self, crypt_id: int):
        self.found = [c for c in self.found if c["id"] != crypt_id]
        self.reserved.pop(crypt_id, None)

    # ------------------------------------------------------------- vigia
    def watchdog(self):
        if not self.link or not self.link.alive:
            raise LinkDown(tr("log.tab_lost"))
        quiet = time.time() - self.link.last_game_request
        if quiet > float(self.cfg("freeze_seconds", 90)):
            raise LinkDown(tr("log.frozen", s=int(quiet)))

    def with_recovery(self, fn, *args):
        for _ in range(int(self.cfg("max_recoveries", 10)) + 1):
            self.cancel.check()
            try:
                return fn(*args)
            except LinkDown as e:
                self.recover(str(e))
        raise CollectorError(tr("err.unrecoverable"))

    def recover(self, reason: str):
        """F5; se o jogo não voltar, reinicia o Chrome. Repete até max_recoveries."""
        if time.time() - self.last_recovery > 1800:
            self.recoveries = 0
        self.recoveries += 1
        self.last_recovery = time.time()
        if self.recoveries > int(self.cfg("max_recoveries", 10)):
            raise CollectorError(tr("err.unrecoverable"))
        self.log(tr("log.recovering", reason=reason), "warning")
        self.found, self.search_at = [], 0.0
        steps = (("reload", float(self.cfg("reload_wait", 120))), ("restart", float(self.cfg("restart_wait", 240))))
        for step, wait in steps:
            self.cancel.check()
            try:
                if step == "reload":
                    if not self.browser.reload():
                        continue
                    self.log(tr("log.reloaded"))
                else:
                    self.log(tr("log.restarting"), "warning")
                    self.browser.restart()
                self.cancel.sleep(8)
                self.connect(wait=wait)
                self.log(tr("log.recovered"))
                return True
            except Cancelled:
                raise
            except Exception as e:  # noqa: BLE001
                self.log(tr("log.recover_failed", step=step, err=e), "warning")
        self.log(tr("log.recover_wait"), "warning")
        self.cancel.sleep(60)
        return False

    # ------------------------------------------------------------- textos
    def item_name(self, item) -> str:
        return (self.cat["items"].get(item) or {}).get("name", f"item {item}")

    @staticmethod
    def fmt_pos(p) -> str:
        return f"X:{p[1]} Y:{p[2]}"

    def summary(self):
        for ln in self.lanes:
            self.log(f"{ln.label} {self.cap_name(ln.captain)}: {ln.done} {tr('log.crypts')} · "
                     f"{ln.stats['tar']:,} {tr('log.tar')} · {ln.stats['speedups']} {tr('log.speedups')} · "
                     f"{ln.stats['keys']} {tr('log.keys')}")
