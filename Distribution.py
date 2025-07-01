import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json

class DistributionTab:
    def __init__(self, root, shared_data=None):
        self.root = root
        self.shared_data = shared_data or {}
        self.selected_date_str = ""

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        # Top container with date label and toggle buttons stacked
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=X)

        self.date_label = ttk.Label(top_frame, text="FEUILLE DU:", font=("Helvetica", 14, "bold"))
        self.date_label.pack(anchor=W)

        # Toggle buttons
        self.shift_var = ttk.StringVar(value="")

        toggle_frame = ttk.Frame(top_frame)
        toggle_frame.pack(anchor=W, pady=5)

        self.matin_button = ttk.Button(
            toggle_frame, text="Matin", bootstyle="outline-primary", width=10,
            command=lambda: self.set_shift("Matin")
        )
        self.soir_button = ttk.Button(
            toggle_frame, text="Soir", bootstyle="outline-primary", width=10,
            command=lambda: self.set_shift("Soir")
        )

        self.matin_button.pack(side=LEFT, padx=5)
        self.soir_button.pack(side=LEFT, padx=5)

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

            if label in {"Ventes Nettes", "Dépot Net"}:
                entry.bind("<KeyRelease>", lambda e: self.process())

        self.create_bussboy_summary_panel(input_frame)

        # Treeview
        self.tree = ttk.Treeview(
            container,
            columns=("number", "name", "points", "hours", "sur_paye", "cash"),
            show="headings",
            bootstyle="info"
        )

        headers = {
            "number": "Number",
            "name": "Name",
            "points": "Points",
            "hours": "Hours",
            "sur_paye": "Sur paye",
            "cash": "Cash"
        }

        for col in self.tree["columns"]:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=100, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)
        self.tree.tag_configure("section", font=("Helvetica", 10, "bold"))

        # Load data from day_data.json
        day_data, selected_date = self.load_day_data()
        self.load_day_sheet_data(day_data, selected_date)

    def create_bussboy_summary_panel(self, parent):
        # Frame container
        bussboy_frame = ttk.LabelFrame(parent, text="BUSSBOY", padding=(10, 5))
        bussboy_frame.grid(row=0, column=2, rowspan=4, padx=(20, 0), sticky=N)

        # Percentage label
        self.bussboy_percentage_label = ttk.Label(bussboy_frame, text="Pourcentage: 0.00%", font=("Helvetica", 11, "bold"), foreground="#000000")
        self.bussboy_percentage_label.pack(anchor=W, pady=(5, 2))

        # Amount label
        self.bussboy_amount_label = ttk.Label(bussboy_frame, text="Montant: 0.00 $", font=("Helvetica", 11, "bold"), foreground="#0d6efd")
        self.bussboy_amount_label.pack(anchor=W, pady=(2, 2))

        # Cash label
        self.bussboy_cash_label = ttk.Label(bussboy_frame, text="Cash: 0.00 $", font=("Helvetica", 11, "bold"), foreground="#28a745")
        self.bussboy_cash_label.pack(anchor=W, pady=(2, 5))

    def load_day_data(self):
        try:
            with open("DaySheet.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return [], "aucune date"

        entries = data.get("entries", [])
        selected_date = data.get("date", "aucune date")

        organized_data = []
        last_section = None
        for entry in entries:
            section = entry.get("section", "")
            if section != last_section:
                organized_data.append({
                    "section": section,
                    "number": "",
                    "name": f"--- {section} ---",
                    "points": "",
                    "in": "",
                    "out": "",
                    "hours": "",
                    "is_section": True
                })
                last_section = section

            entry["is_section"] = False
            organized_data.append(entry)

        return organized_data, selected_date

    def set_shift(self, value):
        self.shift_var.set(value)

        if value == "Matin":
            self.matin_button.config(bootstyle="primary")
            self.soir_button.config(bootstyle="outline-primary")
        elif value == "Soir":
            self.matin_button.config(bootstyle="outline-primary")
            self.soir_button.config(bootstyle="primary")

        if self.selected_date_str:
            self.date_label.config(text=f"Feuille du: {self.selected_date_str}-{value.upper()}")

        self.process()

    def load_day_sheet_data(self, data, selected_date=None):
        self.tree.delete(*self.tree.get_children())

        if selected_date:
            self.selected_date_str = selected_date
        else:
            self.selected_date_str = "??-??-????"

        self.date_label.config(text=f"Feuille du: {self.selected_date_str}")

        for entry in data:
            if entry.get("is_section"):
                self.tree.insert("", "end", values=("", entry["name"], "", "", "", ""), tags=("section",))
            else:
                self.tree.insert("", "end", values=(
                    entry.get("number", ""),
                    entry.get("name", ""),
                    entry.get("points", ""),
                    entry.get("hours", ""),
                    "",  # Sur paye
                    ""   # Cash
                ))

        self.process()

    def get_inputs(self):
        try:
            ventes_net = float(self.fields["Ventes Nettes"].get() or "0")
        except ValueError:
            ventes_net = 0.0

        try:
            depot_net = float(self.fields["Dépot Net"].get() or "0")
        except ValueError:
            depot_net = 0.0

        return ventes_net, depot_net

    def get_bussboy_percentage(self, count):
        shift = self.shift_var.get()

        if shift == "Matin":
            return 0.03 if count >= 1 else 0.0
        elif shift == "Soir":
            if count == 0:
                return 0.0
            elif count == 1:
                return 0.02
            elif count == 2:
                return 0.025
            else:
                return 0.03
        return 0.0

    def distribution_bussboys(self):
        bussboy_rows = []
        count = 0
        in_bussboy_section = False

        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            name = values[1]

            if name.startswith("---"):
                in_bussboy_section = "Bussboy" in name
                continue

            if in_bussboy_section and values[0] and values[1]:
                try:
                    hours = float(values[3])
                    points = float(values[2])
                    bussboy_rows.append((item, hours, points))
                    count += 1
                except (ValueError, TypeError):
                    continue

        percentage = self.get_bussboy_percentage(count)
        self.bussboy_percentage_label.config(text=f"Pourcentage: {percentage * 100:.2f}%")

        bussboy_amount = self.ventes_net * percentage
        actual_tip_from_depot = abs(self.depot_net) if self.depot_net < 0 else 0.0
        depot_paid = min(bussboy_amount, actual_tip_from_depot)
        cash_paid = max(0, bussboy_amount - depot_paid)
        total_weight = sum(h * p for _, h, p in bussboy_rows)

        for item, hours, points in bussboy_rows:
            weight = hours * points
            if total_weight > 0:
                share = (weight / total_weight) * bussboy_amount
                sur_paye = (weight / total_weight) * depot_paid
                cash = share - sur_paye
            else:
                sur_paye = cash = 0.0

            values = list(self.tree.item(item)["values"])
            values[4] = f"{sur_paye:.2f}"
            values[5] = f"{cash:.2f}"
            self.tree.item(item, values=values)

    def distribution_service(self):
        pass

    def process(self):
        self.ventes_net, self.depot_net = self.get_inputs()
        self.distribution_bussboys()
        self.distribution_service()
