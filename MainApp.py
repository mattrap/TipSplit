import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from MenuBar import create_menu_bar
from Master import MasterSheet
from TimeSheet import TimeSheet
from DaySheet import DaySheet

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
        self.create_daysheet_tab()  # Now placed after Time Sheet

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

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
        # Temporarily create an empty DaySheet reference, filled after creation
        self.timesheet_tab = None  # Placeholder

    def create_daysheet_tab(self):
        self.daysheet_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.daysheet_frame, text="Day Sheet")
        self.daysheet_tab = DaySheet(self.daysheet_frame)

        # Now that DaySheet exists, create TimeSheet and pass reference
        self.timesheet_tab = TimeSheet(
            self.timesheet_frame,
            shared_data=self.shared_data,
            day_sheet=self.daysheet_tab
        )

    def reload_timesheet_data(self):
        if hasattr(self, "timesheet_tab"):
            self.timesheet_tab.reload()

    def on_tab_changed(self, event):
        selected_tab = event.widget.select()
        tab_text = event.widget.tab(selected_tab, "text")
        if tab_text == "Time Sheet" and hasattr(self, "timesheet_tab"):
            self.timesheet_tab.reload()

if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")
    app = TipSplitApp(app_root)
    app_root.mainloop()
