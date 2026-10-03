"""
Achar um botão ou um ícone pela imagem dele.

O cv2.matchTemplate não tem invariância de escala: uma referência recortada em
uma página de 1920 de largura marca perto de zero contra o mesmo botão em uma de
1536. Por isso toda busca varre uma escada curta de escalas em torno da razão
entre a página calibrada e a atual.

Redimensionar o template sempre custa correlação - a interpolação nunca
reproduz os pixels originais - então um template redimensionado compete contra
um limiar um pouco menor (`scaled_threshold_relief`).
"""

import os
from typing import Any, Dict, Iterable, NamedTuple, Optional, Sequence, Tuple

import cv2
import numpy as np

from .logger import logger

Region = Tuple[int, int, int, int]      # (left, top, width, height) em pixels CSS da página

# Escalas tentadas quando ainda não se sabe em que tamanho o jogo desenha os
# ícones de cripta (as imagens de images/cript vieram do cliente em 1920x1080).
WIDE_SCALES = tuple(round(0.5 + 0.05 * step, 2) for step in range(21))     # 0.50 .. 1.50


class Hit(NamedTuple):
    path: str
    score: float
    scale: float
    box: Region             # na mesma referência da imagem em que foi procurado
    passed: bool

    @property
    def center(self) -> Tuple[int, int]:
        return (self.box[0] + self.box[2] // 2, self.box[1] + self.box[3] // 2)


def changed_fraction(before, after, tolerance: int = 12) -> float:
    """
    Quanto da tela mudou entre duas capturas, de 0 a 1.

    'O clique não fez nada' é a coisa mais difícil de diagnosticar por um log:
    um clique que erra e um clique em área morta são idênticos, ambos mudos.
    Comparar a tela antes e depois transforma isso em um número. A tolerância
    ignora o tremor das animações e do anti-aliasing.
    """
    if before is None or after is None:
        return 0.0
    if before.shape != after.shape or before.size == 0:
        return 1.0
    difference = cv2.absdiff(before, after)
    if difference.ndim == 3:
        difference = difference.max(axis=2)
    return float((difference > tolerance).mean())


def ladder(base: float) -> Tuple[float, ...]:
    """
    Escalas tentadas, da mais provável para a menos provável.

    A escada é fina perto da escala nominal porque a interface do jogo não
    acompanha a página de forma perfeitamente linear: um erro de 2% já derruba a
    correlação de um ícone de 60 px o bastante para perder o match.
    """
    factors = (1.0, 0.98, 1.02, 0.95, 1.05) if abs(base - 1.0) < 0.02 else \
              (1.0, 0.98, 1.02, 0.95, 1.05, 0.92, 1.08, 0.9, 1.1)
    scales = []
    for factor in factors:
        value = round(base * factor, 3)
        if value > 0 and value not in scales:
            scales.append(value)
    return tuple(scales)


def expand(region: Region, margin_x: int, margin_y: int) -> Region:
    return (region[0] - margin_x, region[1] - margin_y,
            region[2] + 2 * margin_x, region[3] + 2 * margin_y)


class Vision:
    """Busca de templates dentro de uma região da página do jogo."""

    def __init__(self, browser, config: Dict[str, Any]):
        self.browser = browser
        self.threshold = float(config.get("match_threshold", 0.80))
        self.relief = float(config.get("scaled_threshold_relief", 0.06))
        self._cache: Dict[Tuple[str, float, float], Optional[np.ndarray]] = {}

    # --------------------------------------------------------------- templates
    def load_template(self, path: str, scale: float = 1.0) -> Optional[np.ndarray]:
        # A data do arquivo entra na chave: uma referência recalibrada tem o
        # mesmo caminho e outro conteúdo.
        try:
            modified = os.path.getmtime(path)
        except OSError:
            return None
        key = (os.path.abspath(path), round(float(scale), 3), modified)
        if key in self._cache:
            return self._cache[key]

        # imdecode em vez de imread: o imread não abre caminhos com acentos no Windows.
        try:
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        except OSError:
            image = None
        if image is not None and abs(scale - 1.0) > 0.01:
            width = max(1, int(round(image.shape[1] * scale)))
            height = max(1, int(round(image.shape[0] * scale)))
            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            image = cv2.resize(image, (width, height), interpolation=interpolation)
        if image is None:
            logger.error(f"Reference image could not be read: {path}")

        self._cache[key] = image
        return image

    # ----------------------------------------------------------------- captura
    def grab(self, region: Optional[Region] = None):
        """Captura a região em tons de cinza. Devolve (imagem, (left, top)) já recortada à página."""
        left, top = (max(0, int(region[0])), max(0, int(region[1]))) if region else (0, 0)
        image = self.browser.capture(region)
        if image is None or image.size == 0:
            return None, (left, top)
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (left, top)

    # ------------------------------------------------------------------- busca
    def best_match(self, haystack: np.ndarray, path: str, scales: Sequence[float],
                   threshold: Optional[float] = None) -> Optional[Hit]:
        """
        O melhor lugar para `path` dentro de `haystack`, tenha ou não passado do limiar.

        Devolver também o que não passou é o que permite ao log dizer o quanto
        faltou, em vez de só "não encontrado".
        """
        limit = self.threshold if threshold is None else threshold
        best: Optional[Hit] = None
        best_margin = None
        for scale in scales:
            template = self.load_template(path, scale)
            if template is None:
                return None
            height, width = template.shape[:2]
            if height > haystack.shape[0] or width > haystack.shape[1]:
                continue

            result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
            # Áreas lisas produzem NaN aqui.
            result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
            _, score, _, location = cv2.minMaxLoc(result)

            bar = limit if abs(scale - 1.0) <= 0.01 else max(0.0, limit - self.relief)
            margin = score - bar
            if best_margin is None or margin > best_margin:
                best_margin = margin
                best = Hit(path, float(score), scale, (location[0], location[1], width, height),
                           margin >= 0)
        return best

    def best_of(self, haystack: np.ndarray, paths: Iterable[str], scales: Sequence[float],
                thresholds: Optional[Dict[str, float]] = None) -> Optional[Hit]:
        """Entre várias imagens, a que casou melhor - as que passaram do limiar têm preferência."""
        best: Optional[Hit] = None
        for path in paths:
            hit = self.best_match(haystack, path, scales, (thresholds or {}).get(path))
            if hit is None:
                continue
            if best is None or (hit.passed, hit.score) > (best.passed, best.score):
                best = hit
        return best

    def find(self, path: str, region: Optional[Region] = None, base_scale: float = 1.0,
             threshold: Optional[float] = None) -> Optional[Hit]:
        """Procura a referência em uma região da página; a caixa do Hit vem em pixels da página."""
        if not os.path.exists(path):
            logger.error(f"Reference image is missing: {path}")
            return None
        scales = ladder(base_scale)

        # Uma região calibrada rente ao botão fica menor que o próprio template
        # e o matchTemplate não teria onde deslizar: cresce até caber com folga.
        largest = self.load_template(path, max(scales))
        if region is not None and largest is not None:
            lack_x = int(largest.shape[1] * 1.2) - region[2]
            lack_y = int(largest.shape[0] * 1.2) - region[3]
            region = expand(region, max(0, (lack_x + 1) // 2), max(0, (lack_y + 1) // 2))

        haystack, (left, top) = self.grab(region)
        if haystack is None:
            return None
        hit = self.best_match(haystack, path, scales, threshold)
        if hit is None:
            return None
        hit = hit._replace(box=(hit.box[0] + left, hit.box[1] + top, hit.box[2], hit.box[3]))
        if not hit.passed:
            logger.debug(f"'{os.path.basename(path)}' not found in {region} (best score {hit.score:.2f}).")
        return hit
