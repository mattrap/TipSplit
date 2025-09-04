import os, sys, platform
from PIL import Image, ImageTk


def _resource_path(relative_path: str) -> str:
    """Return absolute path to resource for dev and PyInstaller."""
    base_path = getattr(
        sys,
        "_MEIPASS",
        os.path.dirname(os.path.abspath(__file__)),
    )
    return os.path.join(base_path, relative_path)


def set_app_icon(root, keep_ref_container: dict | None = None):
    """Set the application icon on a Tk window.

    Both ICO and PNG variants are applied so the icon displays in the
    window title bar *and* the Windows taskbar/alt-tab switcher. Optional
    ``keep_ref_container`` keeps a reference to ``PhotoImage`` to avoid GC.
    """
    system = platform.system().lower()
    ico_path = _resource_path("assets/icons/app_icon.ico")
    png_path = _resource_path("assets/icons/app_icon.png")

    # First try to set the PNG icon via wm_iconphoto (works cross-platform).
    if os.path.exists(png_path):
        try:
            photo = ImageTk.PhotoImage(Image.open(png_path))
            root.wm_iconphoto(True, photo)
            if keep_ref_container is not None:
                keep_ref_container["_app_icon_photo"] = photo
            else:
                root._app_icon_photo = photo
        except Exception:
            pass

    # On Windows also set the ICO so the executable carries the icon.
    if system == "windows" and os.path.exists(ico_path):
        try:
            root.iconbitmap(ico_path)
        except Exception:
            pass
    # If neither worked, silently continue (no icon set).
