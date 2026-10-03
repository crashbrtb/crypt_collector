# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['docrypt.py'],
    pathex=[],
    binaries=[],
    datas=[('images', 'images'), ('config_crypt.cfg', '.')],
    hiddenimports=['screen_utils', 'language'],
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
    # Evita o diálogo modal de traceback, que num processo lançado com
    # CREATE_NO_WINDOW ninguém veria. Atenção: isto NÃO resolve travamento.
    # Medido: um exe windowed com exceção não tratada fica vivo indefinidamente
    # com esta flag em True *ou* False. Quem garante o encerramento é o
    # try/except + os._exit() em volta de cada modo no docrypt.py.
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icone.ico'],
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
