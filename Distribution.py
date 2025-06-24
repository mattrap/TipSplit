
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class DistributionTab:
    def __init__(self, root, shared_data=None, day_sheet_data=None):
        self.root = root
        self.shared_data = shared_data or {}
        self.day_sheet_data = day_sheet_data or []

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        # Input section
        input_frame = ttk.LabelFrame(container, text="Paramètres de distribution", padding=10)
        input_frame.pack(fill=X, pady=(0, 10))

        self.fields = {}
        labels = ["Ventes Nettes", "Dépot Net", "Frais Admin", "Cash"]
        for i, label in enumerate(labels):
            ttk.Label(input_frame, text=label + ":", font=("Helvetica", 10)).grid(row=i, column=0, sticky=W, pady=5)
            entry = ttk.Entry(input_frame, width=20)
            entry.grid(row=i, column=1, sticky=W, pady=5)
            self.fields[label] = entry

        # DaySheet data section
        self.tree = ttk.Treeview(
            container,
            columns=("number", "name", "points", "hours"),
            show="headings",
            bootstyle="info"
        )

        for col in ("number", "name", "points", "hours"):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=100, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)
        self.tree.tag_configure("section", font=("Helvetica", 10, "bold"))

        self.load_day_sheet_data(self.day_sheet_data)

    def load_day_sheet_data(self, data):
        self.tree.delete(*self.tree.get_children())

        last_section = None
        for entry in data:
            section = entry.get("section", "")
            if section != last_section:
                self.tree.insert("", "end", values=("", f"--- {section} ---", "", "", "", ""), tags=("section",))
                last_section = section

            self.tree.insert("", "end", values=(entry.get("number", ""), entry.get("name", ""), entry.get("points", ""), entry.get("hours", "")))
