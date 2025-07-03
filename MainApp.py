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

    def reload_distribution_tab(self):
        if hasattr(self, "distribution_tab"):
            self.distribution_tab.load_day_sheet_data()

    def reload_timesheet_data(self):
        if hasattr(self, "timesheet_tab"):
            self.timesheet_tab.reload()

if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")
    app_root.state('zoomed')
    app = TipSplitApp(app_root)
    app_root.mainloop()
