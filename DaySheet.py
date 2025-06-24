import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json

class DaySheet:
    def __init__(self, root):
        self.root = root
        self.title_label = None

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        top_frame = ttk.Frame(container)
        top_frame.pack(fill=X, pady=(0, 10))

        self.title_label = ttk.Label(top_frame, text="Feuille du: aucune date", font=("Helvetica", 14, "bold"))
        self.title_label.pack(side=LEFT)

        self.tree = ttk.Treeview(
            container,
            columns=("number", "name", "points", "in", "out", "hours"),
            show="headings",
            bootstyle="info"
        )

        for col in ("number", "name", "points", "in", "out", "hours"):
            self.tree.heading(col, text=col.capitalize())

        self.tree.column("number", width=100, anchor=CENTER)
        self.tree.column("name", width=200, anchor=W)
        self.tree.column("points", width=80, anchor=CENTER)
        self.tree.column("in", width=80, anchor=CENTER)
        self.tree.column("out", width=80, anchor=CENTER)
        self.tree.column("hours", width=80, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)

        # Bold for section headers like "Service" and "Bussboy"
        self.tree.tag_configure("section", font=("Helvetica", 10, "bold"))

    def load_data(self, data, selected_date=None):
        self.tree.delete(*self.tree.get_children())

        if selected_date:
            self.title_label.config(text=f"Feuille du {selected_date}")
        else:
            self.title_label.config(text="Feuille du: aucune date")

        last_section = None
        for entry in data:
            section = entry.get("section", "")
            if section != last_section:
                self.tree.insert("", "end", values=("", f"--- {section} ---", "", "", "", ""), tags=("section",))
                last_section = section

            self.tree.insert("", "end", values=(
                entry.get("number", ""),
                entry.get("name", ""),
                entry.get("points", ""),
                entry.get("in", ""),
                entry.get("out", ""),
                entry.get("hours", "")
            ))
