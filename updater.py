# updater.py
import os, sys, json, tempfile, hashlib, subprocess, time, webbrowser
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from tkinter import messagebox
from typing import Optional, Dict, Any, Tuple, List

from app_version import APP_NAME, APP_VERSION
from AppConfig import get_auto_check_updates, load_config

GITHUB_OWNER = "mattrap"
GITHUB_REPO  = "TipSplit"

API_LATEST    = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
API_RELEASES  = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
RELEASES_URL  = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# Name of the Inno installer asset on GitHub Releases (no version in filename)
INSTALLER_FILENAME = "TipSplit-Setup.exe"

HTTP_TIMEOUT = 30

# ---------- Helpers ----------
def _norm_version(v: str) -> Tuple[int, ...]:
    v = v.strip()
    if v.lower().startswith("v"):
        v = v[1:]
    parts: List[int] = []
    for p in v.split("."):
        p2 = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(p2) if p2 else 0)
    return tuple(parts)

def _http_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": APP_NAME})
    with urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

def _http_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": APP_NAME})
    with urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")

def _http_download(url: str, out_path: str) -> None:
    req = Request(url, headers={"User-Agent": APP_NAME})
    with urlopen(req, timeout=HTTP_TIMEOUT) as r, open(out_path, "wb") as f:
        while True:
            chunk = r.read(1024 * 64)
            if not chunk:
                break
            f.write(chunk)

def _pick_release(cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    stable: use /releases/latest
    beta:   use first non-draft from /releases (includes prereleases)
    """
    channel = (cfg.get("update_channel") or "stable").lower()
    if channel == "beta":
        rels = _http_json(API_RELEASES)
        if not isinstance(rels, list):
            return None
        for rel in rels:
            if not rel.get("draft"):
                return rel
        return None
    else:
        return _http_json(API_LATEST)

def _find_asset_urls(assets: list, target_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (installer_url, installer_name, sha256_url)
    - installer: exact matching filename
    - sha256: file named "<installer>.sha256" or any *.sha256 that mentions installer name
    """
    installer_url = installer_name = sha_url = None
    for a in assets or []:
        name = a.get("name") or ""
        url  = a.get("browser_download_url")
        if not url:
            continue
        if name.lower() == target_name.lower():
            installer_url, installer_name = url, name
            break
    if installer_name:
        # try exact "<installer>.sha256" first
        exact = installer_name + ".sha256"
        for a in assets or []:
            name = a.get("name") or ""
            url  = a.get("browser_download_url")
            if name == exact:
                sha_url = url
                break
        if not sha_url:
            # fallback: any *.sha256 that mentions installer name
            for a in assets or []:
                name = a.get("name") or ""
                url  = a.get("browser_download_url")
                if name.lower().endswith(".sha256") and installer_name in name:
                    sha_url = url
                    break
    return installer_url, installer_name, sha_url

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _verify_sha256(file_path: str, sha256_text: str) -> bool:
    # Accept "HASH  filename" or just "HASH"
    first = sha256_text.strip().split()[0].lower()
    return _sha256(file_path).lower() == first

def _run_installer_silent(installer_path: str) -> None:
    """
    Inno Setup silent upgrade with app close/restart.
    Requires [Setup] CloseApplications=yes, RestartApplications=yes in installer.iss
    """
    args = [
        installer_path,
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/CLOSEAPPLICATIONS",
        "/RESTARTAPPLICATIONS",
        "/NORESTART",
    ]
    # Launch detached; let installer close us and relaunch
    subprocess.Popen(args, shell=False)

# ---------- Public API ----------
def check_for_update(parent=None, silent_if_current: bool = False, auto: bool = False):
    """
    - If newer found, asks user unless auto=True (then proceeds without prompt).
    - If same/newer, shows 'up to date' unless silent_if_current=True.
    """
    try:
        cfg = load_config()
        rel = _pick_release(cfg)
        if not rel:
            raise RuntimeError("Impossible d'obtenir la version la plus récente.")

        tag = (rel.get("tag_name") or rel.get("name") or "").strip()
        if not tag:
            raise RuntimeError("Version distante invalide.")
        tag_norm = tag[1:] if tag.lower().startswith("v") else tag

        if _norm_version(tag_norm) <= _norm_version(APP_VERSION):
            if not silent_if_current:
                messagebox.showinfo("Mise à jour", f"{APP_NAME} est à jour (v{APP_VERSION}).", parent=parent)
            return

        assets = rel.get("assets") or []
        inst_url, inst_name, sha_url = _find_asset_urls(assets, INSTALLER_FILENAME)

        if not inst_url:
            # Couldn’t auto-find the installer; open releases page
            if auto:
                # In auto mode, avoid surprise browser pop; just inform.
                messagebox.showwarning(
                    "Mise à jour",
                    "Une nouvelle version est disponible mais l’installateur n’a pas été trouvé automatiquement.",
                    parent=parent
                )
                return
            messagebox.showinfo("Téléchargement", "Ouverture de la page des versions.", parent=parent)
            webbrowser.open(RELEASES_URL)
            return

        # Confirm unless auto
        proceed = True
        if not auto:
            proceed = messagebox.askyesno(
                "Mise à jour disponible",
                f"Nouvelle version: {tag}\nVersion actuelle: v{APP_VERSION}\n\n"
                "Installer maintenant ?",
                parent=parent,
            )
        if not proceed:
            return

        tmpdir = tempfile.mkdtemp(prefix=f"{APP_NAME}-upd-")
        inst_path = os.path.join(tmpdir, inst_name)

        _http_download(inst_url, inst_path)

        if sha_url:
            try:
                sha_txt = _http_text(sha_url)
                if not _verify_sha256(inst_path, sha_txt):
                    messagebox.showerror("Mise à jour", "Vérification SHA-256 échouée. Abandon.")
                    return
            except Exception:
                # If checksum fetch fails, we can still proceed, or you can choose to abort.
                pass

        # Run silent upgrade and exit current app
        _run_installer_silent(inst_path)
        # Give Tk a moment to process UI, then quit hard to let installer replace files
        try:
            time.sleep(0.5)
            if parent is not None:
                try:
                    parent.quit()
                except Exception:
                    pass
        finally:
            os._exit(0)

    except (HTTPError, URLError) as e:
        if not silent_if_current:
            messagebox.showerror("Mise à jour", f"Impossible de vérifier les mises à jour.\n{e}", parent=parent)
    except Exception as e:
        if not silent_if_current:
            messagebox.showerror("Mise à jour", f"Erreur pendant la mise à jour.\n{e}", parent=parent)

def maybe_auto_check(parent=None):
    try:
        if get_auto_check_updates():
            # Silent if already current; auto=True to skip prompt when newer exists
            check_for_update(parent=parent, silent_if_current=True, auto=True)
    except Exception:
        # Never block startup on update errors
        pass
