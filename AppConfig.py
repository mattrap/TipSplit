# AppConfig.py  — drop-in replacement
# Safe locations for installers, supports portable mode, versioned schema, and robust dialogs.

from __future__ import annotations
import json
import os
import sys
import platform
import tempfile
import shutil
import time
from typing import Dict, Any, Tuple

try:
    # Import lazily-safe: these may be unavailable in headless contexts
    from tkinter import filedialog, messagebox, Tk
except Exception:  # pragma: no cover
    filedialog = None
    messagebox = None
    Tk = None

APP_NAME = "TipSplit"
CONFIG_FILENAME = "config.json"

# Increment when you change the schema; migrate in _migrate_config()
SCHEMA_VERSION = 2

DEFAULTS: Dict[str, Any] = {
    "exports_pdf_dir": "",        # ask the user on first run
    "exports_backend_dir": "",    # auto-set under app data
    "version": SCHEMA_VERSION,

    # New since v2 (future-proofing)
    "update_channel": "stable",   # stable / beta (if you add channels later)
    "auto_check_updates": True,
}

# ----------------------------
# Portable mode detection
# ----------------------------
def _is_portable() -> bool:
    """Portable if TIPSLIT_PORTABLE=1 or a 'portable.flag' file sits next to the executable/script."""
    if os.environ.get("TIPSLIT_PORTABLE", "").strip() == "1":
        return True
    try:
        base = _program_base()
        return os.path.isfile(os.path.join(base, "portable.flag"))
    except Exception:
        return False

def _program_base() -> str:
    """Folder where the executable or the main script resides."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.dirname(sys.executable)
    # Fallback for non-frozen
    return os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__))

# ----------------------------
# Resource helpers (dev + PyInstaller)
# ----------------------------
def _resource_base() -> str:
    """
    Base folder for read-only app resources.
    - In PyInstaller: sys._MEIPASS
    - In dev: project root (near your script)
    """
    return getattr(sys, "_MEIPASS", _program_base())

def _resource_path(relative_path: str) -> str:
    return os.path.join(_resource_base(), relative_path)

# ----------------------------
# Paths & filesystem helpers
# ----------------------------
def _user_data_base() -> str:
    """User-writable base for data (AppData/Library/.config) unless portable."""
    if _is_portable():
        base = os.path.join(_program_base(), "data")
        os.makedirs(base, exist_ok=True)
        return base

    system = platform.system().lower()
    if system == "windows":
        # %APPDATA% is roaming and fine for user configs; LOCALAPPDATA also possible
        base = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
        return os.path.join(base, APP_NAME)
    elif system == "darwin":  # macOS
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    else:  # linux/others
        return os.path.join(os.path.expanduser("~/.config"), APP_NAME)

def _config_path() -> str:
    base = _user_data_base()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, CONFIG_FILENAME)

def _safe_mkdir(path: str):
    if path:
        os.makedirs(path, exist_ok=True)

def _expand_norm(path: str) -> str:
    if not path:
        return ""
    return os.path.normpath(os.path.expanduser(path))

def _atomic_write_json(path: str, data: Dict[str, Any]):
    tmp_dir = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".cfg_", dir=tmp_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise

def _load_json_or_none(path: str):
    """
    Try to load JSON file and return the parsed data.
    Returns None if file is missing or corrupt. If corrupt, the bad file is backed up.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # backup corrupt file and treat as missing
        ts = time.strftime("%Y%m%d-%H%M%S")
        try:
            os.replace(path, f"{path}.bak-{ts}")
        except Exception:
            pass
        return None

