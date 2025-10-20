import os, sys
import tkinter as tk
from PIL import Image, ImageTk  # pillow is in requirements
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from MenuBar import create_menu_bar
from Master import MasterSheet
from TimeSheet import TimeSheet
from Distribution import DistributionTab
from AnalyseTab import AnalyseTab
from tkinter.simpledialog import askstring
from tkinter import messagebox
from Pay import PayTab
from AppConfig import (
    ensure_pdf_dir_selected,
    ensure_default_employee_files,
    get_last_auth_sync,
    get_supabase_settings,
    set_supabase_settings,
)
from updater import maybe_auto_check
from version import APP_NAME, APP_VERSION
from icon_helper import set_app_icon
from ui_scale import init_scaling, enable_high_dpi_awareness
from auth import AuthManager, SupabaseConfigurationError, SupabaseSyncError
from login import LoginDialog



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
    def __init__(self, root, auth_manager: AuthManager, login_context: dict):
        # --- Seed backend employee JSONs on first run (never overwrites valid files) ---
        ensure_default_employee_files()

        self.root = root
        self.auth_manager = auth_manager
        self.login_context = login_context or {}
        self.current_user = self.login_context.get("user")
        self.offline_mode = bool(self.login_context.get("offline"))
        self.last_sync = self.login_context.get("last_sync") or self.auth_manager.last_sync or get_last_auth_sync()

        title_suffix = f" - {self.current_user.email}" if self.current_user else ""
        self.root.title(f"{APP_NAME} v{APP_VERSION}{title_suffix}")
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

        # Gentle delayed update check
        self.root.after(2000, lambda: maybe_auto_check(self.root))

        # Notify user if offline and schedule periodic background syncs
        if self.offline_mode:
            messagebox.showwarning(
                "Mode hors ligne",
                "Connexion à Supabase impossible. Utilisation de la dernière liste d’utilisateurs synchronisée.",
            )
        self._schedule_periodic_sync()

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
        self.show_master_tab()

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

    # ----- Authentication helpers -----
    def retry_auth_sync(self):
        try:
            count = self.auth_manager.sync()
        except SupabaseConfigurationError:
            self.offline_mode = True
            messagebox.showerror(
                "Supabase non configuré",
                "Aucune URL ou service key Supabase n’est définie. Configurez-les avant de synchroniser.",
            )
            return
        except SupabaseSyncError as exc:
            self.offline_mode = True
            messagebox.showwarning(
                "Supabase hors ligne",
                f"Impossible de synchroniser les accès pour le moment.\n\n{exc}",
            )
            return

        self.offline_mode = False
        self.last_sync = self.auth_manager.last_sync
        messagebox.showinfo(
            "Synchronisation Supabase",
            f"Synchronisation terminée avec succès. ({count} utilisateurs)",
        )

    def show_auth_sync_info(self):
        last_sync = self.last_sync or get_last_auth_sync() or "Jamais"
        status = "hors ligne" if self.offline_mode else "connecté"
        messagebox.showinfo(
            "Statut Supabase",
            f"Dernière synchronisation: {last_sync}\nStatut actuel: {status}",
        )

    def configure_supabase(self):
        settings = get_supabase_settings()
        current_url = settings.get("url", "")
        new_url = askstring(
            "Configurer Supabase",
            "URL du projet Supabase (ex: https://xyz.supabase.co)",
            initialvalue=current_url,
            parent=self.root,
        )
        if new_url is None:
            return

        message = (
            "Service role key Supabase. Laissez vide pour conserver la valeur actuelle."
        )
        new_key = askstring(
            "Service role key",
            message,
            parent=self.root,
            show="•",
        )
        if new_key == "" or new_key is None:
            # Keep existing key if user leaves empty (None indicates cancel → already handled)
            new_key = settings.get("service_key", "") if new_key == "" else None
        if new_key is None:
            return

        set_supabase_settings(new_url, new_key)
        messagebox.showinfo("Supabase", "Paramètres enregistrés. Une synchronisation va être lancée.")
        self.retry_auth_sync()

    def get_last_sync_display(self) -> str:
        return self.last_sync or get_last_auth_sync() or "Jamais"

    def _schedule_periodic_sync(self):
        self.root.after(15 * 60 * 1000, self._periodic_sync)

    def _periodic_sync(self):
        previous_state = self.offline_mode
        try:
            count = self.auth_manager.sync()
            self.offline_mode = False
            self.last_sync = self.auth_manager.last_sync
            if previous_state:
                messagebox.showinfo(
                    "Connexion rétablie",
                    f"Synchronisation Supabase réussie ({count} utilisateurs).",
                )
        except SupabaseConfigurationError:
            self.offline_mode = True
            if not previous_state:
                messagebox.showwarning(
                    "Supabase non configuré",
                    "Aucun identifiant Supabase n’est défini. Configurez-les via Réglages.",
                )
        except SupabaseSyncError:
            self.offline_mode = True
            if not previous_state:
                messagebox.showwarning(
                    "Supabase hors ligne",
                    "Impossible de synchroniser les accès. Dernière liste en cache utilisée.",
                )
        finally:
            self._schedule_periodic_sync()


if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")

    # --- Splash screen before creating the main app ---
    splash_img_path = _resource_path("assets/images/loading.png")
    splash = show_splash(app_root, splash_img_path, duration_ms=2500)

    def start_main_app():
        # Ensure splash is gone
        if splash and splash.winfo_exists():
            splash.destroy()

        auth_manager = AuthManager()
        login_dialog = LoginDialog(app_root, auth_manager)
        app_root.wait_window(login_dialog.window)

        if not login_dialog.result:
            app_root.destroy()
            return

        context = login_dialog.result

        # Create the main app
        app = TipSplitApp(app_root, auth_manager, context)

    # Start the app after the splash duration
    app_root.after(2500, start_main_app)
    app_root.mainloop()
