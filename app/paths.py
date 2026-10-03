"""
Onde ficam os arquivos do aplicativo.

Dois diretórios diferentes quando empacotado pelo PyInstaller:
  APP_DIR    - onde fica o docrypt.exe. É o lugar de tudo o que o aplicativo
               escreve (configuração, calibração, logs, perfil do navegador) e
               que precisa sobreviver a uma reinstalação.
  BUNDLE_DIR - onde o PyInstaller extrai os 'datas' (a partir da versão 6 é a
               subpasta _internal). É onde estão as imagens e o arquivo VERSION.
"""

import os
import sys

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VERSION_FILE = os.path.join(BUNDLE_DIR, "VERSION")
ICON_FILE = os.path.join(BUNDLE_DIR, "Logo-crypt.ico")

IMAGES_DIR = os.path.join(BUNDLE_DIR, "images")
CRYPT_IMAGES_DIR = os.path.join(IMAGES_DIR, "cript")
FALLBACK_CLOSE_IMAGE = os.path.join(IMAGES_DIR, "x.png")

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
LEGACY_CONFIG_FILE = os.path.join(APP_DIR, "config_crypt.cfg")
CALIBRATION_FILE = os.path.join(APP_DIR, "calibration.json")
CALIBRATION_REFS_DIR = os.path.join(APP_DIR, "calib_refs")
LOG_DIR = os.path.join(APP_DIR, "logs")
BROWSER_PROFILE_DIR = os.path.join(APP_DIR, "browser_profile")
