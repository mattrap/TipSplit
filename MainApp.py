import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from MenuBar import create_menu_bar
from Master import MasterSheet
from TimeSheet import TimeSheet
from Distribution import DistributionTab
from tkinter.simpledialog import askstring
from tkinter import messagebox

class TipSplitApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TipSplit")
        self.root.geometry("800x850")

        self.shared_data = {}

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True)

        self.create_master_tab()
        self.create_timesheet_tab()
        self.create_distribution_tab()

        create_menu_bar(self.root, self)

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

    def reload_distribution_tab(self):
        if hasattr(self, "distribution_tab"):
            self.distribution_tab.load_day_sheet_data()

    def reload_timesheet_data(self):
        if hasattr(self, "timesheet_tab"):
            self.timesheet_tab.reload()

if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")
    app = TipSplitApp(app_root)

    def fit_to_screen(win):
        # Windows/Linux: maximize
        if win.tk.call('tk', 'windowingsystem') in ('x11', 'win32'):
            try:
                win.state('zoomed')
                return
            except:
                pass

        # macOS: fill the whole screen (no margins), not fullscreen
        if win.tk.call('tk', 'windowingsystem') == 'aqua':
            win.update_idletasks()  # ensure correct screen metrics
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            win.geometry(f"{sw}x{sh}+0+0")

    app_root.after(0, lambda: fit_to_screen(app_root))
    app_root.mainloop()
