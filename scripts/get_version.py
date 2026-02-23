#!/usr/bin/env python3
import subprocess
from pathlib import Path

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def _git_tag() -> str | None:
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=_repo_root(),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if tag.lower().startswith("v"):
            tag = tag[1:]
        return tag or None
    except Exception:
        return None

def _version_py() -> str | None:
    root = _repo_root()
    version_path = root / "app_version.py"
    if not version_path.exists():
        version_path = root / "version.py"
    if not version_path.exists():
        return None
    namespace: dict[str, object] = {}
    exec(version_path.read_text(encoding="utf-8"), namespace)
    version = namespace.get("APP_VERSION")
    return str(version) if version else None

def main() -> None:
    version = _git_tag() or _version_py() or "0.0.0"
    print(version)

if __name__ == "__main__":
    main()
