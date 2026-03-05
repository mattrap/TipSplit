# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import re
import subprocess
from pathlib import Path
from sys import platform

from PyInstaller.utils.hooks import collect_data_files


def _git_tag_version() -> str:
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            "Release build requires an exact git tag like v1.2.3. "
            "No exact tag was found for this commit."
        ) from exc

    if not re.fullmatch(r"v\\d+\\.\\d+\\.\\d+", tag):
        raise RuntimeError(
            f"Invalid tag format: {tag!r}. Expected vX.Y.Z (e.g., v1.2.3)."
        )
    return tag[1:]


def _set_app_version(version: str) -> None:
    version_path = Path(__file__).with_name("app_version.py")
    text = version_path.read_text(encoding="utf-8")
    updated = re.sub(
        r'APP_VERSION\\s*=\\s*\"[^\"]*\"',
        f'APP_VERSION = \"{version}\"',
        text,
        count=1,
    )
    if updated == text:
        raise RuntimeError("APP_VERSION not found in app_version.py")
    if updated != text:
        version_path.write_text(updated, encoding="utf-8")


_set_app_version(_git_tag_version())

a = Analysis(
    ['MainApp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('supabase.env', '.'),
        # include icons and splash images
        ('assets/icons/*', 'assets/icons'),
        ('assets/images/*', 'assets/images'),
    ] + collect_data_files('ttkbootstrap') + collect_data_files('certifi'),
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
    [],
    exclude_binaries=True,
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

if platform == 'darwin':
    app = BUNDLE(
        exe,
        name='TipSplit.app',
        icon='assets/icons/app_icon.icns',
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='TipSplit',
    )
