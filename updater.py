# updater.py
import os, json, webbrowser, tempfile
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from tkinter import messagebox
from typing import Optional, Dict, Any

from version import APP_NAME, APP_VERSION
from AppConfig import get_auto_check_updates, load_config

# -------- EDIT THESE 2 LINES --------
GITHUB_OWNER = "mattrap"
GITHUB_REPO  = "TipSplit"
# ------------------------------------

API_LATEST   = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
API_RELEASES = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

def _cmp_versions(a: str, b: str) -> int:
    def parts(v): return [int(x) for x in v.strip().lstrip("v").split(".")]
    A, B = parts(a), parts(b)
    while len(A) < len(B): A.append(0)
    while len(B) < len(A): B.append(0)
    return (A > B) - (A < B)

def _http_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": APP_NAME})
    with urlopen(req, timeout=15) as r:
        return json.load(r)

def _pick_release(cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    channel = (cfg.get("update_channel") or "stable").lower()
    if channel == "beta":
        # include pre-releases
        rels = _http_json(API_RELEASES)
        if not isinstance(rels, list):
            return None
        for rel in rels:
            # first item is most recent (pre or stable)
            return rel
        return None
    else:
        # stable only
        return _http_json(API_LATEST)

def _find_windows_asset(assets, version: str) -> Optional[str]:
    target = f"{APP_NAME}-Setup-{version}.exe"
    for a in assets or []:
        if a.get("name") == target and a.get("browser_download_url"):
            return a["browser_download_url"]
    return None

def check_for_update(parent=None, silent_if_current=False):
    try:
        cfg = load_config()
        rel = _pick_release(cfg)
        if not rel:
            raise RuntimeError("Impossible d'obtenir la version la plus récente.")

        tag = (rel.get("tag_name") or rel.get("name") or "").lstrip("v")
        if not tag:
            raise RuntimeError("Version distante invalide.")

        cmp = _cmp_versions(tag, APP_VERSION)
        if cmp <= 0:
            if not silent_if_current:
                messagebox.showinfo("Mise à jour", f"{APP_NAME} est à jour (v{APP_VERSION}).", parent=parent)
            return

        # Newer available
        if messagebox.askyesno(
            "Mise à jour disponible",
            f"Nouvelle version disponible: v{tag}\n"
            f"Version actuelle: v{APP_VERSION}\n\n"
            "Voulez-vous télécharger et installer maintenant?",
            parent=parent
        ):
            asset_url = _find_windows_asset(rel.get("assets"), tag)
            if not asset_url:
                # Fallback to releases page
                messagebox.showinfo("Téléchargement", "Ouverture de la page des versions.", parent=parent)
                webbrowser.open(RELEASES_URL)
                return

            # Download installer to temp and run
            req = Request(asset_url, headers={"User-Agent": APP_NAME})
            with urlopen(req, timeout=120) as r:
                data = r.read()

            fd, path = tempfile.mkstemp(prefix=f"{APP_NAME}-", suffix=f"-{tag}.exe")
            os.close(fd)
            with open(path, "wb") as f:
                f.write(data)

            os.startfile(path)  # type: ignore[attr-defined]

    except (HTTPError, URLError) as e:
        messagebox.showerror("Mise à jour", f"Impossible de vérifier les mises à jour.\n{e}", parent=parent)
    except Exception as e:
        messagebox.showerror("Mise à jour", f"Erreur pendant la mise à jour.\n{e}", parent=parent)

def maybe_auto_check(parent=None):
    try:
        if get_auto_check_updates():
            # silent if already up-to-date
            check_for_update(parent=parent, silent_if_current=True)
    except Exception:
        # Never block startup on update errors
        pass
