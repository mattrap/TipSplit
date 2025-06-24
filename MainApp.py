import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from MenuBar import create_menu_bar
from Master import MasterSheet
from TimeSheet import TimeSheet
from DaySheet import DaySheet
from Distribution import DistributionTab

class TipSplitApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TipSplit")
        self.root.geometry("800x850")

        self.shared_data = {}

        create_menu_bar(self.root)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True)

        self.create_master_tab()
        self.create_timesheet_tab()
        self.create_daysheet_tab()
        self.create_distribution_tab()

    def create_master_tab(self):
        self.master_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.master_frame, text="Master Sheet")
        self.master_tab = MasterSheet(
            self.master_frame,
            on_save_callback=self.reload_timesheet_data,
            shared_data=self.shared_data
        )

    def create_timesheet_tab(self):
        self.timesheet_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.timesheet_frame, text="Time Sheet")
        self.timesheet_tab = None  # Will be set in create_daysheet_tab

    def create_daysheet_tab(self):
        self.daysheet_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.daysheet_frame, text="Day Sheet")
        self.daysheet_tab = DaySheet(self.daysheet_frame)

        self.timesheet_tab = TimeSheet(
            self.timesheet_frame,
            shared_data=self.shared_data,
            day_sheet=self.daysheet_tab,
            reload_distribution_data=self.reload_distribution_tab  # Live link
        )

    def create_distribution_tab(self):
        self.distribution_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.distribution_frame, text="Distribution")

        data = []
        section = ""
        for item in self.daysheet_tab.tree.get_children():
            values = self.daysheet_tab.tree.item(item)["values"]
            if values[1].startswith("---"):
                section = values[1].strip("- ").strip()
                continue
            data.append({
                "section": section,
                "number": values[0],
                "name": values[1],
                "points": values[2],
                "hours": values[5]
            })

        self.distribution_tab = DistributionTab(
            root=self.distribution_frame,
            shared_data=self.shared_data,
            day_sheet_data=data
        )

    def reload_distribution_tab(self):
        if hasattr(self, "distribution_tab") and hasattr(self.daysheet_tab, "tree"):
            data = []
            section = ""
            for item in self.daysheet_tab.tree.get_children():
                values = self.daysheet_tab.tree.item(item)["values"]
                if values[1].startswith("---"):
                    section = values[1].strip("- ").strip()
                    continue
                data.append({
                    "section": section,
                    "number": values[0],
                    "name": values[1],
                    "points": values[2],
                    "hours": values[5]
                })

            selected_date = self.daysheet_tab.title_label.cget("text").replace("Feuille du ", "")
            self.distribution_tab.load_day_sheet_data(data, selected_date=selected_date)

    def reload_timesheet_data(self):
        if hasattr(self, "timesheet_tab"):
            self.timesheet_tab.reload()

if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")
    app = TipSplitApp(app_root)
    app_root.mainloop()
