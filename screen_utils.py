# -*- coding: utf-8 -*-
"""
Camada de compatibilidade de resolucao do Crypt Collector.

Motivo: as imagens de referencia (images/*.png) e as coordenadas padrao do
config_crypt.cfg foram capturadas em 1920x1080. O cv2.matchTemplate NAO tem
invariancia de escala, entao em monitores HD (1366x768, 1280x720) nenhuma
imagem era encontrada e o robo ficava rodando sem sair do lugar.

Este modulo centraliza:
  * DPI awareness (evita que o Windows entregue screenshots virtualizados);
  * conversao/normalizacao das regioes gravadas pela calibracao;
  * reescala das coordenadas do config para a resolucao atual;
  * busca de template em varias escalas, com cache.
"""

import ast
import ctypes
import os
import sys

import cv2
import numpy as np
import pyautogui

# Resolucao em que os PNGs de images/ foram capturados.
REFERENCE_RESOLUTION = (1920, 1080)

# Versao do formato do config_crypt.cfg.
#   1 (ou ausente) -> areas gravadas pela calibracao antiga em (x1, y1, x2, y2)
#   2              -> todas as areas em (left, top, width, height)
CONFIG_VERSION = 2

# Folga minima entre a regiao de busca e o template (evita regiao menor que a imagem).
_MIN_MATCH_REGION_RATIO = 1.3

# Redimensionar o template custa correlacao mesmo quando o alvo esta certo (a
# interpolacao nunca reproduz os pixels originais). Sem este desconto, um icone
# de cripta corretamente localizado marcava 0.79 e era descartado pelo 0.8.
SCALED_THRESHOLD_RELIEF = 0.06

# Chaves que guardam um ponto (x, y).
POINT_KEYS = (
    "cord_click_watchtower",
    "cord_click_cripts",
    "cord_click_go_cript",
    "cord_speedup_march",
    "cord_click_use_speedups",
    "open_button",
    "cord_click_scripts",
)

# Chaves que guardam uma regiao de 4 valores.
REGION_KEYS = (
    "area_menu_button_go_cript",
    "area_cript_icons",
    "cord_click_use_speedups_screen",
    "cord_explore_button",
    "verify_if_open_explorer_button",
)

# Regioes que a calibracao antiga gravava em formato de cantos (x1, y1, x2, y2).
# screen_area nao entra aqui porque comeca em (0, 0) e os dois formatos coincidem.
# cord_explore_button tambem nao: sempre foi escrito a mao em (left, top, w, h).
LEGACY_CORNER_KEYS = (
    "area_menu_button_go_cript",
    "area_cript_icons",
    "cord_click_use_speedups_screen",
    "verify_if_open_explorer_button",
)

_dpi_ready = False
_template_cache = {}

# Resultado da ultima busca, para diagnostico (ver locate()).
last_match = {"path": None, "score": 0.0, "scale": None, "region": None, "hit": False}