# ----------------------------
# Migration
# ----------------------------
def _migrate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate cfg to the latest schema. Always return a dict with 'version' == SCHEMA_VERSION."""
    version = int(cfg.get("version") or 1)

    # -> v2: add update prefs if missing
    if version < 2:
        cfg.setdefault("update_channel", DEFAULTS["update_channel"])
        cfg.setdefault("auto_check_updates", DEFAULTS["auto_check_updates"])
        version = 2

    cfg["version"] = SCHEMA_VERSION
    return cfg

# ----------------------------
# Load / Save config
# ----------------------------
def load_config() -> Dict[str, Any]:
    path = _config_path()
    if not os.path.exists(path):
        cfg = DEFAULTS.copy()
        # Initialize backend dir right away, under user data base
        backend_dir = os.path.join(_user_data_base(), "backend")
        _safe_mkdir(backend_dir)
        cfg["exports_backend_dir"] = backend_dir
        _atomic_write_json(path, cfg)
        return cfg

    # Read file
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise ValueError("Config must be a JSON object.")
    except Exception:
        # Backup the broken file and start fresh
        try:
            broken = f"{path}.broken"
            shutil.copy2(path, broken)
        except Exception:
            pass
        cfg = DEFAULTS.copy()

    # Fill defaults
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)

    # Ensure backend dir exists
    if not cfg.get("exports_backend_dir"):
        backend_dir = os.path.join(_user_data_base(), "backend")
        _safe_mkdir(backend_dir)
        cfg["exports_backend_dir"] = backend_dir

    # Migrate schema if needed
    cfg = _migrate_config(cfg)

    # Persist any fixes
    save_config(cfg)
    return cfg

def save_config(cfg: Dict[str, Any]):
    path = _config_path()
    _atomic_write_json(path, cfg)

# ----------------------------
# Backend employee files (public API)
# ----------------------------
def get_backend_dir() -> str:
    return _expand_norm(load_config().get("exports_backend_dir", ""))

def set_backend_dir(new_dir: str):
    """
    Allow changing the internal backend folder (where raw JSONs live).
    """
    new_dir = _expand_norm(new_dir)
    cfg = load_config()
    cfg["exports_backend_dir"] = new_dir
    if new_dir:
        _safe_mkdir(new_dir)
    save_config(cfg)

def get_employee_files() -> Tuple[str, str]:
    """
    Returns the current (read/write) employee JSON paths in the backend.
    Always call this rather than hard-coding filenames so it respects set_backend_dir().
    """
    backend = get_backend_dir()
    service_path = os.path.join(backend, "service_employees.json")
    bussboy_path = os.path.join(backend, "bussboy_employees.json")
    return service_path, bussboy_path

def ensure_default_employee_files(defaults_subdir: str = "defaults") -> None:
    """
    Seed (or self-heal) backend employee files from read-only bundled defaults.

    Behavior:
      - If backend file is missing or corrupt -> copy from defaults.
      - If backend file exists and is valid JSON -> leave it alone (never overwrite).
      - Works in dev and PyInstaller via _resource_path().

    Ship these with your app:
      defaults/service_employees.json
      defaults/bussboy_employees.json
    """
    backend_dir = get_backend_dir()
    _safe_mkdir(backend_dir)

    svc_path, bus_path = get_employee_files()

    # Locations of bundled defaults (read-only in the app bundle)
    default_service_src = _resource_path(os.path.join(defaults_subdir, "service_employees.json"))
    default_bussboy_src = _resource_path(os.path.join(defaults_subdir, "bussboy_employees.json"))

    # Service
    if _load_json_or_none(svc_path) is None:
        # If default is missing (developer mistake), fall back to a minimal template
        if os.path.exists(default_service_src):
            shutil.copyfile(default_service_src, svc_path)
        else:
            _atomic_write_json(svc_path, [
                [1, "SERVEUR À REMPLIR 1", 7, ""],
                [2, "SERVEUR À REMPLIR 2", 7, ""]
            ])

    # Bussboy
    if _load_json_or_none(bus_path) is None:
        if os.path.exists(default_bussboy_src):
            shutil.copyfile(default_bussboy_src, bus_path)
        else:
            _atomic_write_json(bus_path, [
                [101, "BUSSBOY À REMPLIR 1", 3, ""],
                [102, "BUSSBOY À REMPLIR 2", 3, ""]
            ])

# ----------------------------
# Public API (used by the app) — PDF export dir
# ----------------------------
def ensure_pdf_dir_selected(root=None) -> str:
    """
    Ensure a PDF export directory exists. If missing, prompt the user to select one.
    Returns the directory path (string, possibly empty if user cancelled).
    """
    cfg = load_config()
    pdf_dir = _expand_norm(cfg.get("exports_pdf_dir", ""))

    if not pdf_dir or not os.path.isdir(pdf_dir):
        # Show dialogs only if tkinter is available
        if messagebox and filedialog:
            # Create a temporary hidden root if none is provided
            temp_root = None
            try:
                if root is None and Tk is not None:
                    temp_root = Tk()
                    temp_root.withdraw()
                messagebox.showinfo(
                    "Dossier d’exportation PDF requis",
                    "Veuillez choisir un dossier pour enregistrer les exports PDF.",
                    parent=root or temp_root
                )
                selected = filedialog.askdirectory(parent=root or temp_root, title="Choisir le dossier d’exportation PDF")
            finally:
                if temp_root is not None:
                    temp_root.destroy()
        else:
            # Headless fallback: default to a subfolder under user data
            selected = os.path.join(_user_data_base(), "pdf_exports")

        selected = _expand_norm(selected)
        if selected:
            _safe_mkdir(selected)
        else:
            # Allow empty; user can set it later via settings
            pass

        cfg["exports_pdf_dir"] = selected
        save_config(cfg)
        return selected

    return pdf_dir

def get_pdf_dir() -> str:
    return _expand_norm(load_config().get("exports_pdf_dir", ""))

def set_pdf_dir(new_dir: str):
    new_dir = _expand_norm(new_dir)
    cfg = load_config()
    cfg["exports_pdf_dir"] = new_dir
    if new_dir:
        _safe_mkdir(new_dir)
    save_config(cfg)

# ----------------------------
# Handy extras for a shipped app
# ----------------------------
def is_portable_mode() -> bool:
    return _is_portable()

def open_config_folder():
    """Open the folder where config lives (useful for a menu item)."""
    path = _user_data_base()
    try:
        if platform.system().lower() == "windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system().lower() == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2&>1 &')
    except Exception:
        pass

def reset_to_defaults():
    """Reset config to factory defaults but preserve existing folders on disk."""
    cfg = DEFAULTS.copy()
    backend_dir = os.path.join(_user_data_base(), "backend")
    _safe_mkdir(backend_dir)
    cfg["exports_backend_dir"] = backend_dir
    save_config(cfg)

def get_auto_check_updates() -> bool:
    return bool(load_config().get("auto_check_updates", True))

def set_auto_check_updates(enabled: bool):
    cfg = load_config()
    cfg["auto_check_updates"] = bool(enabled)
    save_config(cfg)
