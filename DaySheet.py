import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json
import os

EXPORT_FILE = "DaySheet.json"

class DaySheet:
    def __init__(self, root):
        self.root = root
        self.title_label = None

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        # Header with Title Only
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=X, pady=(0, 10))

        self.title_label = ttk.Label(top_frame, text="Feuille du: aucune date", font=("Helvetica", 14, "bold"))
        self.title_label.pack(side=LEFT)

        self.tree = ttk.Treeview(
            container,
            columns=("number", "name", "points", "hours"),
            show="headings",
            bootstyle="info"
        )
        for col in ("number", "name", "points", "hours"):
            self.tree.heading(col, text=col.capitalize())

        self.tree.column("number", width=100, anchor=CENTER)
        self.tree.column("name", width=200, anchor=W)
        self.tree.column("points", width=100, anchor=CENTER)
        self.tree.column("hours", width=100, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)

    def load_data(self, data, selected_date=None):
        self.tree.delete(*self.tree.get_children())

        if selected_date:
            self.title_label.config(text=f"Feuille du {selected_date}")
        else:
            self.title_label.config(text="Feuille du: aucune date")

        for entry in data:
            self.tree.insert("", "end", values=(
                entry.get("number", ""),
                entry.get("name", ""),
                entry.get("points", ""),
                entry.get("hours", "")
            ))
