import os, sys
import tkinter as tk
from PIL import Image, ImageTk  # pillow is in requirements
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.style import Style
from MenuBar import create_menu_bar
from Master import MasterSheet
from TimeSheet import TimeSheet
from Distribution import DistributionTab
from AnalyseTab import AnalyseTab
from tkinter.simpledialog import askstring
from tkinter import messagebox
from Pay import PayTab
from AppConfig import ensure_pdf_dir_selected, ensure_default_employee_files
from updater import maybe_auto_check
from version import APP_NAME, APP_VERSION
from icon_helper import set_app_icon
from ui_scale import init_scaling, enable_high_dpi_awareness
from access_control import AccessController, AccessError
from ui.login_dialog import LoginDialog



# ---------- Resource & Icon helpers (dev + PyInstaller) ----------
def _resource_path(relative_path: str) -> str:
    """
    Return absolute path to resource. Works for dev and for PyInstaller
    where data is unpacked to _MEIPASS.
    """
    base_path = getattr(
        sys,
        "_MEIPASS",
        os.path.dirname(os.path.abspath(__file__)),
    )
    return os.path.join(base_path, relative_path)


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

def fit_to_screen(win):
    """Adjust the given window to fill the screen cross‑platform."""
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


class TipSplitApp:
    def __init__(self, root, user_role: str = "user"):
        # --- Seed backend employee JSONs on first run (never overwrites valid files) ---
        ensure_default_employee_files()

        self.root = root
        self.user_role = user_role or "user"
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        # Configure DPI-aware scaling so the UI looks consistent across displays
        init_scaling(self.root)

        # Start with a size relative to the screen and immediately fit to screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{int(sw * 0.8)}x{int(sh * 0.85)}")
        fit_to_screen(self.root)

        self._icon_refs = {}  # keep a reference so Tk doesn't GC the image
        set_app_icon(self.root, self._icon_refs)

        # Ensure export folder is set
        ensure_pdf_dir_selected(self.root)

        # Initialize shared data with validation
        self.shared_data = {}
        self._initialize_shared_data()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True)

        self.create_master_tab()
        self.create_timesheet_tab()
        self.create_distribution_tab()
        

        create_menu_bar(self.root, self)

        self.role_var = tk.StringVar(value=f"Role: {self.user_role}")
        self.role_label = ttk.Label(
            self.root,
            textvariable=self.role_var,
            anchor="w",
            bootstyle="secondary",
        )
        self.role_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Gentle delayed update check
        self.root.after(2000, lambda: maybe_auto_check(self.root))

    def _initialize_shared_data(self):
        """Initialize shared data structure with validation and error handling"""
        try:
            # Initialize transfer data structure
            self.shared_data.setdefault("transfer", {})
            
            # Initialize other shared data structures
            self.shared_data.setdefault("employee_data", {})
            self.shared_data.setdefault("pay_periods", {})
            
            # Validate existing data if any
            self._validate_shared_data()
            
        except Exception as e:
            print(f"⚠️ Warning: Error initializing shared data: {e}")
            # Ensure basic structure exists even if validation fails
            self.shared_data = {
                "transfer": {},
                "employee_data": {},
                "pay_periods": {}
            }

    def _validate_shared_data(self):
        """Validate and repair shared data structure if needed"""
        try:
            # Validate transfer data
            transfer = self.shared_data.get("transfer", {})
            if not isinstance(transfer, dict):
                print("⚠️ Repairing invalid transfer data structure")
                self.shared_data["transfer"] = {}
            
            # Validate entries if they exist
            entries = transfer.get("entries", [])
            if entries and not isinstance(entries, list):
                print("⚠️ Repairing invalid entries structure")
                self.shared_data["transfer"]["entries"] = []
            
            # Validate date if they exist
            date = transfer.get("date", "")
            if date and not isinstance(date, str):
                print("⚠️ Repairing invalid date structure")
                self.shared_data["transfer"]["date"] = ""
                
        except Exception as e:
            print(f"⚠️ Warning: Error validating shared data: {e}")

    def _safe_shared_data_access(self, key, default=None):
        """Safely access shared data with error handling"""
        try:
            return self.shared_data.get(key, default)
        except Exception as e:
            print(f"⚠️ Warning: Error accessing shared data key '{key}': {e}")
            return default

    def _safe_shared_data_set(self, key, value):
        """Safely set shared data with error handling"""
        try:
            self.shared_data[key] = value
            return True
        except Exception as e:
            print(f"⚠️ Warning: Error setting shared data key '{key}': {e}")
            return False

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

    def create_analyse_tab(self):
        self.analyse_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analyse_frame, text="Analyse")
        self.analyse_tab = AnalyseTab(self.analyse_frame)

    def show_analyse_tab(self):
        if not hasattr(self, "analyse_tab"):
            self.create_analyse_tab()
        elif str(self.analyse_frame) not in self.notebook.tabs():
            self.notebook.add(self.analyse_frame, text="Analyse")
        self.notebook.select(self.analyse_frame)

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
            self.notebook.add(self.json_viewer_frame, text="Confirmer les distribution")
        elif str(self.json_viewer_frame) not in self.notebook.tabs():
            self.notebook.add(self.json_viewer_frame, text="Confrimer les distribution")
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


def main():
    enable_high_dpi_awareness()
    try:
        controller = AccessController()
    except AccessError as exc:
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror("Configuration error", str(exc))
        temp_root.destroy()
        return

    login = LoginDialog(
        sign_in_callback=controller.sign_in,
        app_name=APP_NAME,
        themename="flatly",
        accent="primary",
    )
    login.mainloop()
    if not login.result:
        controller.stop()
        return

    # Reset bootstrap style singleton before creating a new root window
    Style.instance = None

    app_root = ttk.Window(themename="flatly")

    splash_img_path = _resource_path("assets/images/loading.png")
    splash = show_splash(app_root, splash_img_path, duration_ms=2500)

    def on_close():
        controller.stop()
        if app_root.winfo_exists():
            app_root.destroy()

    def handle_revocation(reason: str):
        if not app_root.winfo_exists():
            return
        messagebox.showerror("Access revoked", reason)
        on_close()

    def start_main_app():
        if splash and splash.winfo_exists():
            splash.destroy()
        app_root._tipsplit_app = TipSplitApp(app_root, user_role=controller.role or "user")
        if splash and splash.winfo_exists():
            splash.destroy()

    app_root.protocol("WM_DELETE_WINDOW", on_close)
    app_root.after(2500, start_main_app)

    controller.start_heartbeat(handle_revocation, tk_widget=app_root)

    try:
        app_root.mainloop()
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
