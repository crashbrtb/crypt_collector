"""
Onde ficam os arquivos do aplicativo.

Dois diretórios diferentes quando empacotado pelo PyInstaller:
  APP_DIR    - onde fica o docrypt.exe. É o lugar de tudo o que o aplicativo
               escreve (configuração, dados do jogo em cache, logs, perfil do
               navegador) e que precisa sobreviver a uma reinstalação.
  BUNDLE_DIR - onde o PyInstaller extrai os 'datas' (a partir da versão 6 é a
               subpasta _internal). É onde estão o ícone e o arquivo VERSION.
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

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
LOG_DIR = os.path.join(APP_DIR, "logs")
BROWSER_PROFILE_DIR = os.path.join(APP_DIR, "browser_profile")

# Dados do jogo baixados dos CDNs públicos: tabelas estáticas, traduções e imagens.
DATA_DIR = os.path.join(APP_DIR, "data")
STATIC_DIR = os.path.join(DATA_DIR, "static")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
