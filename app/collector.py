"""
A execução: abrir a lista de criptas, escolher uma, explorar e acelerar a marcha.

Parte do princípio de que o jogo já está aberto e logado em um Chrome com CDP.
Este módulo não abre navegador nem faz login: se a aba do jogo não for
encontrada, a execução para com uma mensagem dizendo isso.
"""

import os
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .browser import Browser, BrowserError
from .calibration import Calibration
from .cancel import cancellation
from .i18n import tr
from .logger import logger
from .paths import CRYPT_IMAGES_DIR, FALLBACK_CLOSE_IMAGE
from .settings import ANY_MODE, CRYPT_TYPES, Settings
from .vision import WIDE_SCALES, Hit, Region, Vision, changed_fraction, expand, ladder

Point = Tuple[int, int]

# Ícones que só casam com um limiar mais baixo que o geral.
ICON_THRESHOLDS = {"rare/2.png": 0.6}

# As imagens de images/ vieram do cliente instalado em 1920x1080.
BUNDLED_IMAGE_SIZE = (1920, 1080)

# A cada tantas voltas seguidas sem conseguir, a execução recarrega o jogo e
# tenta de novo - ela não para sozinha.
MAX_CONSECUTIVE_FAILURES = 5
FAILURE_PAUSE = 30.0            # entre duas tentativas de reabrir o jogo
GAME_LOAD_WAIT = 45.0           # do carregamento da página até o mapa aparecer

LIST_END_CHANGE = 0.005         # abaixo disto a lista não se moveu: chegou ao fim
SCROLL_SETTLE = 0.6

# A cripta no mapa é procurada pelo recorte memorizado dela. O limiar é baixo de
# propósito: o terreno em volta muda de uma cripta para outra, e um palpite
# errado custa só um clique antes de cair na busca pelas posições vizinhas.
MAP_MATCH_THRESHOLD = 0.6
WINDOW_OPENED_CHANGE = 0.2      # acima disto, o clique no mapa abriu uma janela


class CollectorError(RuntimeError):
    """Problema que impede a execução de começar ou de continuar."""


def icon_path(name: str) -> str:
    return os.path.join(CRYPT_IMAGES_DIR, *name.split("/"))


def icon_name(path: str) -> str:
    """ "…/images/cript/epic/3.png" -> "epic/3.png" """
    return "/".join(path.replace("\\", "/").split("/")[-2:])


def all_icon_names() -> Dict[str, List[str]]:
    """As imagens de cripta disponíveis, por tipo, na ordem dos números dos arquivos."""
    names: Dict[str, List[str]] = {}
    for kind in CRYPT_TYPES:
        folder = os.path.join(CRYPT_IMAGES_DIR, kind)
        try:
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        except OSError:
            files = []
        # 1.png, 2.png, ... 10.png - e não 1, 10, 11, 2.
        files.sort(key=lambda f: (int(f.split(".")[0]) if f.split(".")[0].isdigit() else 10 ** 6, f))
        names[kind] = [f"{kind}/{f}" for f in files]
    return names


def recognise_icon(vision: Vision, haystack, names: Optional[List[str]] = None) -> Optional[Hit]:
    """
    Descobre qual ícone de cripta aparece em `haystack`, e em que escala.

    Procura em uma faixa larga de escalas: o navegador desenha o jogo em um
    tamanho que depende da janela, e as imagens de images/cript vieram do
    cliente instalado. A escala medida aqui é guardada na calibração, e as
    buscas da execução passam a varrer só uma escada curta em torno dela.
    """
    if names is None:
        names = [name for group in all_icon_names().values() for name in group]
    if haystack is None or not names:
        return None
    thresholds = {icon_path(n): t for n, t in ICON_THRESHOLDS.items()}
    return vision.best_of(haystack, [icon_path(n) for n in names], WIDE_SCALES, thresholds)


