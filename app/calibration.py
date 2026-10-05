"""
Onde ficam os controles do jogo - aprendido, nunca escrito à mão.

As posições são gravadas uma vez, marcando-as sobre uma captura do jogo, e ficam
em calibration.json.

Três tipos de passo
-------------------
click   um ponto a clicar.
area    um retângulo, sem imagem guardada.
region  um retângulo E o recorte do que havia dentro dele. O recorte vira uma
        imagem de referência: na execução procura-se essa imagem, o que confirma
        que a tela certa está aberta e acha o botão mesmo que ele se desloque.

`acts` diz se o que o passo marca é um controle a ser pressionado. O assistente
pressiona esses controles ao gravá-los (um ponto, no próprio ponto; um
retângulo, no centro dele), para que o jogo chegue à tela que o passo seguinte
pede. Os passos sem `acts` são áreas de validação: só confirmam o que está na
tela e o assistente segue adiante sem clicar.

Independência do tamanho da página
----------------------------------
O tamanho da página no momento da calibração é guardado junto de cada passo. Se
a janela estiver de outro tamanho na execução, pontos e regiões são reescalados
pela razão, e as imagens de referência são procuradas em uma escada de escalas.
"""

import json
import os
import time
from typing import Dict, List, NamedTuple, Optional, Tuple

import cv2
import numpy as np

from .paths import CALIBRATION_FILE, CALIBRATION_REFS_DIR

Point = Tuple[int, int]
Region = Tuple[int, int, int, int]      # (left, top, width, height)

# Abaixo disto uma referência não tem por onde ser reconhecida: um recorte liso
# marca ~1.0 contra QUALQUER fundo liso e seria "encontrado" em todo lugar.
MIN_REFERENCE_CONTRAST = 10.0
MIN_REGION_SIZE = 6


class Step(NamedTuple):
    name: str
    type: str                # click | area | region
    acts: bool = False
    optional: bool = False

    @property
    def is_rectangle(self) -> bool:
        return self.type in ("area", "region")

    @property
    def keeps_reference(self) -> bool:
        return self.type == "region"


# A ordem é a de uma execução real: cada passo deixa o jogo no estado que o
# seguinte espera, então calibrar é jogar a sequência uma vez. Título e
# instrução de cada passo vêm do i18n ("step.<nome>.title" / ".text").
STEPS: List[Step] = [
    Step("watchtower_button", "click", acts=True),
    Step("crypts_tab", "click", acts=True),
    Step("crypt_icon_area", "area"),
    Step("crypt_list_area", "area", optional=True),
    Step("go_button", "area", acts=True),
    # A loja costuma abrir sozinha logo depois do Go - mas nem sempre. Por isso
    # os dois passos dela são opcionais e o assistente deixa adiá-los para o fim.
    Step("store_marker", "region", optional=True),
    Step("store_close_button", "region", acts=True, optional=True),
    # As duas casas vizinhas medem a grade do mapa. Vêm antes da cripta porque o
    # clique nela abre uma janela por cima do mapa.
    Step("map_neighbor_a", "click", optional=True),
    Step("map_neighbor_b", "click", optional=True),
    Step("crypt_on_map", "click", acts=True),
    Step("open_button", "click", acts=True, optional=True),
    Step("explore_button", "region", acts=True),
    Step("speedup_button", "click", acts=True),
    Step("march_icon", "region"),
    Step("use_button", "click", acts=True),
]

STEPS_BY_NAME = {step.name: step for step in STEPS}
STORE_STEPS = ("store_marker", "store_close_button")
MAP_NEIGHBOR_STEPS = ("map_neighbor_a", "map_neighbor_b")


