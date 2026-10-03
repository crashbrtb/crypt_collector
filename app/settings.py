"""
Configuração do aplicativo (config.json).

Tudo o que antes era editado à mão no config_crypt.cfg está aqui e é alterado
pela interface. As coordenadas não: elas vivem em calibration.json e são
gravadas pelo assistente de calibração.
"""

import ast
import configparser
import copy
import json
import os
from typing import Any, Dict, List, NamedTuple

from .logger import logger
from .paths import CONFIG_FILE, LEGACY_CONFIG_FILE

LANGUAGES = {"pt": "Português", "en": "English"}
CRYPT_TYPES = ("common", "epic", "rare")
ANY_MODE = "any"

DEFAULTS: Dict[str, Any] = {
    "language": "pt",
    "browser": {
        "cdp_port": 9222,
        "game_url": "https://totalbattle.com/",
        "url_filter": "totalbattle.com",
        "executable_path": "",
    },
    "run": {
        "mode": "epic",
        "selected": [],
        "crypt_count": 5,
        "speedups_per_march": 5,
    },
    "timing": {
        "click_delay": 1.5,
        "scroll_delta": 100,
        "max_scrolls": 80,
        "list_passes": 3,
        "march_timeout": 1800,
    },
    "vision": {
        "match_threshold": 0.80,
        "scaled_threshold_relief": 0.06,
    },
}


class Field(NamedTuple):
    section: str
    key: str
    type: str       # int | float | str


# Parâmetros exibidos na aba "Parâmetros". Rótulo e ajuda vêm do i18n, pelas
# chaves "param.<seção>.<chave>" e "param.<seção>.<chave>.help".
FIELDS: List[Field] = [
    Field("run", "speedups_per_march", "int"),
    Field("timing", "click_delay", "float"),
    Field("timing", "scroll_delta", "int"),
    Field("timing", "max_scrolls", "int"),
    Field("timing", "list_passes", "int"),
    Field("timing", "march_timeout", "int"),
    Field("vision", "match_threshold", "float"),
    Field("browser", "cdp_port", "int"),
    Field("browser", "game_url", "str"),
    Field("browser", "executable_path", "str"),
]

_CASTS = {"int": int, "float": float, "str": str}


class Settings:
    def __init__(self, path: str = CONFIG_FILE):
        self.path = path
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    # ------------------------------------------------------------ persistência
    def load(self):
        if not os.path.exists(self.path):
            self._import_legacy()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning(f"config.json could not be read ({exc}); using defaults.")
            return
        for key, value in stored.items():
            if isinstance(value, dict) and isinstance(self.data.get(key), dict):
                self.data[key].update(value)
            else:
                self.data[key] = value
        if self.data.get("language") not in LANGUAGES:
            self.data["language"] = DEFAULTS["language"]

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error(f"config.json could not be written: {exc}")

    def _import_legacy(self):
        """
        Aproveita as preferências do config_crypt.cfg da versão 1.x.

        Só idioma, quantidades e seleção. As coordenadas ficam para trás: eram
        posições na tela do cliente instalado e não significam nada no navegador.
        """
        if not os.path.exists(LEGACY_CONFIG_FILE):
            return
        legacy = configparser.ConfigParser()
        try:
            legacy.read(LEGACY_CONFIG_FILE, encoding="utf-8")
        except (configparser.Error, OSError, UnicodeDecodeError):
            return

        language = legacy.get("Settings", "language", fallback="")
        if language in LANGUAGES:
            self.data["language"] = language

        run = self.data["run"]
        for old, new in (("how_many_cripts", "crypt_count"), ("how_many_speedups", "speedups_per_march")):
            try:
                run[new] = max(1, int(legacy.get("COORDINATES", old)))
            except (configparser.Error, ValueError):
                pass

        try:
            selected = ast.literal_eval(legacy.get("COORDINATES", "search_cript", fallback="[]"))
        except (ValueError, SyntaxError):
            selected = []
        if selected == ["any"] or legacy.get("COORDINATES", "any_cript", fallback="") == "True":
            run["mode"] = ANY_MODE
        elif isinstance(selected, list):
            # "images/cript/epic/3.png" -> "epic/3.png"
            names = ["/".join(str(item).replace("\\", "/").split("/")[-2:]) for item in selected]
            names = [name for name in names if name.split("/")[0] in CRYPT_TYPES]
            if names:
                run["selected"] = names
                run["mode"] = names[0].split("/")[0]

    # ------------------------------------------------------------------ acesso
    @property
    def language(self) -> str:
        return self.data.get("language", "pt")

    @language.setter
    def language(self, value: str):
        if value in LANGUAGES:
            self.data["language"] = value

    def section(self, name: str) -> Dict[str, Any]:
        return self.data.setdefault(name, {})

    def get(self, section: str, key: str) -> Any:
        return self.data.get(section, {}).get(key, DEFAULTS.get(section, {}).get(key))

    def set(self, section: str, key: str, value: Any):
        self.section(section)[key] = value

    def set_field(self, field: Field, raw: str):
        """Grava um valor digitado na interface. Levanta ValueError se não for do tipo esperado."""
        text = str(raw).strip()
        if field.type == "float":
            text = text.replace(",", ".")
        value = _CASTS[field.type](text)
        if field.type != "str" and value < 0:
            raise ValueError(raw)
        self.set(field.section, field.key, value)
