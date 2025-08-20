# AppConfig.py
import json
import os
import platform
from tkinter import filedialog, messagebox

APP_NAME = "TipSplit"
CONFIG_FILENAME = "config.json"

DEFAULTS = {
    "exports_pdf_dir": "",        # ask the user on first run
    "exports_backend_dir": "",    # auto-set under app data
    "version": 1,
}

# ----------------------------
# Paths & filesystem helpers
# ----------------------------
def _appdata_base() -> str:
    system = platform.system().lower()
    if system == "windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(base, APP_NAME)
    elif system == "darwin":  # macOS
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    else:  # linux/others
        return os.path.join(os.path.expanduser("~/.config"), APP_NAME)

def _config_path() -> str:
    base = _appdata_base()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, CONFIG_FILENAME)

def _safe_mkdir(path: str):
    if path:
        os.makedirs(path, exist_ok=True)

def _expand_norm(path: str) -> str:
    if not path:
        return ""
    return os.path.normpath(os.path.expanduser(path))

# ----------------------------
# Load / Save config
# ----------------------------
def load_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        cfg = DEFAULTS.copy()
        # Initialize backend dir right away, under app data
        backend_dir = os.path.join(_appdata_base(), "backend")
        _safe_mkdir(backend_dir)
        cfg["exports_backend_dir"] = backend_dir
        save_config(cfg)
        return cfg

    with open(path, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except Exception:
            cfg = DEFAULTS.copy()

    # ensure required keys exist
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)

    # ensure backend dir exists
    if not cfg.get("exports_backend_dir"):
        backend_dir = os.path.join(_appdata_base(), "backend")
        _safe_mkdir(backend_dir)
        cfg["exports_backend_dir"] = backend_dir
        save_config(cfg)

    return cfg

def save_config(cfg: dict):
    path = _config_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# ----------------------------
# Public API (used by the app)
# ----------------------------
def ensure_pdf_dir_selected(root=None) -> str:
    """
    Ensure a PDF export directory exists. If missing, prompt the user to select one.
    Returns the directory path (string, possibly empty if user cancelled).
    """
    cfg = load_config()
    pdf_dir = _expand_norm(cfg.get("exports_pdf_dir", ""))

    if not pdf_dir or not os.path.isdir(pdf_dir):
        messagebox.showinfo(
            "Dossier d’exportation PDF requis",
            "Veuillez choisir un dossier pour enregistrer les exports PDF."
        )
        selected = filedialog.askdirectory(parent=root, title="Choisir le dossier d’exportation PDF")
        selected = _expand_norm(selected)
        if not selected:
            messagebox.showwarning(
                "Aucun dossier sélectionné",
                "Vous pourrez définir le dossier via le menu: Réglages → Dossier d’exportation PDF…"
            )
            selected = ""  # allow empty; user can set it later via settings
        else:
            _safe_mkdir(selected)

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
