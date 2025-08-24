import os, sys, platform
import tkinter as tk
from PIL import Image, ImageTk  # pillow is in requirements
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from MenuBar import create_menu_bar
from Master import MasterSheet
from TimeSheet import TimeSheet
from Distribution import DistributionTab
from tkinter.simpledialog import askstring
from tkinter import messagebox
from Pay import PayTab
from AppConfig import ensure_pdf_dir_selected, ensure_default_employee_files
from updater import maybe_auto_check
from version import APP_NAME, APP_VERSION


# ---------- Resource & Icon helpers (dev + PyInstaller) ----------
def _resource_path(relative_path: str) -> str:
    """
    Return absolute path to resource. Works for dev and for PyInstaller
    where data is unpacked to _MEIPASS.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def set_app_icon(root, keep_ref_container: dict | None = None):
    """
    Try platform-preferred icon first (.ico on Windows via iconbitmap),
    then fall back to a PNG via wm_iconphoto (cross‑platform).
    keep_ref_container keeps a reference to PhotoImage to avoid GC.
    """
    system = platform.system().lower()
    ico_path = _resource_path("assets/icons/app_icon.ico")
    png_path = _resource_path("assets/icons/app_icon.png")

    if system == "windows" and os.path.exists(ico_path):
        try:
            root.iconbitmap(ico_path)
            return
        except Exception:
            pass  # fall back to PNG

    if os.path.exists(png_path):
        try:
            photo = ImageTk.PhotoImage(Image.open(png_path))
            root.wm_iconphoto(True, photo)
            # prevent image from being garbage‑collected
            if keep_ref_container is not None:
                keep_ref_container["_app_icon_photo"] = photo
            else:
                root._app_icon_photo = photo
            return
        except Exception:
            pass
    # If neither worked, silently continue (no icon set).


# ---------- Splash / Loading screen ----------
def show_splash(root, image_path: str, duration_ms: int = 2500):
    """
    Show a splash/loading screen centered on the display for `duration_ms`.
    Returns the splash Toplevel (caller may destroy earlier if needed).
    """
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)   # no window borders
    try:
        splash.attributes("-topmost", True)
    except Exception:
        pass

    # Load image (fallback to text if not found/invalid)
    img = None
    if os.path.exists(image_path):
        try:
            img = Image.open(image_path)
            photo = ImageTk.PhotoImage(img)
            splash._photo_ref = photo  # avoid GC
            lbl = ttk.Label(splash, image=photo)
        except Exception:
            lbl = ttk.Label(splash, text="Chargement…", font=("Helvetica", 14, "bold"))
    else:
        lbl = ttk.Label(splash, text="Chargement…", font=("Helvetica", 14, "bold"))

    lbl.pack()

    # Determine size to center
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    if img:
        w, h = img.size
    else:
        # approximate label size after layout
        splash.update_idletasks()
        w = lbl.winfo_reqwidth()
        h = lbl.winfo_reqheight()

    x = (screen_w - w) // 2
    y = (screen_h - h) // 2
    splash.geometry(f"{w}x{h}+{x}+{y}")

    # Give splash an icon too (nice touch)
    try:
        _refs = {}
        set_app_icon(splash, _refs)
        splash._icon_refs = _refs
    except Exception:
        pass

    # Auto-close after duration
    root.after(duration_ms, lambda: splash.winfo_exists() and splash.destroy())
    return splash


class TipSplitApp:
    def __init__(self, root):
        # --- Seed backend employee JSONs on first run (never overwrites valid files) ---
        ensure_default_employee_files()

        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("800x850")

        self._icon_refs = {}  # keep a reference so Tk doesn't GC the image
        set_app_icon(self.root, self._icon_refs)

        # Ensure export folder is set
        ensure_pdf_dir_selected(self.root)

        self.shared_data = {}

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True)

        self.create_master_tab()
        self.create_timesheet_tab()
        self.create_distribution_tab()
        # Pay tab is shown via menu action; create on demand.
        # self.create_pay_tab()

        create_menu_bar(self.root, self)

        # Gentle delayed update check
        self.root.after(2000, lambda: maybe_auto_check(self.root))

    def create_master_tab(self):
        self.master_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.master_frame, text="Master Sheet")
        self.notebook.hide(self.master_frame)  # Hide the tab on startup
        self.master_tab = MasterSheet(
            self.master_frame,
            on_save_callback=self.reload_timesheet_data,
            shared_data=self.shared_data
        )

    def create_timesheet_tab(self):
        self.timesheet_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.timesheet_frame, text="Time Sheet")

        self.timesheet_tab = TimeSheet(
            self.timesheet_frame,
            shared_data=self.shared_data,
            reload_distribution_data=self.reload_distribution_tab
        )

    def create_distribution_tab(self):
        self.distribution_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.distribution_frame, text="Distribution")

        self.distribution_tab = DistributionTab(
            root=self.distribution_frame,
            shared_data=self.shared_data
        )
        self.shared_data["distribution_tab"] = self.distribution_tab

    def create_pay_tab(self):
        self.pay_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.pay_frame, text="Pay")
        self.pay_tab = PayTab(self.pay_frame)

    def authenticate_and_show_master(self):
        password = askstring("🔒 Accès restreint", "Entrez le mot de passe:")
        if password == "admin123":
            self.show_master_tab()
        else:
            messagebox.showerror("Erreur", "Mot de passe incorrect.")

    def show_master_tab(self):
        if str(self.master_frame) not in self.notebook.tabs():
            self.notebook.add(self.master_frame, text="Master Sheet")
        self.notebook.select(self.master_frame)

    def show_json_viewer_tab(self):
        if not hasattr(self, "json_viewer_tab"):
            from JsonViewerTab import JsonViewerTab
            self.json_viewer_frame = ttk.Frame(self.notebook)
            self.json_viewer_tab = JsonViewerTab(self.json_viewer_frame)
            self.notebook.add(self.json_viewer_frame, text="Modifier la distribution")
        elif str(self.json_viewer_frame) not in self.notebook.tabs():
            self.notebook.add(self.json_viewer_frame, text="Modifier la distribution")
        self.notebook.select(self.json_viewer_frame)

    def show_pay_tab(self):
        if not hasattr(self, "pay_tab"):
            self.pay_frame = ttk.Frame(self.notebook)
            self.pay_tab = PayTab(self.pay_frame)
            self.notebook.add(self.pay_frame, text="Pay")
        elif str(self.pay_frame) not in self.notebook.tabs():
            self.notebook.add(self.pay_frame, text="Pay")
        self.notebook.select(self.pay_frame)

    # ----- Cross-tab refresh hooks -----
    def reload_distribution_tab(self):
        if hasattr(self, "distribution_tab"):
            # Keep the method name used by your DistributionTab
            self.distribution_tab.load_day_sheet_data()

    def reload_timesheet_data(self):
        if hasattr(self, "timesheet_tab"):
            self.timesheet_tab.reload()


if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")

    # --- Splash screen before creating the main app ---
    splash_img_path = _resource_path("assets/images/loading.png")
    splash = show_splash(app_root, splash_img_path, duration_ms=2500)

    def start_main_app():
        # Ensure splash is gone
        if splash and splash.winfo_exists():
            splash.destroy()

        # Create the main app
        app = TipSplitApp(app_root)

        # Fit to screen after widgets exist
        def fit_to_screen(win):
            # Windows/Linux: maximize
            if win.tk.call('tk', 'windowingsystem') in ('x11', 'win32'):
                try:
                    win.state('zoomed')
                    return
                except Exception:
                    pass

            # macOS: fill the whole screen (no margins), not fullscreen
            if win.tk.call('tk', 'windowingsystem') == 'aqua':
                win.update_idletasks()  # ensure correct screen metrics
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                win.geometry(f"{sw}x{sh}+0+0")

        app_root.after(0, lambda: fit_to_screen(app_root))

    # Start the app after the splash duration
    app_root.after(2500, start_main_app)
    app_root.mainloop()
