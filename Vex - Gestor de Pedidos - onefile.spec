# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('Icon.ico', '.')],
    hiddenimports=[
        # CustomTkinter
        'customtkinter',

        # Tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',

        # Pillow
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageOps',

        # tkcalendar
        'tkcalendar',
        'tkcalendar.calendar_',
        'tkcalendar.dateentry',

        # Flask
        'flask',
        'waitress',

        # pywin32
        'win32print',
        'win32api',

        # Módulos do próprio VEX
        'styles',
        'database',
        'utils',
        'printer',
        'server',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='VEX - Gestor de Comandas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Icon.ico'],
)