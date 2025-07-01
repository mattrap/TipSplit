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
        self.matin_button = ttk.Button(toggle_frame, text="Matin", bootstyle="outline-primary", width=10,
            command=lambda: self.set_shift("Matin"))
        self.soir_button = ttk.Button(toggle_frame, text="Soir", bootstyle="outline-primary", width=10,
            command=lambda: self.set_shift("Soir"))
        self.matin_button.pack(side=LEFT, padx=5)
        self.soir_button.pack(side=LEFT, padx=5)

        # Distribution colors
        self.sur_paye_color = "#258dba"
        self.cash_color = "#28a745"

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

            entry.bind("<KeyRelease>", lambda e: self.process())
            entry.bind("<FocusOut>", lambda e: self.process())

        # Summary panels
        self.create_bussboy_summary_panel(input_frame)
        self.create_service_summary_panel(input_frame)
        self.create_depot_summary_panel(input_frame)

        # Treeview
        self.tree = ttk.Treeview(
            container,
            columns=("number", "name", "points", "hours", "sur_paye", "cash"),
            show="headings",
            bootstyle="primary"
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
        bussboy_wrapper = ttk.Frame(parent)
        bussboy_wrapper.grid(row=0, column=2, rowspan=4, padx=(20, 0), sticky=N)

        title_label = ttk.Label(bussboy_wrapper, text="BUSSBOYS", font=("Helvetica", 11, "bold"))
        title_label.pack(anchor=CENTER, pady=(0, 5))

        bussboy_frame = ttk.Frame(bussboy_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        bussboy_frame.pack(fill=X)

        # Percentage label
        self.bussboy_percentage_label = ttk.Label(bussboy_frame, text="Pourcentage: 0.00%", font=("Helvetica", 11, "bold"), foreground="#000000")
        self.bussboy_percentage_label.pack(anchor=W, pady=(5, 2))
        # Montant label
        self.bussboy_amount_label = ttk.Label(bussboy_frame, text="Montant: 0.00 $", font=("Helvetica", 11, "bold"), foreground="#000000")
        self.bussboy_amount_label.pack(anchor=W, pady=(2, 2))
        # Sur paye label
        self.bussboy_sur_paye_label = ttk.Label(bussboy_frame, text="Sur Paye: 0.00 $", font=("Helvetica", 11, "bold"), foreground=self.sur_paye_color)
        self.bussboy_sur_paye_label.pack(anchor=W, pady=(2, 2))
        # Cash label
        self.bussboy_cash_label = ttk.Label(bussboy_frame, text="Cash: 0.00 $", font=("Helvetica", 11, "bold"), foreground=self.cash_color)
        self.bussboy_cash_label.pack(anchor=W, pady=(2, 5))

    def create_service_summary_panel(self, parent):
        service_wrapper = ttk.Frame(parent)
        service_wrapper.grid(row=0, column=3, rowspan=4, padx=(20, 0), sticky=N)

        title_label = ttk.Label(service_wrapper, text="SERVICE", font=("Helvetica", 11, "bold"))
        title_label.pack(anchor=CENTER, pady=(0, 5))

        service_frame = ttk.Frame(service_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        service_frame.pack(fill=X)

        # Sur Paye
        self.service_sur_paye_label = ttk.Label(service_frame, text="Sur Paye: 0.00 $", font=("Helvetica", 11, "bold"), foreground=self.sur_paye_color)
        self.service_sur_paye_label.pack(anchor=W, pady=(5, 2))

        # Cash
        self.service_cash_label = ttk.Label(service_frame, text="Cash: 0.00 $", font=("Helvetica", 11, "bold"), foreground=self.cash_color)
        self.service_cash_label.pack(anchor=W, pady=(2, 2))

        # Frais Admin
        self.service_admin_fees_label = ttk.Label(service_frame, text="Frais Admin: 0.00 $", font=("Helvetica", 11, "bold"), foreground=self.sur_paye_color)
        self.service_admin_fees_label.pack(anchor=W, pady=(2, 5))

    def create_depot_summary_panel(self, parent):
        depot_wrapper = ttk.Frame(parent)
        depot_wrapper.grid(row=0, column=4, rowspan=4, padx=(20, 0), sticky=N)

        title_label = ttk.Label(depot_wrapper, text="DÉPOT", font=("Helvetica", 11, "bold"))
        title_label.pack(anchor=CENTER, pady=(0, 5))

        depot_frame = ttk.Frame(depot_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        depot_frame.pack(fill=X)

        self.service_owes_admin_label = ttk.Label(depot_frame, text="À remettre: 0.00 $", font=("Helvetica", 11, "bold"), foreground="#dc3545")
        self.service_owes_admin_label.pack(anchor=W, pady=(5, 2))

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
        def parse_float(value):
            try:
                return float(value or "0")
            except ValueError:
                return 0.0

        ventes_net = parse_float(self.fields["Ventes Nettes"].get())
        depot_net = parse_float(self.fields["Dépot Net"].get())
        frais_admin = parse_float(self.fields["Frais Admin"].get())
        cash = parse_float(self.fields["Cash"].get())

        return ventes_net, depot_net, frais_admin, cash

    def distribution_net_values(self, bussboy_amount):
        _, depot_net, _, cash_initial = self.get_inputs()

        if depot_net < 0:
            depot_available = abs(depot_net)
            service_owes_admin = 0.0
        else:
            depot_available = 0.0
            service_owes_admin = depot_net

        bussboy_sur_paye_distributed = min(bussboy_amount, depot_available)
        bussboy_cash_distributed = bussboy_amount - bussboy_sur_paye_distributed

        remaining_depot_for_service = max(0.0, depot_available - bussboy_sur_paye_distributed)
        cash_available_for_service = max(0.0, cash_initial - service_owes_admin - bussboy_cash_distributed)

        return {
            "bussboy_sur_paye_distributed": bussboy_sur_paye_distributed,
            "bussboy_cash_distributed": bussboy_cash_distributed,
            "service_owes_admin": service_owes_admin,
            "remaining_depot_for_service": remaining_depot_for_service,
            "cash_available_for_service": cash_available_for_service
        }

    def get_bussboy_percentage_and_amount(self):
        # Count bussboys
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
                    float(values[3])  # hours
                    float(values[2])  # points
                    count += 1
                except (ValueError, TypeError):
                    continue

        # Determine percentage based on count and shift
        shift = self.shift_var.get()

        if shift == "Matin":
            bussboy_percentage = 0.03 if count >= 1 else 0.0
        elif shift == "Soir":
            if count == 0:
                bussboy_percentage = 0.0
            elif count == 1:
                bussboy_percentage = 0.02
            elif count == 2:
                bussboy_percentage = 0.025
            else:
                bussboy_percentage = 0.03
        else:
            bussboy_percentage = 0.0

        # Calculate amount
        ventes_net, _, _, _ = self.get_inputs()
        bussboy_amount = ventes_net * bussboy_percentage

        return bussboy_percentage, bussboy_amount

    def distribution_bussboys(self):
        pass

    def distribution_service(self):
        pass

    def process(self):
        # Get user-entered inputs
        self.ventes_net, self.depot_net, self.frais_admin, self.cash = self.get_inputs()

        # Calculate bussboy percentage and amount
        bussboy_percentage, bussboy_amount = self.get_bussboy_percentage_and_amount()

        # Calculate distribution net values
        net_values = self.distribution_net_values(bussboy_amount)

        # Update BUSSBOYS summary panel
        self.bussboy_percentage_label.config(text=f"Pourcentage: {bussboy_percentage * 100:.2f}%")
        self.bussboy_amount_label.config(text=f"Montant: {bussboy_amount:.2f} $")
        self.bussboy_sur_paye_label.config(text=f"Sur Paye: {net_values['bussboy_sur_paye_distributed']:.2f} $")
        self.bussboy_cash_label.config(text=f"Cash: {net_values['bussboy_cash_distributed']:.2f} $")

        # Update DÉPOT summary panel
        self.service_owes_admin_label.config(text=f"À remettre: {net_values['service_owes_admin']:.2f} $")

        # Update SERVICE summary panel
        self.service_sur_paye_label.config(text=f"Sur Paye: {net_values['remaining_depot_for_service']:.2f} $")
        self.service_cash_label.config(text=f"Cash: {net_values['cash_available_for_service']:.2f} $")
        self.service_admin_fees_label.config(text=f"Frais Admin: {self.frais_admin:.2f} $")

        # 🔄 Distribute values to table
        self.distribution_bussboys()
        self.distribution_service()