# --------------------------------------------------------------------------
# Tela / DPI
# --------------------------------------------------------------------------
def enable_dpi_awareness():
    """
    Marca o processo como DPI aware.

    Sem isto, num notebook HD com escala do Windows em 125%/150% o processo
    recebe uma tela virtualizada: o screenshot sai borrado e esticado e as
    coordenadas do clique nao batem com o que a calibracao gravou.
    """
    global _dpi_ready
    if _dpi_ready:
        return
    _dpi_ready = True
    if sys.platform != "win32":
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_screen_size():
    """Resolucao real do monitor primario, em pixels."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            width = int(user32.GetSystemMetrics(0))
            height = int(user32.GetSystemMetrics(1))
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass
    size = pyautogui.size()
    return int(size[0]), int(size[1])


def get_screen_rect():
    """Tela inteira no formato (left, top, width, height)."""
    width, height = get_screen_size()
    return (0, 0, width, height)


def dpi_scale():
    """Fator de escala do Windows (1.0 = 100%, 1.5 = 150%)."""
    if sys.platform != "win32":
        return 1.0
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


def image_scale(screen=None):
    """Quanto os PNGs de referencia precisam encolher/crescer para a tela atual."""
    width, height = screen or get_screen_size()
    return min(width / float(REFERENCE_RESOLUTION[0]), height / float(REFERENCE_RESOLUTION[1]))


# --------------------------------------------------------------------------
# Regioes
# --------------------------------------------------------------------------
def corners_to_region(values):
    """(x1, y1, x2, y2) -> (left, top, width, height), aceitando arrasto em qualquer sentido."""
    x1, y1, x2, y2 = (int(v) for v in values)
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return (left, top, right - left, bottom - top)


def scale_point(point, scale_x, scale_y):
    return (int(round(point[0] * scale_x)), int(round(point[1] * scale_y)))


def scale_region(region, scale_x, scale_y):
    left, top, width, height = region
    return (
        int(round(left * scale_x)),
        int(round(top * scale_y)),
        max(1, int(round(width * scale_x))),
        max(1, int(round(height * scale_y))),
    )


def clamp_region(region, screen=None):
    """Recorta a regiao para dentro da tela.

    Sem isto o PIL preenche o que passa da borda com preto: era o que
    acontecia com screen_area = (0, 0, 1920, 1080) num monitor 1366x768.
    """
    screen_w, screen_h = screen or get_screen_size()
    left, top, width, height = (int(v) for v in region)
    right = min(left + max(width, 0), screen_w)
    bottom = min(top + max(height, 0), screen_h)
    left = max(0, min(left, screen_w))
    top = max(0, min(top, screen_h))
    return (left, top, max(0, right - left), max(0, bottom - top))


def expand_region(region, min_width, min_height, screen=None):
    """Cresce a regiao em torno do proprio centro ate caber o template com folga."""
    left, top, width, height = (int(v) for v in region)
    if width < min_width:
        left -= (min_width - width) // 2
        width = min_width
    if height < min_height:
        top -= (min_height - height) // 2
        height = min_height
    return clamp_region((left, top, width, height), screen)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
def load_template(path_image, scale):
    """Carrega o PNG em tons de cinza, ja redimensionado. O resultado fica em cache."""
    key = (os.path.abspath(path_image), round(float(scale), 3))
    if key in _template_cache:
        return _template_cache[key]

    image = cv2.imread(path_image, cv2.IMREAD_GRAYSCALE)
    if image is None:
        # Tolera caminhos com ponto/espaco sobrando no fim.
        cleaned = path_image.rstrip(". ")
        if cleaned != path_image:
            image = cv2.imread(cleaned, cv2.IMREAD_GRAYSCALE)
    if image is None:
        _template_cache[key] = None
        return None

    if abs(scale - 1.0) > 0.01:
        new_w = max(1, int(round(image.shape[1] * scale)))
        new_h = max(1, int(round(image.shape[0] * scale)))
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        image = cv2.resize(image, (new_w, new_h), interpolation=interpolation)

    _template_cache[key] = image
    return image


def match_scales(base=None):
    """
    Escalas testadas na busca, da mais provavel para a menos provavel.

    A escada precisa ser fina perto da escala nominal: a interface do jogo nao
    acompanha a resolucao de forma perfeitamente linear, e um erro de 2% ja
    derruba a correlacao de um icone de 60 px o bastante para perder o match.
    """
    base = image_scale() if base is None else base
    if abs(base - 1.0) < 0.02:
        factors = (1.0, 0.98, 1.02, 0.95, 1.05)
    else:
        factors = (1.0, 0.98, 1.02, 0.95, 1.05, 0.92, 1.08, 0.9, 1.1)
    scales = []
    for factor in factors:
        value = round(base * factor, 3)
        if value > 0 and value not in scales:
            scales.append(value)
    # Ultimo recurso: imagens que ja foram recortadas na escala da tela atual.
    if 1.0 not in scales:
        scales.append(1.0)
    return tuple(scales)


def grab_gray(region):
    """Screenshot da regiao em tons de cinza. Devolve (imagem, regiao_efetiva)."""
    region = clamp_region(region)
    if region[2] <= 0 or region[3] <= 0:
        return None, region

    array = np.array(pyautogui.screenshot(region=region))
    if array.ndim == 2:
        return array, region
    # pyautogui devolve RGB. Usar BGR2GRAY aqui trocava os canais R e B e
    # baixava a pontuacao do match contra templates lidos pelo cv2.imread.
    code = cv2.COLOR_RGBA2GRAY if array.shape[2] == 4 else cv2.COLOR_RGB2GRAY
    return cv2.cvtColor(array, code), region


def locate(path_image, region, show=False, threshold=0.8, scales=None):
    """
    Procura path_image dentro de region e devolve o centro em coordenadas de tela.

    Diferente da versao antiga, testa varias escalas: e isso que faz as imagens
    capturadas em Full HD serem encontradas num monitor HD.
    """
    if scales is None:
        scales = match_scales()

    biggest = None
    for scale in scales:
        template = load_template(path_image, scale)
        if template is None:
            continue
        if biggest is None or template.shape[0] * template.shape[1] > biggest[0] * biggest[1]:
            biggest = template.shape[:2]
    if biggest is None:
        print("[screen_utils] imagem de referencia nao pode ser lida: %s" % path_image, flush=True)
        return None

    search = expand_region(
        region,
        int(biggest[1] * _MIN_MATCH_REGION_RATIO),
        int(biggest[0] * _MIN_MATCH_REGION_RATIO),
    )
    screenshot, search = grab_gray(search)
    if screenshot is None:
        return None

    if show:
        cv2.imshow("screenshot", screenshot)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    best_margin = None
    best_location = None
    best_shape = None
    best_score = -1.0
    best_scale = None
    for scale in scales:
        template = load_template(path_image, scale)
        if template is None:
            continue
        height, width = template.shape[:2]
        if height > screenshot.shape[0] or width > screenshot.shape[1]:
            continue
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        # Regioes uniformes (o preto que sobra fora da tela) geram NaN aqui.
        result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
        _, max_value, _, max_location = cv2.minMaxLoc(result)

        # Templates redimensionados competem com um limiar um pouco menor.
        limit = threshold
        if abs(scale - 1.0) > 0.01:
            limit = max(0.0, threshold - SCALED_THRESHOLD_RELIEF)
        margin = max_value - limit

        if best_margin is None or margin > best_margin:
            best_margin = margin
            best_location = max_location
            best_shape = (height, width)
            best_score = max_value
            best_scale = scale
        if margin >= 0:
            break

    # Guarda o resultado da última busca para diagnóstico (quanto faltou para
    # bater o limiar, e em que escala foi o melhor palpite).
    last_match["path"] = path_image
    last_match["score"] = round(best_score, 4)
    last_match["scale"] = best_scale
    last_match["region"] = search
    last_match["hit"] = best_margin is not None and best_margin >= 0

    if best_location is None or best_margin < 0:
        return None

    center_x = best_location[0] + best_shape[1] // 2 + search[0]
    center_y = best_location[1] + best_shape[0] // 2 + search[1]
    return center_x, center_y


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
def parse_value(raw, default=None):
    """literal_eval tolerante, para os valores do config_crypt.cfg."""
    if raw is None:
        return default
    try:
        return ast.literal_eval(raw.strip())
    except Exception:
        return default


def get_config_version(config):
    if config.has_section("Settings") and config.has_option("Settings", "config_version"):
        try:
            return int(config.get("Settings", "config_version"))
        except ValueError:
            pass
    return 1


def _is_usable_region(region):
    return region is not None and len(region) == 4 and region[2] > 1 and region[3] > 1


def load_coordinates(config, screen=None, verbose=True):
    """
    Le [COORDINATES], converte o formato antigo e reescala tudo para a tela atual.

    A referencia da reescala e o screen_area gravado pela calibracao, ou seja,
    a resolucao em que aquelas coordenadas foram capturadas. Num monitor igual
    ao da calibracao o fator e 1.0 e nada muda.
    """
    if "COORDINATES" not in config:
        raise KeyError("COORDINATES")

    section = config["COORDINATES"]
    version = get_config_version(config)
    screen_w, screen_h = screen or get_screen_size()

    reference = parse_value(section.get("screen_area"))
    if reference and len(reference) == 4 and reference[2] > 0 and reference[3] > 0:
        ref_w, ref_h = int(reference[2]), int(reference[3])
    else:
        ref_w, ref_h = REFERENCE_RESOLUTION
    scale_x = screen_w / float(ref_w)
    scale_y = screen_h / float(ref_h)

    coords = {}

    for key in ("how_many_cripts", "how_many_speedups", "test", "rare_cript", "search_cript"):
        if key in section:
            coords[key] = parse_value(section[key])
    coords.setdefault("how_many_cripts", 0)
    coords.setdefault("how_many_speedups", 0)
    coords.setdefault("test", 0)
    coords.setdefault("rare_cript", False)
    coords.setdefault("search_cript", [])

    for key in POINT_KEYS:
        point = parse_value(section.get(key))
        if point and len(point) >= 2:
            coords[key] = scale_point(point, scale_x, scale_y)

    for key in REGION_KEYS:
        region = parse_value(section.get(key))
        if not region or len(region) != 4:
            continue
        if version < CONFIG_VERSION and key in LEGACY_CORNER_KEYS:
            region = corners_to_region(region)
        coords[key] = scale_region(region, scale_x, scale_y)

    center = parse_value(section.get("center_of_screen"))
    if center:
        coords["center_of_screen"] = [scale_point(p, scale_x, scale_y) for p in center]

    coords["screen_area"] = (0, 0, screen_w, screen_h)

    # any_cript: aceita True/False e tambem o formato booleano do configparser.
    any_cript = False
    if "any_cript" in section:
        parsed = parse_value(section["any_cript"])
        if isinstance(parsed, bool):
            any_cript = parsed
        else:
            any_cript = section.getboolean("any_cript", fallback=False)
    elif coords.get("search_cript") in (["any"], "any"):
        any_cript = True
    coords["any_cript"] = any_cript

    # A calibracao gravava a area do botao Explorar na chave errada
    # (verify_if_open_explorer_button), deixando cord_explore_button parado no
    # valor de Full HD. Usa a chave certa quando cord_explore_button nao serve.
    if not _is_usable_region(coords.get("cord_explore_button")):
        fallback = coords.get("verify_if_open_explorer_button")
        if _is_usable_region(fallback):
            coords["cord_explore_button"] = fallback
    if not _is_usable_region(coords.get("cord_explore_button")):
        coords["cord_explore_button"] = coords["screen_area"]

    # cord_click_go_cript nunca foi calibrado. A area do botao Go e, entao
    # clicar no centro dela mantem os dois em sincronia depois da calibracao.
    go_area = coords.get("area_menu_button_go_cript")
    if _is_usable_region(go_area):
        coords["cord_click_go_cript"] = (
            go_area[0] + go_area[2] // 2,
            go_area[1] + go_area[3] // 2,
        )

    if verbose:
        print(
            "[resolucao] tela %dx%d | calibrado em %dx%d (fator %.3fx%.3f) | "
            "escala das imagens %.3f | escala do Windows %.0f%% | config v%d"
            % (
                screen_w,
                screen_h,
                ref_w,
                ref_h,
                scale_x,
                scale_y,
                image_scale((screen_w, screen_h)),
                dpi_scale() * 100,
                version,
            ),
            flush=True,
        )

    return coords


def enable_line_buffering():
    """
    Faz os prints chegarem na janela de status na hora, e sem poder falhar.

    Dois problemas resolvidos aqui:

    * O processo filho escreve num pipe, e nesse caso o Python usa buffer de
      bloco de 8 KB: era por isso que a janela parava em "Iniciando script..."
      e so mostrava tudo de uma vez quando o processo morria.
    * O encoding padrao do console no Windows e cp1252. Um unico caractere
      fora dessa tabela (uma seta, reticencias tipograficas, um nome de janela
      qualquer) levantava UnicodeEncodeError dentro do print e derrubava o
      processo. utf-8 com errors="replace" torna o print infalivel.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            try:
                stream.reconfigure(line_buffering=True)
            except Exception:
                pass
