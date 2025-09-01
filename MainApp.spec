# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['MainApp.py'],
    pathex=[],
    binaries=[],
    datas=[
        # include employee defaults
        ('defaults/*.json', 'defaults'),
        # include icons and splash images
        ('assets/icons/*', 'assets/icons'),
        ('assets/images/*', 'assets/images'),
    ] + collect_data_files('ttkbootstrap'),
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
    console=True,   # set False if you don’t want a console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/app_icon.ico',
)
