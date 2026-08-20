# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Mapeia dinamicamente as DLLs do pywin32 do ambiente virtual em uso
venv_path = os.path.dirname(os.path.dirname(sys.executable))
pywin32_dlls = os.path.join(venv_path, 'Lib', 'site-packages', 'pywin32_system32')

binaries_list = []
if os.path.exists(pywin32_dlls):
    binaries_list.append((os.path.join(pywin32_dlls, '*.dll'), '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_list,
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

        # pywin32 completos para suporte a impressão e win32com
        'win32print',
        'win32api',
        'win32com',
        'win32gui',
        'win32con',

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
    [],
    exclude_binaries=True,
    name='Vex - Gestor de Pedidos',
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
    uac_admin=True,  # Solcita elevação de Administrador para I/O de impressão
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Vex - Gestor de Pedidos',
)