#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "app_version.py"
LEGACY_VERSION_FILE = ROOT / "version.py"
APP_NAME = "TipSplit"


def _git_tag() -> str | None:
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if tag.lower().startswith("v"):
            tag = tag[1:]
        return tag or None
    except Exception:
        return None


def main() -> None:
    version = _git_tag()
    if not version:
        raise SystemExit("No git tag found. Tag a release like v1.2.3.")

    content = (
        '"""Application identity and semantic version."""\n\n'
        f'APP_NAME = "{APP_NAME}"\n'
        f'APP_VERSION = "{version}"\n'
    )
    VERSION_FILE.write_text(content, encoding="utf-8")

    # Keep a compatibility shim for older imports.
    LEGACY_VERSION_FILE.write_text(
        '"""Backward-compatible shim for legacy imports."""\n\n'
        'from app_version import APP_NAME, APP_VERSION\n\n'
        '__all__ = ["APP_NAME", "APP_VERSION"]\n',
        encoding="utf-8",
    )
    print(version)


if __name__ == "__main__":
    main()
