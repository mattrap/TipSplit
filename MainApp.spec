# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files
from sys import platform

a = Analysis(
    ['MainApp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('supabase.env', '.'),
        # include icons and splash images
        ('assets/icons/*', 'assets/icons'),
        ('assets/images/*', 'assets/images'),
    ] + collect_data_files('ttkbootstrap'),
    hiddenimports=['PyPDF2'],
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
    name='TipSplit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # GUI app; no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/app_icon.icns' if platform == 'darwin' else 'assets/icons/app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TipSplit',
)
