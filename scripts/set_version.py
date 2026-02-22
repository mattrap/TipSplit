#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "version.py"
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

    content = f"# version.py\nAPP_NAME = \"{APP_NAME}\"\nAPP_VERSION = \"{version}\"\n"
    VERSION_FILE.write_text(content, encoding="utf-8")
    print(version)


if __name__ == "__main__":
    main()