class Collector:
    def __init__(self, browser: Browser, vision: Vision, calibration: Calibration, settings: Settings):
        self.browser = browser
        self.vision = vision
        self.calibration = calibration
        self.settings = settings

        run = settings.section("run")
        self.any_mode = run.get("mode") == ANY_MODE
        self.selected: List[str] = [] if self.any_mode else [
            name for name in run.get("selected", []) if os.path.exists(icon_path(name))
        ]
        self.target = int(run.get("crypt_count", 0))
        self.speedups = int(run.get("speedups_per_march", 0))

        timing = settings.section("timing")
        self.click_delay = float(timing.get("click_delay", 1.5))
        self.scroll_delta = int(timing.get("scroll_delta", 100))
        self.max_scrolls = int(timing.get("max_scrolls", 80))
        self.list_passes = max(1, int(timing.get("list_passes", 3)))
        self.march_timeout = float(timing.get("march_timeout", 1800))
        self.game_load_wait = float(timing.get("game_load_wait", GAME_LOAD_WAIT))

    # -------------------------------------------------------------- preparação
    def preflight(self) -> List[str]:
        """O que falta para poder executar - vazio quando está tudo pronto."""
        problems = []
        missing = self.calibration.missing_steps()
        if missing:
            titles = ", ".join(tr(f"step.{name}.title") for name in missing)
            problems.append(tr("run.missing_calibration", steps=titles))
        if not self.any_mode and not self.selected:
            problems.append(tr("run.no_selection"))
        if self.target <= 0:
            problems.append(tr("run.no_quantity"))
        return problems

    def sync_viewport(self):
        """
        Devolve a página ao tamanho em que foi calibrada e informa à calibração
        o que de fato conseguiu.

        Redimensionar vem primeiro porque elimina o problema; reescalar as
        coordenadas só o compensa.
        """
        wanted = self.calibration.viewport
        current = self.browser.viewport()
        if wanted[0] and wanted[1] and current != wanted:
            if self.browser.set_viewport(*wanted):
                logger.info(tr("run.viewport_resized", width=wanted[0], height=wanted[1]))
            else:
                logger.warning(tr("run.viewport_rescaled", width=current[0], height=current[1],
                                  cal_width=wanted[0], cal_height=wanted[1]))
        current = self.browser.viewport()
        self.calibration.use_viewport(*current)
        self.viewport = current

    # ---------------------------------------------------------------- execução
    def run(self) -> Dict[str, int]:
        problems = self.preflight()
        if problems:
            raise CollectorError("\n".join(problems))

        self.browser.ensure_attached()
        self.browser.make_visible()
        self.sync_viewport()
        logger.info(tr("run.start", target=self.target,
                       mode=tr("mode.any") if self.any_mode else tr("run.images", count=len(self.selected))))

        # Uma volta que falha não conta: a execução só termina com a quantidade
        # pedida explorada, ou quando o usuário a interrompe.
        done = failures = streak = 0
        while done < self.target:
            cancellation.check()
            logger.info(tr("run.round", round=done + 1, target=self.target))
            try:
                success = self.collect_one()
            except BrowserError as exc:
                self.reconnect(exc)
                success = False

            if success:
                done += 1
                streak = 0
            else:
                failures += 1
                streak += 1
            logger.info(tr("run.progress", done=done, target=self.target, failures=failures))
            if not success:
                self.recover(streak)

        return {"done": done, "failures": failures, "target": self.target}

    def recover(self, streak: int):
        """
        Deixa o jogo pronto para a próxima volta depois de uma que falhou.

        Uma janela que ficou aberta (a de uma cripta errada, uma oferta) taparia
        os cliques seguintes, e a volta nova falharia pelo mesmo motivo.
        """
        try:
            if streak and streak % MAX_CONSECUTIVE_FAILURES == 0:
                # Tantas falhas seguidas indicam o jogo preso em alguma tela:
                # recarregar a página o devolve ao mapa.
                logger.error(tr("run.too_many_failures", count=streak))
                self.browser.reload()
                cancellation.sleep(self.game_load_wait)
                self.sync_viewport()
            self.close_store() or self.close_window()
            self.browser.press_escape()
        except BrowserError as exc:
            self.reconnect(exc)
        cancellation.sleep(0.5)

    def reconnect(self, error: Exception):
        """
        Recupera a conexão com o jogo, insistindo até conseguir.

        Uma aba recarregada só precisa de uma conexão nova. Se nem isso
        funciona - aba travada, navegador fechado - o jogo é aberto de novo.
        """
        logger.warning(tr("run.reconnecting", error=error))
        reopen = False
        while True:
            cancellation.check()
            try:
                if reopen:
                    logger.warning(tr("run.reopening"))
                    self.browser.reopen_game()
                    cancellation.sleep(self.game_load_wait)
                else:
                    self.browser.attach()
                self.sync_viewport()
                return
            except BrowserError as exc:
                logger.warning(tr("run.reconnect_failed", error=exc))
                if reopen:
                    cancellation.sleep(FAILURE_PAUSE)
                reopen = True

    def collect_one(self) -> bool:
        self.close_store()
        self.open_crypt_menu()

        if self.any_mode:
            logger.info(tr("run.any_selected"))
            crypt = self.first_row_crypt()
            self.click(self.calibration.region_center("go_button"))
        else:
            crypt = self.search_crypt()
            if crypt is None:
                logger.warning(tr("run.search_failed"))
                return False

        # É depois do Go que a loja costuma abrir sozinha.
        self.close_store()
        if not self.enter_crypt(crypt):
            logger.warning(tr("run.explore_failed"))
            return False
        logger.info(tr("run.invading"))

        if not self.speedup_march():
            logger.warning(tr("run.speedup_failed"))
            return False
        return True

    # ------------------------------------------------------------------- ações
    def click(self, point: Point):
        cancellation.check()
        self.browser.click(point[0], point[1])
        cancellation.sleep(self.click_delay)

    def _find_close_button(self) -> Optional[Point]:
        """O X de uma janela aberta, pela imagem calibrada (ou pela que vem com o aplicativo)."""
        if self.calibration.is_calibrated("store_close_button"):
            path = self.calibration.ref_path("store_close_button")
            scale = self.calibration.image_scale("store_close_button")
        else:
            path = FALLBACK_CLOSE_IMAGE
            scale = min(self.viewport[0] / BUNDLED_IMAGE_SIZE[0], self.viewport[1] / BUNDLED_IMAGE_SIZE[1])
        hit = self.vision.find(path, None, base_scale=scale)
        return hit.center if hit and hit.passed else None

    def close_window(self) -> bool:
        """Fecha uma janela qualquer que tenha ficado aberta (menu errado, oferta) pelo X dela."""
        target = self._find_close_button()
        if target is None:
            return False
        self.click(target)
        logger.info(tr("run.popup_closed"))
        return True

    def close_store(self) -> bool:
        """
        Fecha a loja, se ela estiver aberta.

        Com a loja calibrada, é a imagem dela que diz se está aberta - só então
        o X é clicado. Sem essa calibração vale o comportamento antigo: qualquer
        X visível na tela é fechado.
        """
        if not self.calibration.is_calibrated("store_marker"):
            return self.close_window()
        marker = self.vision.find(self.calibration.ref_path("store_marker"), None,
                                  base_scale=self.calibration.image_scale("store_marker"))
        if marker is None or not marker.passed:
            return False
        # O X é procurado pela imagem; se ela falhar, vale a posição calibrada.
        target = self._find_close_button() or self.calibration.region_center("store_close_button")
        if target is None:
            return False
        self.click(target)
        logger.info(tr("run.store_closed"))
        return True

    def open_crypt_menu(self):
        self.click(self.calibration.point("watchtower_button"))
        self.click(self.calibration.point("crypts_tab"))

    # ------------------------------------------------------------------- lista
    def _search_column(self):
        """A coluna de ícones da lista: onde procurar, e onde girar a roda do mouse."""
        icon = self.calibration.region("crypt_icon_area")
        whole_list = self.calibration.region("crypt_list_area")
        if whole_list:
            top, height = min(icon[1], whole_list[1]), whole_list[3]
            if icon[1] < whole_list[1]:
                height += whole_list[1] - icon[1]
            column = (icon[0] - icon[2] // 4, top, icon[2] + icon[2] // 2, height)
            watched = whole_list
        else:
            # Sem a lista calibrada, só a primeira linha, com folga para um
            # ícone que parou desalinhado depois da rolagem.
            column = expand(icon, icon[2] // 4, icon[3] // 2)
            watched = expand(icon, icon[2], icon[3])
        return column, watched

    def _icon_scales(self):
        scale = self.calibration.current_icon_scale()
        return ladder(scale) if scale else WIDE_SCALES

    def find_crypt(self, column) -> Optional[Hit]:
        """O ícone selecionado que melhor casa na coluna, com a caixa em pixels da página."""
        haystack, (left, top) = self.vision.grab(column)
        if haystack is None:
            return None
        thresholds = {icon_path(n): t for n, t in ICON_THRESHOLDS.items()}
        hit = self.vision.best_of(haystack, [icon_path(n) for n in self.selected],
                                  self._icon_scales(), thresholds)
        if hit is None:
            return None
        return hit._replace(box=(hit.box[0] + left, hit.box[1] + top, hit.box[2], hit.box[3]))

    def first_row_crypt(self) -> Optional[str]:
        """Qual cripta está na primeira linha da lista - no modo Qualquer ninguém a escolheu."""
        icon = self.calibration.region("crypt_icon_area")
        haystack, _ = self.vision.grab(expand(icon, icon[2] // 4, icon[3] // 2))
        if haystack is None:
            return None
        names = [name for group in all_icon_names().values() for name in group]
        thresholds = {icon_path(n): t for n, t in ICON_THRESHOLDS.items()}
        hit = self.vision.best_of(haystack, [icon_path(n) for n in names], self._icon_scales(), thresholds)
        return icon_name(hit.path) if hit and hit.passed else None

    def search_crypt(self) -> Optional[str]:
        """
        Percorre a lista até achar uma das criptas selecionadas e clica no Go da linha dela.

        Devolve o nome da imagem que casou ("rare/2.png"), ou None se nenhuma apareceu.
        """
        column, watched = self._search_column()
        anchor = (watched[0] + watched[2] // 2, watched[1] + watched[3] // 2)
        go = self.calibration.region_center("go_button")
        icon = self.calibration.region_center("crypt_icon_area")

        passes = scrolls = 0
        while True:
            cancellation.check()
            hit = self.find_crypt(column)
            name = icon_name(hit.path) if hit else "-"
            if hit and hit.passed:
                logger.info(tr("run.crypt_found", name=name, score=hit.score))
                if not self.calibration.icon_scale:
                    self.calibration.set_icon_scale(hit.scale, self.viewport)
                    self.calibration.save()
                # O Go fica na mesma linha do ícone, com o deslocamento calibrado.
                self.click((go[0], hit.center[1] + (go[1] - icon[1])))
                return name
            logger.debug(f"no crypt above threshold; best guess {name} "
                         f"score {hit.score if hit else 0:.3f} scale {hit.scale if hit else 0}")

            before = self.browser.capture(watched)
            self.browser.scroll(anchor[0], anchor[1], self.scroll_delta)
            cancellation.sleep(SCROLL_SETTLE)
            scrolls += 1
            at_end = changed_fraction(before, self.browser.capture(watched)) < LIST_END_CHANGE
            if not at_end and scrolls < self.max_scrolls:
                continue

            passes += 1
            if at_end and scrolls == 1:
                logger.info(tr("run.list_did_not_move"))
            if passes >= self.list_passes:
                logger.info(tr("run.list_exhausted", best=name, score=hit.score if hit else 0.0))
                return None

            logger.info(tr("run.list_restart", current=passes + 1, total=self.list_passes))
            self.close_window()
            self.open_crypt_menu()
            self.scroll_to_top(anchor, watched)
            scrolls = 0

    def scroll_to_top(self, anchor: Point, watched):
        for _ in range(self.max_scrolls):
            cancellation.check()
            before = self.browser.capture(watched)
            self.browser.scroll(anchor[0], anchor[1], -6 * abs(self.scroll_delta))
            cancellation.sleep(SCROLL_SETTLE)
            if changed_fraction(before, self.browser.capture(watched)) < LIST_END_CHANGE:
                return

    # ------------------------------------------------------------------ cripta
    def _tile(self) -> Tuple[int, int]:
        """Distância, na tela, entre uma casa do mapa e as vizinhas dela."""
        grid = self.calibration.map_grid()
        if grid:
            (ax, ay), (bx, by) = grid
            return max(abs(ax), abs(bx)), max(abs(ay), abs(by))
        return self.viewport[0] // 9, self.viewport[1] // 9

    def _crypt_offsets(self) -> List[Point]:
        """
        A cripta e as oito casas em volta dela, como deslocamentos do ponto calibrado.

        Com as duas casas vizinhas calibradas a grade é medida: as outras seis
        saem dos dois deslocamentos (os opostos, a soma e a diferença). Sem
        elas, a distância entre as casas é estimada pelo tamanho da página.
        """
        grid = self.calibration.map_grid()
        if grid:
            (ax, ay), (bx, by) = grid
            return [(0, 0), (ax, ay), (-ax, -ay), (bx, by), (-bx, -by),
                    (ax + bx, ay + by), (-ax - bx, -ay - by), (ax - bx, ay - by), (bx - ax, by - ay)]
        dx, dy = self._tile()
        return [(0, 0), (0, dy), (0, -dy), (dx, 0), (-dx, 0),
                (dx // 2, dy // 2), (-dx // 2, -dy // 2), (dx // 2, -dy // 2), (-dx // 2, dy // 2)]

    def _crypt_points(self) -> List[Point]:
        """O ponto calibrado da cripta e os pontos em volta dele, para quando ela não cai no centro."""
        x, y = self.calibration.point("crypt_on_map")
        return [(x + ox, y + oy) for ox, oy in self._crypt_offsets()]

    # A cripta no mapa
    # ----------------
    # Depois de algumas dezenas de criptas o jogo deixa de centralizar o mapa
    # nela: a cripta aparece em uma das casas vizinhas. Clicar nas nove posições
    # até acertar funciona, mas cada erro custa segundos. Então, quando um clique
    # acerta, o pedaço do mapa em volta dele é guardado como a aparência daquela
    # cripta; nas voltas seguintes esse recorte é procurado na vizinhança do
    # centro e o primeiro clique vai direto para onde ele casou. As nove
    # posições continuam como reserva, e um recorte que levou a um clique errado
    # é substituído pelo do clique que acertou.
    def _sprite_half(self) -> int:
        """Metade do lado do recorte memorizado: ele cobre a cripta, não a casa inteira."""
        return max(16, self._tile()[0] // 4)

    def _map_area(self) -> Region:
        """A vizinhança do ponto calibrado: todas as posições possíveis, com folga para o recorte."""
        x, y = self.calibration.point("crypt_on_map")
        offsets = self._crypt_offsets()
        dx, dy = max(abs(ox) for ox, _ in offsets), max(abs(oy) for _, oy in offsets)
        reach = 2 * self._sprite_half()
        return (x - dx - reach, y - dy - reach, 2 * (dx + reach), 2 * (dy + reach))

    def _map_ref_path(self, crypt: str) -> str:
        """ "rare/2.png" -> calib_refs/map/rare_2.png """
        return os.path.join(self.calibration.refs_dir, "map", crypt.replace("/", "_"))

    def _map_refs(self, crypt: Optional[str]) -> List[str]:
        """O recorte da cripta escolhida; sem saber qual ela é, todos os já memorizados."""
        if crypt:
            return [self._map_ref_path(crypt)]
        folder = os.path.join(self.calibration.refs_dir, "map")
        try:
            return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith(".png")]
        except OSError:
            return []

    def _locate_on_map(self, snapshot, origin: Point, crypt: Optional[str]) -> Optional[Point]:
        """Onde clicar, pelo recorte memorizado - ou None se ele não existe ou não aparece."""
        if snapshot is None:
            return None
        best_score, best_point = 0.0, None
        for path in self._map_refs(crypt):
            if not os.path.exists(path):
                continue
            try:
                # Em cores: no mapa a cor separa a cripta do terreno melhor que a forma.
                template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            except OSError:
                continue
            if template is None or template.shape[0] > snapshot.shape[0] or template.shape[1] > snapshot.shape[1]:
                continue
            result = cv2.matchTemplate(snapshot, template, cv2.TM_CCOEFF_NORMED)
            result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
            _, score, _, location = cv2.minMaxLoc(result)
            if score > best_score:
                best_score = float(score)
                best_point = (origin[0] + location[0] + template.shape[1] // 2,
                              origin[1] + location[1] + template.shape[0] // 2)
        if best_point is None or best_score < MAP_MATCH_THRESHOLD:
            logger.debug(f"crypt {crypt or '?'} not located on the map (best score {best_score:.2f}).")
            return None
        logger.info(tr("run.map_located", x=best_point[0], y=best_point[1], score=best_score))
        return best_point

    def _learn_map_sprite(self, snapshot, origin: Point, position: Point, crypt: Optional[str]):
        """Guarda o pedaço do mapa em volta do clique que abriu a cripta."""
        if snapshot is None or not crypt:
            return
        half = self._sprite_half()
        left, top = position[0] - origin[0] - half, position[1] - origin[1] - half
        if left < 0 or top < 0:
            return
        crop = snapshot[top:top + 2 * half, left:left + 2 * half]
        if crop.shape[:2] != (2 * half, 2 * half):
            return
        path = self._map_ref_path(crypt)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # imencode + tofile: o imwrite não grava em caminhos com acentos no Windows.
            cv2.imencode(".png", crop)[1].tofile(path)
        except (OSError, cv2.error) as exc:
            logger.debug(f"could not save the map sprite of {crypt}: {exc}")
            return
        logger.info(tr("run.map_learned", name=crypt))

    def _window_area(self) -> Region:
        """Onde uma janela aberta por um clique no mapa aparece: os botões Explorar e Abrir."""
        region = self.calibration.region("explore_button")
        margin = max(20, region[3])
        left, top, width, height = expand(region, margin, margin)
        right, bottom = left + width, top + height
        open_button = self.calibration.point("open_button")
        if open_button:
            left, top = min(left, open_button[0] - margin), min(top, open_button[1] - margin)
            right, bottom = max(right, open_button[0] + margin), max(bottom, open_button[1] + margin)
        return (left, top, right - left, bottom - top)

    def _find_explore(self) -> Optional[Point]:
        region = self.calibration.region("explore_button")
        margin = max(20, region[3])
        hit = self.vision.find(self.calibration.ref_path("explore_button"), expand(region, margin, margin),
                               base_scale=self.calibration.image_scale("explore_button"))
        return hit.center if hit and hit.passed else None

    def enter_crypt(self, crypt: Optional[str] = None) -> bool:
        """Clica na cripta no mapa e no botão Explorar (passando pelo Abrir nas criptas raras)."""
        open_button = self.calibration.point("open_button")
        watched = self._window_area()

        area = self._map_area()
        origin = (max(0, area[0]), max(0, area[1]))
        snapshot = self.browser.capture(area)
        positions = self._crypt_points()
        guess = self._locate_on_map(snapshot, origin, crypt)
        if guess:
            near = self._sprite_half()
            positions = [guess] + [p for p in positions
                                   if abs(p[0] - guess[0]) > near or abs(p[1] - guess[1]) > near]

        for attempt, position in enumerate(positions):
            cancellation.check()
            if attempt > 0:
                logger.info(tr("run.explore_retry", attempt=attempt + 1, total=len(positions)))

            before = self.browser.capture(watched)
            self.click(position)
            # Um clique em terreno vazio não abre janela nenhuma: sem mudança
            # onde os botões apareceriam, não vale procurar por eles - nem
            # clicar às cegas na posição do Abrir, que ali ainda é mapa.
            opened = changed_fraction(before, self.browser.capture(watched)) >= WINDOW_OPENED_CHANGE
            if opened:
                explore = self._find_explore()
                if explore is None and open_button:
                    self.click(open_button)
                    explore = self._find_explore()
                if explore is not None:
                    if position != guess:
                        self._learn_map_sprite(snapshot, origin, position, crypt)
                    self.click(explore)
                    return True

            # O clique caiu em outro objeto do mapa: o jogo abre um popup com as
            # informações dele, que taparia o próximo clique. Ele pode aparecer
            # fora da área dos botões, então o X é procurado mesmo sem `opened`.
            closed = self.close_store() or self.close_window()
            if opened and not closed:
                self.browser.press_escape()
                cancellation.sleep(0.5)
        return False

    # ------------------------------------------------------------------ marcha
    def _march_visible(self) -> bool:
        region = self.calibration.region("march_icon")
        margin = max(10, region[3] // 2)
        hit = self.vision.find(self.calibration.ref_path("march_icon"), expand(region, margin, margin),
                               base_scale=self.calibration.image_scale("march_icon"))
        return bool(hit and hit.passed)

    def speedup_march(self) -> bool:
        """Usa as acelerações e espera a marcha ir e voltar."""
        self.click(self.calibration.point("speedup_button"))
        if not self._march_visible():
            return False

        use = self.calibration.point("use_button")
        for _ in range(self.speedups):
            self.click(use)

        # A tela de aceleração fecha sozinha quando a marcha chega.
        started = time.time()
        while self._march_visible():
            if time.time() - started > self.march_timeout:
                logger.warning(tr("run.march_timeout"))
                break
            logger.info(tr("run.waiting_march"))
            cancellation.sleep(5.0)

        duration = time.time() - started
        logger.info(tr("run.waiting_return", seconds=int(duration)))
        cancellation.sleep(duration)
        return True
