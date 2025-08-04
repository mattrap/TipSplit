import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PayPeriods import get_selected_period
from Export import export_distribution_from_tab
from datetime import datetime

class DistributionTab:
    def __init__(self, root, shared_data):
        self.root = root
        if shared_data is None:
            raise ValueError("shared_data must be provided to DistributionTab")
        self.shared_data = shared_data
        self.selected_date_str = ""

        self.set_theme_colors()

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        self.setup_layout(container)

    def set_theme_colors(self):
        self.sur_paye_color = "#258dba"
        self.cash_color = "#28a745"
        self.grey_color = "#6c757d"

    def setup_layout(self, container):
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=X)

        self.create_header_labels(top_frame)
        self.create_shift_and_export_buttons(top_frame)
        self.create_input_fields(container)
        self.create_summary_panels(self.input_frame)
        self.create_distribution_treeview(container)

    def create_header_labels(self, parent):
        label_row = ttk.Frame(parent)
        label_row.pack(fill=X, pady=(0, 5))

        self.date_label = ttk.Label(label_row, text="Feuille du:", font=("Helvetica", 14, "bold"))
        self.date_label.pack(side=LEFT)

        ttk.Label(label_row).pack(side=LEFT, expand=True)

        self.pay_period_label = ttk.Label(label_row, font=("Helvetica", 12, "bold"), foreground="#1f6f8b")
        self.pay_period_label.pack(side=LEFT, padx=(10, 0))

    def create_shift_and_export_buttons(self, parent):
        toggle_frame = ttk.Frame(parent)
        toggle_frame.pack(fill=X, pady=5)

        shift_buttons = ttk.Frame(toggle_frame)
        shift_buttons.pack(side=LEFT)

        self.shift_var = ttk.StringVar(value="")

        self.matin_button = ttk.Button(
            shift_buttons, text="Matin", width=10, bootstyle="outline-primary",
            command=lambda: self.set_shift("Matin")
        )
        self.soir_button = ttk.Button(
            shift_buttons, text="Soir", width=10, bootstyle="outline-primary",
            command=lambda: self.set_shift("Soir")
        )
        self.matin_button.pack(side=LEFT, padx=5)
        self.soir_button.pack(side=LEFT, padx=5)

        self.export_button = ttk.Button(
            toggle_frame, text="📤 Exporter", width=12, bootstyle="success",
            command=lambda: export_distribution_from_tab(self)
        )
        self.export_button.pack(side=RIGHT)

    def create_input_fields(self, parent):
        self.input_frame = ttk.LabelFrame(parent, text="Paramètres de distribution", padding=10)
        self.input_frame.pack(fill=X, pady=(0, 10))

        self.fields = {}
        labels = ["Ventes Nettes", "Dépot Net", "Frais Admin", "Cash"]
        for i, label in enumerate(labels):
            ttk.Label(self.input_frame, text=label + ":", font=("Helvetica", 10)).grid(row=i, column=0, sticky=W, pady=5)
            entry = ttk.Entry(self.input_frame, width=20)
            entry.grid(row=i, column=1, sticky=W, pady=5)
            self.fields[label] = entry
            entry.bind("<KeyRelease>", lambda e: self.process())
            entry.bind("<FocusOut>", lambda e: self.process())

    def create_summary_panels(self, parent):
        self.create_bussboy_summary_panel(parent)
        self.create_service_summary_panel(parent)
        self.create_depot_summary_panel(parent)

    def create_distribution_treeview(self, parent):
        self.tree = ttk.Treeview(
            parent,
            columns=("number", "name", "points", "hours", "cash", "sur_paye", "frais_admin"),
            show="headings",
            bootstyle="primary"
        )

        headers = {
            "number": "Number",
            "name": "Name",
            "points": "Points",
            "hours": "Hours",
            "cash": "💵 Cash 💵",
            "sur_paye": "Sur paye",
            "frais_admin": "Frais Admin"
        }

        for col in self.tree["columns"]:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=100, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)
        self.tree.tag_configure("section", font=("Helvetica", 10, "bold"), background="#b4c7af")

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

        # Frais Admin
        self.service_admin_fees_label = ttk.Label(service_frame, text="Frais Admin: 0.00 $",font=("Helvetica", 11, "bold"), foreground=self.sur_paye_color)
        self.service_admin_fees_label.pack(anchor=W, pady=(2, 5))
        # Cash
        self.service_cash_label = ttk.Label(service_frame, text="Cash: 0.00 $", font=("Helvetica", 11, "bold"), foreground=self.cash_color)
        self.service_cash_label.pack(anchor=W, pady=(2, 2))

    def create_depot_summary_panel(self, parent):
        depot_wrapper = ttk.Frame(parent)
        depot_wrapper.grid(row=0, column=4, rowspan=4, padx=(20, 0), sticky=N)

        title_label = ttk.Label(depot_wrapper, text="DÉPOT", font=("Helvetica", 11, "bold"))
        title_label.pack(anchor=CENTER, pady=(0, 5))

        depot_frame = ttk.Frame(depot_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        depot_frame.pack(fill=X)

        self.service_owes_admin_label = ttk.Label(depot_frame, text="À remettre: 0.00 $", font=("Helvetica", 11, "bold"), foreground="#dc3545")
        self.service_owes_admin_label.pack(anchor=W, pady=(5, 2))

    def update_label(self, label_widget, value, prefix, color_if_nonzero):
        label_widget.config(
            text=f"{prefix}: {value:.2f}",
            foreground=color_if_nonzero if value != 0 else self.grey_color
        )

    def update_pay_period_display(self):
        if not hasattr(self, "pay_period_label"):
            return

        if not self.selected_date_str:
            self.pay_period_label.config(text="Période de paye: ❌ date invalide")
            return

        try:
            selected_dt = datetime.strptime(self.selected_date_str, "%d-%m-%Y")
            period_key, period_data = get_selected_period(selected_dt)
            if period_data:
                self.pay_period_label.config(text=f"Période de paye du: {period_data['range']}")
            else:
                self.pay_period_label.config(text="Période de paye: ❌ hors plage")
        except Exception:
            self.pay_period_label.config(text="Période de paye: ❌ erreur de date")

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

    def get_inputs(self):
        def parse_float(value):
            try:
                return float(value.strip().replace(",", "."))
            except ValueError:
                return 0.0

        ventes_net = parse_float(self.fields["Ventes Nettes"].get())
        depot_net = parse_float(self.fields["Dépot Net"].get())
        frais_admin = parse_float(self.fields["Frais Admin"].get())
        cash = parse_float(self.fields["Cash"].get())

        return ventes_net, depot_net, frais_admin, cash

    def round_cash_down(self, value):
        """Rounds down to the nearest 0.25 (for distributing)"""
        return (int(value * 4)) / 4.0

    def round_cash_up(self, value):
        """Rounds up to the nearest 0.25 (for amounts owed)."""
        return ((int(value * 4 + 0.9999)) / 4.0)

    def distribution_net_values(self, bussboy_amount):
        _, depot_net, frais_admin, cash_initial = self.get_inputs()

        if depot_net < 0:
            depot_available = abs(depot_net)
            service_owes_admin = 0.0
        else:
            depot_available = 0.0
            service_owes_admin = self.round_cash_up(depot_net)

        # zero si depot_available = 0 sinon combien le dépot couvre
        bussboy_sur_paye_distributed = min(bussboy_amount, depot_available)
        # montant manquant du dépot pour couvrir bussboys, ROUND UP
        bussboy_cash_distributed = self.round_cash_up(bussboy_amount - bussboy_sur_paye_distributed)

        # dépot net apres bussboy payés ou zero si il en reste plus
        remaining_depot_for_service = max(0.0, depot_available - bussboy_sur_paye_distributed)
        # cash after paying the dépot and paying the bussboys, montant dù ou 0
        cash_available_for_service = max(0.0, cash_initial - service_owes_admin - bussboy_cash_distributed)
        frais_admin_service = frais_admin * 0.8
        return {
            "bussboy_sur_paye_distributed": bussboy_sur_paye_distributed,
            "bussboy_cash_distributed": bussboy_cash_distributed,
            "service_owes_admin": service_owes_admin,
            "remaining_depot_for_service": remaining_depot_for_service,
            "cash_available_for_service": cash_available_for_service,
            "frais_admin_service": frais_admin_service
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
        # Calculate totals and get net values
        _, bussboy_amount = self.get_bussboy_percentage_and_amount()
        net_values = self.distribution_net_values(bussboy_amount)

        total_points_hours = 0
        bussboy_items = []

        # First pass: gather bussboy entries and compute total (points × hours)
        in_bussboy_section = False
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            name = values[1]

            if name.startswith("---"):
                in_bussboy_section = "Bussboy" in name
                continue

            if in_bussboy_section and values[0] and values[1]:
                try:
                    points = float(values[2])
                    hours = float(values[3])
                    product = points * hours
                    total_points_hours += product
                    bussboy_items.append((item, product))
                except (ValueError, TypeError):
                    continue

        # Avoid division by zero
        if total_points_hours == 0:
            return

        # Second pass: distribute amounts proportionally
        for item, product in bussboy_items:
            proportion = product / total_points_hours
            sur_paye = proportion * net_values["bussboy_sur_paye_distributed"]
            cash = self.round_cash_down(proportion * net_values["bussboy_cash_distributed"])

            self.tree.set(item, "cash", f"{cash:.2f}")
            self.tree.set(item, "sur_paye", f"{sur_paye:.2f}")

    def distribution_service(self):
        # Get distribution values
        _, bussboy_amount = self.get_bussboy_percentage_and_amount()
        net_values = self.distribution_net_values(bussboy_amount)
        remaining_depot = net_values["remaining_depot_for_service"]
        available_cash = net_values["cash_available_for_service"]
        frais_admin_service = net_values["frais_admin_service"]

        total_points_hours = 0
        service_items = []

        # First pass: collect service entries and compute total (points × hours)
        in_service_section = False
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            name = values[1]

            if name.startswith("---"):
                in_service_section = "Service" in name
                continue

            if in_service_section and values[0] and values[1]:
                try:
                    points = float(values[2])
                    hours = float(values[3])
                    product = points * hours
                    total_points_hours += product
                    service_items.append((item, product))
                except (ValueError, TypeError):
                    continue

        if total_points_hours == 0:
            return

        # Second pass: distribute Sur Paye, Cash, and Frais Admin proportionally
        for item, product in service_items:
            proportion = product / total_points_hours
            sur_paye = proportion * remaining_depot
            cash = self.round_cash_down(proportion * available_cash)
            admin = proportion * frais_admin_service

            self.tree.set(item, "cash", f"{cash:.2f}")
            self.tree.set(item, "sur_paye", f"{sur_paye:.2f}")
            self.tree.set(item, "frais_admin", f"{admin:.2f}")

    def load_day_sheet_data(self):
        transfer_data = self.shared_data.get("transfer")
        if not transfer_data:
            print("⚠️ No transfer data found.")
            return

        entries = transfer_data.get("entries", [])
        selected_date = transfer_data.get("date", "??-??-????")
        self.selected_date_str = selected_date

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

        self.tree.delete(*self.tree.get_children())
        self.date_label.config(text=f"Feuille du: {self.selected_date_str}")
        self.update_pay_period_display()

        for entry in organized_data:
            if entry.get("is_section"):
                self.tree.insert("", "end", values=("", entry["name"], "", "", "", ""), tags=("section",))
            else:
                self.tree.insert("", "end", values=(
                    entry.get("number", ""),
                    entry.get("name", ""),
                    entry.get("points", ""),
                    entry.get("hours", ""),
                    "",  # CASH
                    "",  # Sur paye
                    ""  # Frais Admin
                ))

        self.process()

    def process(self):
        # Get user-entered inputs
        self.ventes_net, self.depot_net, self.frais_admin, self.cash = self.get_inputs()

        # Calculate bussboy percentage and amount
        bussboy_percentage, bussboy_amount = self.get_bussboy_percentage_and_amount()

        # Calculate distribution net values
        net_values = self.distribution_net_values(bussboy_amount)

        self.update_label(self.bussboy_percentage_label, bussboy_percentage * 100, "Pourcentage", "#000000")
        self.update_label(self.bussboy_amount_label, bussboy_amount, "Montant", "#000000")
        self.update_label(self.bussboy_sur_paye_label, net_values["bussboy_sur_paye_distributed"], "Sur Paye",self.sur_paye_color)
        self.update_label(self.bussboy_cash_label, net_values["bussboy_cash_distributed"], "Cash", self.cash_color)

        self.update_label(self.service_owes_admin_label, net_values["service_owes_admin"], "À remettre", "#dc3545")

        self.update_label(self.service_sur_paye_label, net_values["remaining_depot_for_service"], "Sur Paye",self.sur_paye_color)
        self.update_label(self.service_cash_label, net_values["cash_available_for_service"], "Cash", self.cash_color)
        self.update_label(self.service_admin_fees_label, net_values["frais_admin_service"], "Frais Admin",self.sur_paye_color)

        # 🔄 Distribute values to table
        self.distribution_bussboys()
        self.distribution_service()
