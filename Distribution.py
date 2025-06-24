import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class DistributionTab:
    def __init__(self, root, shared_data=None, day_sheet_data=None):
        self.root = root
        self.shared_data = shared_data or {}
        self.day_sheet_data = day_sheet_data or []

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        top_frame = ttk.Frame(container)
        top_frame.pack(fill=X)

        self.date_label = ttk.Label(top_frame, text="", font=("Helvetica", 10, "bold"))
        self.date_label.pack(side=RIGHT)

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

            if label == "Ventes Nettes":
                entry.bind("<KeyRelease>", lambda e: self.update_bussboy_info())

        self.bussboy_label = ttk.Label(input_frame, text="", font=("Helvetica", 10, "bold"))
        self.bussboy_label.grid(row=0, column=2, rowspan=4, padx=(20, 0), sticky=N)

        # Treeview
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

    def load_day_sheet_data(self, data, selected_date=None):
        self.tree.delete(*self.tree.get_children())
        if selected_date:
            self.date_label.config(text=f"Feuille du {selected_date}")

        last_section = None
        for entry in data:
            section = entry.get("section", "")
            if section != last_section:
                self.tree.insert("", "end", values=("", f"--- {section} ---", "", ""), tags=("section",))
                last_section = section

            self.tree.insert("", "end", values=(
                entry.get("number", ""),
                entry.get("name", ""),
                entry.get("points", ""),
                entry.get("hours", "")
            ))

        self.update_bussboy_info()

    def update_bussboy_info(self):
        bussboy_count = 0
        in_bussboy_section = False

        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            name = values[1]

            if name.startswith("---"):
                in_bussboy_section = "Bussboy" in name
                continue

            if in_bussboy_section and values[0] != "" and values[1] != "":
                bussboy_count += 1

        percentage = 0.0 if bussboy_count == 0 else 0.02 + (max(bussboy_count - 1, 0) * 0.005)

        try:
            ventes_net_str = self.fields["Ventes Nettes"].get()
            ventes_net = float(ventes_net_str) if ventes_net_str else 0.0
        except ValueError:
            ventes_net = 0.0

        amount = ventes_net * percentage

        self.bussboy_label.config(
            text=f"Bussboys: {bussboy_count} bussboys, ({percentage * 100:.1f}%) = {amount:.2f}$"
        )

