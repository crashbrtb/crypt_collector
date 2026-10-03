# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

# A versão do executável é a do arquivo VERSION, o mesmo que o aplicativo lê.
APP_VERSION = open('VERSION', encoding='utf-8').read().strip()

a = Analysis(
    ['docrypt.py'],
    pathex=[],
    binaries=[],
    # customtkinter carrega os temas (json) e as fontes de dentro do pacote.
    datas=[('images', 'images'), ('VERSION', '.'), ('Logo-crypt.ico', '.')] + collect_data_files('customtkinter'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='docrypt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    # Evita o diálogo modal de traceback de um exe windowed; o traceback vai
    # para logs/crypt_collector.log (ver docrypt.py).
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Logo-crypt.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='docrypt',
)
