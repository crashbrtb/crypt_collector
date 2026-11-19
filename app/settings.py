"""
Configuração do aplicativo (config.json), alterada pela interface.

  lanes        as 3 faixas (um capitão cada): família, nível, imagens escolhidas, quantidade,
               armaduras e artefato
  presets      seleções salvas com nome, para repetir as criptas com os mesmos capitães
  tar_learned  dano por alcatrão medido de cada capitão ("capitão:item" -> dano)
  artifact_map último mapa de artefatos visto nas respostas do jogo
"""

import copy
import json
import os
from typing import Any, Dict, List, NamedTuple

from .logger import logger
from .paths import CONFIG_FILE

LANGUAGES = {"pt": "Português", "en": "English"}
LOCALES = {"pt": "pt_BR", "en": "en_US"}
MAX_LANES = 3
SEARCH_MODES = ("spyglass", "scan")


def empty_lane() -> Dict[str, Any]:
    return {"enabled": False, "captain": None, "kind": "epic", "level": 0, "groups": [], "quantity": 10,
            "gear": [None, None, None], "artifact": None, "fallback": None}


DEFAULTS: Dict[str, Any] = {
    "language": "pt",
    "browser": {
        "cdp_port": 9222,
        "game_url": "https://totalbattle.com/",
        "url_filter": "totalbattle",
        "executable_path": "",
        "profile_dir": "",
    },
    "run": {
        "search_mode": "spyglass",
        "search_radius": 150,
        "search_every": 30,
        "max_checks": 8,
        "check_marches": True,
        "min_time_left": 180,
        "speedup": True,
        "speedups_per_march": 5,
        "speedup_min_left": 25,
        "tar_margin": 1.25,
        "tick": 2.0,
        "track_every": 4,
        "march_timeout": 1800,
        "freeze_seconds": 90,
        "reload_wait": 120,
        "restart_wait": 240,
        "max_recoveries": 10,
        "max_errors": 5,
    },
    "lanes": [empty_lane() for _ in range(MAX_LANES)],
    "presets": {},
    "tar_learned": {},
    "artifact_map": {},
}


class Field(NamedTuple):
    section: str
    key: str
    type: str       # int | float | str | bool | choice


# Parâmetros da aba "Parâmetros". Rótulo e ajuda vêm do i18n: "param.<seção>.<chave>[.help]".
FIELDS: List[Field] = [
    Field("run", "search_mode", "choice"),
    Field("run", "search_radius", "int"),
    Field("run", "search_every", "int"),
    Field("run", "check_marches", "bool"),
    Field("run", "min_time_left", "int"),
    Field("run", "speedup", "bool"),
    Field("run", "speedups_per_march", "int"),
    Field("run", "tar_margin", "float"),
    Field("run", "march_timeout", "int"),
    Field("run", "freeze_seconds", "int"),
    Field("run", "reload_wait", "int"),
    Field("run", "restart_wait", "int"),
    Field("run", "max_recoveries", "int"),
    Field("browser", "cdp_port", "int"),
    Field("browser", "game_url", "str"),
    Field("browser", "executable_path", "str"),
    Field("browser", "profile_dir", "str"),
]
CHOICES = {("run", "search_mode"): SEARCH_MODES}

_CASTS = {"int": int, "float": float, "str": str}
_OBSOLETE = ("timing", "vision")           # da versão 2.x (cliques na tela)
_OBSOLETE_RUN = ("mode", "selected", "crypt_count")


class Settings:
    def __init__(self, path: str = CONFIG_FILE):
        self.path = path
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning(f"config.json could not be read ({exc}); using defaults.")
            return
        for key, value in stored.items():
            if key in _OBSOLETE:
                continue
            if isinstance(value, dict) and isinstance(self.data.get(key), dict) and key in ("browser", "run"):
                self.data[key].update(value)
            else:
                self.data[key] = value
        for k in _OBSOLETE_RUN:
            self.data["run"].pop(k, None)
        if self.data.get("language") not in LANGUAGES:
            self.data["language"] = DEFAULTS["language"]
        lanes = [dict(empty_lane(), **(ln or {})) for ln in (self.data.get("lanes") or [])][:MAX_LANES]
        self.data["lanes"] = lanes + [empty_lane() for _ in range(MAX_LANES - len(lanes))]

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.error(f"config.json could not be written: {exc}")

    # ------------------------------------------------------------------ acesso
    @property
    def language(self) -> str:
        return self.data.get("language", "pt")

    @language.setter
    def language(self, value: str):
        if value in LANGUAGES:
            self.data["language"] = value

    @property
    def locale(self) -> str:
        return LOCALES.get(self.language, "en_US")

    def section(self, name: str) -> Dict[str, Any]:
        return self.data.setdefault(name, {})

    def get(self, section: str, key: str) -> Any:
        return self.data.get(section, {}).get(key, DEFAULTS.get(section, {}).get(key))

    def set(self, section: str, key: str, value: Any):
        self.section(section)[key] = value

    def set_field(self, field: Field, raw) -> None:
        """Grava um valor digitado na interface. Levanta ValueError se não for do tipo esperado."""
        if field.type == "bool":
            self.set(field.section, field.key, bool(raw))
            return
        if field.type == "choice":
            if raw not in CHOICES[(field.section, field.key)]:
                raise ValueError(raw)
            self.set(field.section, field.key, raw)
            return
        text = str(raw).strip()
        if field.type == "float":
            text = text.replace(",", ".")
        value = _CASTS[field.type](text)
        if field.type != "str" and value < 0:
            raise ValueError(raw)
        self.set(field.section, field.key, value)

    # ------------------------------------------------------------------ presets
    def save_preset(self, name: str):
        self.data.setdefault("presets", {})[name] = {"lanes": copy.deepcopy(self.data["lanes"])}

    def load_preset(self, name: str) -> bool:
        p = (self.data.get("presets") or {}).get(name)
        if not p:
            return False
        lanes = [dict(empty_lane(), **ln) for ln in p.get("lanes", [])][:MAX_LANES]
        self.data["lanes"] = lanes + [empty_lane() for _ in range(MAX_LANES - len(lanes))]
        return True

    def delete_preset(self, name: str):
        (self.data.get("presets") or {}).pop(name, None)