class Calibration:
    """As posições calibradas, reescaladas para o tamanho de página da execução."""

    def __init__(self, path: str = CALIBRATION_FILE, refs_dir: str = CALIBRATION_REFS_DIR):
        self.path = path
        self.refs_dir = refs_dir
        self.points: Dict[str, Point] = {}
        self.regions: Dict[str, Dict[str, int]] = {}
        # Tamanho da página em que cada passo foi gravado. Uma calibração pode
        # atravessar várias capturas e a janela pode mudar de tamanho entre elas.
        self.step_viewports: Dict[str, Point] = {}
        # Página do passo gravado por último: é o tamanho que a execução restaura.
        self.viewport: Point = (0, 0)
        # Em que escala o jogo desenha os ícones de images/cript, e em que
        # tamanho de página isso foi medido.
        self.icon_scale: float = 0.0
        self.icon_scale_viewport: Point = (0, 0)
        self.created_at: str = ""
        self._current_viewport: Point = (0, 0)
        self.load()

    # ------------------------------------------------------------ persistência
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        self.points = {k: (int(v[0]), int(v[1])) for k, v in (data.get("points") or {}).items()}
        self.regions = data.get("regions") or {}
        self.step_viewports = {k: (int(v[0]), int(v[1]))
                               for k, v in (data.get("step_viewports") or {}).items()}
        self.viewport = tuple(int(v) for v in (data.get("viewport") or (0, 0)))[:2]
        self.icon_scale = float(data.get("icon_scale") or 0.0)
        self.icon_scale_viewport = tuple(int(v) for v in (data.get("icon_scale_viewport") or (0, 0)))[:2]
        self.created_at = data.get("created_at", "")

    def save(self):
        payload = {
            "viewport": list(self.viewport),
            "points": {k: list(v) for k, v in self.points.items()},
            "regions": self.regions,
            "step_viewports": {k: list(v) for k, v in self.step_viewports.items()},
            "icon_scale": self.icon_scale,
            "icon_scale_viewport": list(self.icon_scale_viewport),
            "created_at": self.created_at,
        }
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ estado
    def is_calibrated(self, name: str) -> bool:
        step = STEPS_BY_NAME.get(name)
        if step is None:
            return False
        if step.is_rectangle:
            return name in self.regions and (not step.keeps_reference or os.path.exists(self.ref_path(name)))
        return name in self.points

    def missing_steps(self) -> List[str]:
        return [step.name for step in STEPS if not step.optional and not self.is_calibrated(step.name)]

    @property
    def complete(self) -> bool:
        return not self.missing_steps()

    # ----------------------------------------------------------------- escala
    def use_viewport(self, width: int, height: int):
        """Informa em que tamanho de página a execução atual está."""
        self._current_viewport = (int(width), int(height))

    @staticmethod
    def _ratio(recorded: Point, current: Point) -> Tuple[float, float]:
        if not (recorded[0] and recorded[1] and current[0] and current[1]):
            return 1.0, 1.0
        return current[0] / recorded[0], current[1] / recorded[1]

    def _factors(self, name: str) -> Tuple[float, float]:
        return self._ratio(self.step_viewports.get(name, self.viewport), self._current_viewport)

    def image_scale(self, name: str) -> float:
        """Quanto a referência de um passo precisa crescer ou encolher para a página atual."""
        return min(self._factors(name))

    def current_icon_scale(self) -> float:
        """Escala dos ícones de cripta na página atual; 0 quando ainda não foi medida."""
        if not self.icon_scale:
            return 0.0
        return self.icon_scale * min(self._ratio(self.icon_scale_viewport, self._current_viewport))

    def set_icon_scale(self, scale: float, viewport: Point):
        self.icon_scale = round(float(scale), 3)
        self.icon_scale_viewport = (int(viewport[0]), int(viewport[1]))

    # ----------------------------------------------------------------- valores
    def point(self, name: str) -> Optional[Point]:
        raw = self.points.get(name)
        if not raw:
            return None
        scale_x, scale_y = self._factors(name)
        return (int(round(raw[0] * scale_x)), int(round(raw[1] * scale_y)))

    def map_grid(self) -> Optional[Tuple[Point, Point]]:
        """
        Os dois deslocamentos da grade do mapa: da cripta até cada casa vizinha marcada.

        None quando as vizinhas não foram calibradas, ou quando as duas ficam na
        mesma linha (opostas, ou a mesma casa) e por isso não definem a grade.
        """
        centre = self.point("crypt_on_map")
        marks = [self.point(name) for name in MAP_NEIGHBOR_STEPS]
        if not centre or not all(marks):
            return None
        (ax, ay), (bx, by) = [(mark[0] - centre[0], mark[1] - centre[1]) for mark in marks]
        if abs(ax * by - ay * bx) < 0.2 * max(1, ax * ax + ay * ay, bx * bx + by * by):
            return None
        return (ax, ay), (bx, by)

    def region(self, name: str) -> Optional[Region]:
        raw = self.regions.get(name)
        if not raw:
            return None
        scale_x, scale_y = self._factors(name)
        return (
            int(round(raw["left"] * scale_x)),
            int(round(raw["top"] * scale_y)),
            max(1, int(round(raw["width"] * scale_x))),
            max(1, int(round(raw["height"] * scale_y))),
        )

    def region_center(self, name: str) -> Optional[Point]:
        region = self.region(name)
        if not region:
            return None
        return (region[0] + region[2] // 2, region[1] + region[3] // 2)

    def action_point(self, name: str) -> Optional[Point]:
        """Onde clicar para operar o que um passo marcou: o ponto, ou o centro do retângulo."""
        step = STEPS_BY_NAME.get(name)
        if step is None:
            return None
        return self.region_center(name) if step.is_rectangle else self.point(name)

    def ref_path(self, name: str) -> str:
        return os.path.join(self.refs_dir, f"{name}.png")

    # ---------------------------------------------------------------- gravação
    def _stamp(self, name: str, viewport: Point):
        if viewport[0] and viewport[1]:
            self.step_viewports[name] = (int(viewport[0]), int(viewport[1]))
            self.viewport = self.step_viewports[name]
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def set_point(self, name: str, x: int, y: int, viewport: Point):
        self.points[name] = (int(x), int(y))
        self._stamp(name, viewport)

    def set_region(self, name: str, corner_a: Point, corner_b: Point, image, viewport: Point) -> Optional[float]:
        """
        Grava um retângulo e, nos passos 'region', o recorte dentro dele.

        Os cantos podem vir em qualquer ordem. Levanta ValueError se a área for
        pequena demais. Devolve o contraste do recorte quando ele é baixo demais
        para servir de referência (o chamador avisa), senão None.
        """
        left, right = sorted((int(corner_a[0]), int(corner_b[0])))
        top, bottom = sorted((int(corner_a[1]), int(corner_b[1])))
        if right - left < MIN_REGION_SIZE or bottom - top < MIN_REGION_SIZE:
            raise ValueError("too small")

        low_contrast = None
        if STEPS_BY_NAME[name].keeps_reference:
            crop = image[top:bottom, left:right]
            if crop.size == 0:
                raise ValueError("outside the capture")
            os.makedirs(self.refs_dir, exist_ok=True)
            # imencode + tofile: o imwrite não grava em caminhos com acentos no Windows.
            cv2.imencode(".png", crop)[1].tofile(self.ref_path(name))
            contrast = float(np.std(crop))
            if contrast < MIN_REFERENCE_CONTRAST:
                low_contrast = contrast

        self.regions[name] = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        self._stamp(name, viewport)
        return low_contrast

    def forget(self, name: str):
        """Descarta um passo, para refazê-lo sem repetir a sequência inteira."""
        self.points.pop(name, None)
        self.regions.pop(name, None)
        self.step_viewports.pop(name, None)
        try:
            os.remove(self.ref_path(name))
        except OSError:
            pass
