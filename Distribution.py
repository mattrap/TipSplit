import math
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from Export import export_distribution_from_tab
from datetime import datetime
from ui_scale import scale
from tree_utils import fit_columns
from tkinter import messagebox
from AppConfig import get_distribution_settings

class DistributionTab:
    def __init__(self, root, shared_data):
        self.root = root
        if shared_data is None:
            raise ValueError("shared_data must be provided to DistributionTab")
        self.shared_data = shared_data
        self.selected_date_str = ""
        self.current_period = None
        self._dist_settings = get_distribution_settings()

        self.set_theme_colors()

        container = ttk.Frame(root, padding=10)
        container.pack(fill=BOTH, expand=True)

        self.setup_layout(container)

        self.update_export_button_state()

    def _refresh_distribution_settings(self):
        """Reload distribution settings from config."""
        self._dist_settings = get_distribution_settings()
        return self._dist_settings

    def _get_dist_setting(self, key: str, default: float) -> float:
        settings = getattr(self, "_dist_settings", None)
        if not settings or key not in settings:
            settings = self._refresh_distribution_settings()
        return float(settings.get(key, default))

    def set_theme_colors(self):
        self.sur_paye_color = "#258dba"
        self.cash_color = "#28a745"
        self.grey_color = "#6c757d"
        self.depot_color = "#dc3545"

    def setup_layout(self, container):
        self.view_mode = ttk.StringVar(value="distribution")

        top_frame = ttk.Frame(container)
        top_frame.pack(fill=X)

        self.create_header_labels(top_frame)
        self.create_shift_and_export_buttons(top_frame)
        self.create_input_fields(container)
        self.create_summary_panels(self.input_frame)
        self.create_helper_panel(container)
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

        # LEFT: Matin / Soir
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

        # RIGHT: Export (far right)
        self.export_button = ttk.Button(
            toggle_frame, text="📤 Exporter", width=12, bootstyle="success",
            command=self.confirm_export, state=DISABLED
        )
        self.export_button.pack(side=RIGHT)

        # RIGHT: View toggle (to the left of Export)
        view_frame = ttk.Frame(toggle_frame)
        view_frame.pack(side=RIGHT, padx=(0, 8))

        self.view_dist_btn = ttk.Button(
            view_frame, text="Vue Distribution", width=16, bootstyle="primary",
            command=lambda: self.set_view_mode("distribution")
        )
        self.view_decl_btn = ttk.Button(
            view_frame, text="Vue Déclaration", width=16, bootstyle="outline-primary",
            command=lambda: self.set_view_mode("declaration")
        )
        self.view_dist_btn.pack(side=LEFT)
        self.view_decl_btn.pack(side=LEFT, padx=(6, 0))

    def create_input_fields(self, parent):
        # This is the overall row that will hold BOTH input groups + the summary panels
        self.input_frame = ttk.Frame(parent, padding=0)
        self.input_frame.pack(fill=X, pady=(0, 10))

        # Make room for: [0]=distribution inputs, [1]=declaration inputs, [2..4]=summary panels
        for c in range(5):
            self.input_frame.columnconfigure(c, weight=0)
        # Let summary columns breathe if window grows
        self.input_frame.columnconfigure(2, weight=1)
        self.input_frame.columnconfigure(3, weight=1)
        self.input_frame.columnconfigure(4, weight=1)

        # --- LEFT: Paramètres de distribution (your existing inputs) ---
        self.distrib_group = ttk.LabelFrame(self.input_frame, text="Paramètres de distribution", padding=10)
        self.distrib_group.grid(row=0, column=0, sticky=N, padx=(0, 10))

        self.fields = {}
        distrib_labels = ["Ventes Nettes", "Dépot Net", "Frais Admin", "Cash"]
        for i, label in enumerate(distrib_labels):
            ttk.Label(self.distrib_group, text=label + ":", font=("Helvetica", 10)).grid(
                row=i, column=0, sticky=W, pady=5
            )
            entry = self._create_numeric_entry(self.distrib_group)
            entry.grid(row=i, column=1, sticky=W, pady=5)
            self.fields[label] = entry
            entry.bind("<KeyRelease>", lambda e: self.process())
            entry.bind("<FocusOut>", lambda e: self.process())

        # --- RIGHT: Paramètres de déclaration (new) ---
        self.declaration_group = ttk.LabelFrame(self.input_frame, text="Paramètres de déclaration", padding=10)
        self.declaration_group.grid(row=0, column=1, sticky=N, padx=(10, 10))

        self.declaration_fields = {}
        declaration_labels = ["Ventes Totales", "Clients", "Tips due", "Ventes Nourriture"]
        for i, label in enumerate(declaration_labels):
            ttk.Label(self.declaration_group, text=label + ":", font=("Helvetica", 10)).grid(
                row=i, column=0, sticky=W, pady=5
            )
            entry = self._create_numeric_entry(self.declaration_group)
            entry.grid(row=i, column=1, sticky=W, pady=5)
            self.declaration_fields[label] = entry
            entry.bind("<KeyRelease>", lambda e: self.process())
            entry.bind("<FocusOut>", lambda e: self.process())

    def _create_numeric_entry(self, parent):
        """Create a left-aligned entry with restricted input and 2 decimals."""
        vcmd = (self.root.register(self._validate_numeric_pattern), "%P")
        entry = ttk.Entry(parent, width=20, justify=LEFT, validate="key", validatecommand=vcmd)
        return entry

    def _validate_numeric_pattern(self, proposed: str) -> bool:
        """Allow only digits, one leading '-', one decimal ('.' or ','), max 2 decimals."""
        if proposed == "":
            return True
        # Allowed characters
        for ch in proposed:
            if ch not in "0123456789-.,":
                self._beep_safe()
                return False
        # '-' only at the start and at most one
        if proposed.count("-") > 1 or ("-" in proposed and not proposed.startswith("-")):
            self._beep_safe()
            return False
        # Only one decimal separator total
        if proposed.count(".") + proposed.count(",") > 1:
            self._beep_safe()
            return False
        # Max two digits after decimal separator
        sep_index = -1
        if "." in proposed:
            sep_index = proposed.index(".")
        elif "," in proposed:
            sep_index = proposed.index(",")
        if sep_index != -1:
            frac = proposed[sep_index + 1:]
            if len(frac) > 2:
                self._beep_safe()
                return False
        return True

    def _beep_safe(self):
        try:
            self.root.bell()
        except Exception:
            pass

    def create_summary_panels(self, parent):
        self.create_bussboy_summary_panel(parent)
        self.create_service_summary_panel(parent)
        self.create_depots_summary_pannel(parent)
        self.create_declaration_summary_panel(parent)

    def create_helper_panel(self, parent):
        helper_frame = ttk.LabelFrame(parent, text="Légende", padding=10)
        helper_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(
            helper_frame,
            text="Remis comptant",
            font=("Helvetica", 11, "bold"),
            foreground=self.cash_color,
        ).pack(side=LEFT, padx=10)

        ttk.Label(
            helper_frame,
            text="Reçu sur paye",
            font=("Helvetica", 11, "bold"),
            foreground=self.sur_paye_color,
        ).pack(side=LEFT, padx=10)

        ttk.Label(
            helper_frame,
            text="À partir du dépot",
            font=("Helvetica", 11, "bold"),
            foreground=self.depot_color,
        ).pack(side=LEFT, padx=10)

    def create_distribution_treeview(self, parent):
        group = ttk.LabelFrame(parent, text="Résumé du shift", padding=10)
        group.pack(fill=BOTH, expand=True, pady=(0, 8))

        self.distribution_tree = ttk.Treeview(
            group,
            columns=("number", "name", "points", "hours", "cash", "sur_paye", "frais_admin", "A", "B", "D", "E", "F"),
            show="headings",
            bootstyle="primary"
        )

        headers = {
            "number": "Numéro d'employé",
            "name": "Nom",
            "points": "Points",
            "hours": "Heures",
            "cash": "CASH",
            "sur_paye": "Sur paye",
            "frais_admin": "Frais admin",
            "A": "A",
            "B": "B",
            "D": "D",
            "E": "E",
            "F": "F",
        }
        self._width_map = {}
        for col in self.distribution_tree["columns"]:
            self.distribution_tree.heading(col, text=headers[col])
            width = 180 if col == "name" else 90
            anchor = W if col == "name" else CENTER
            scaled_width = scale(width)
            self._width_map[col] = scaled_width
            self.distribution_tree.column(col, width=scaled_width, minwidth=scale(20), anchor=anchor, stretch=True)

        self.distribution_tree.pack(fill=BOTH, expand=True)
        fit_columns(self.distribution_tree, self._width_map)
        self.distribution_tree.tag_configure("section", font=("Helvetica", 14, "bold"), background="#b4c7af")

        # Back-compat alias
        self.tree = self.distribution_tree

        # Respect current mode and sync button styles/columns
        mode = self.view_mode.get() if hasattr(self, "view_mode") else "distribution"
        self.set_view_mode(mode)

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

    def create_depots_summary_pannel(self, parent):
        # One wrapper in column 4 that holds both panels stacked
        depot_wrapper = ttk.Frame(parent)
        depot_wrapper.grid(row=0, column=4, padx=(20, 0), sticky=N)

        # ---------- Admin Panel ----------
        admin_title = ttk.Label(
            depot_wrapper,
            text="DÉPOT ADMINISTRATION",
            font=("Helvetica", 11, "bold")
        )
        admin_title.pack(anchor=CENTER, pady=(0, 5))

        admin_frame = ttk.Frame(depot_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        admin_frame.pack(fill=X)

        self.service_owes_admin_label = ttk.Label(
            admin_frame,
            text="À remettre: 0.00 $",
            font=("Helvetica", 11, "bold"),
            foreground=self.grey_color,
        )
        self.service_owes_admin_label.pack(anchor=W, pady=(5, 2))

        # ---------- Cuisine Panel (immediately under Admin) ----------
        cuisine_title = ttk.Label(
            depot_wrapper,
            text="DÉPOT CUISINE",
            font=("Helvetica", 11, "bold")
        )
        cuisine_title.pack(anchor=CENTER, pady=(10, 5))  # small gap to keep it close

        cuisine_frame = ttk.Frame(depot_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        cuisine_frame.pack(fill=X)

        self.service_owes_cuisine_label = ttk.Label(
            cuisine_frame,
            text="Cuisine: 0.00 $",
            font=("Helvetica", 11, "bold"),
            foreground=self.grey_color,
        )
        self.service_owes_cuisine_label.pack(anchor=W, pady=(5, 2))

        return depot_wrapper

    def create_declaration_summary_panel(self, parent):
        decl_wrapper = ttk.Frame(parent)
        # Put it after the others (uses next column)
        decl_wrapper.grid(row=0, column=5, rowspan=4, padx=(20, 0), sticky=N)

        title_label = ttk.Label(decl_wrapper, text="DÉCLARATION", font=("Helvetica", 11, "bold"))
        title_label.pack(anchor=CENTER, pady=(0, 5))

        decl_frame = ttk.Frame(decl_wrapper, padding=(10, 5), relief="groove", borderwidth=2)
        decl_frame.pack(fill=X)

        self.ventes_declarees_label = ttk.Label(
            decl_frame, text="Ventes déclarées: 0.00 $", font=("Helvetica", 11, "bold"), foreground="#000000"
        )
        self.ventes_declarees_label.pack(anchor=W, pady=(5, 2))

    def update_label(self, label_widget, value, prefix, color_if_nonzero):
        label_widget.config(
            text=f"{prefix}: {value:.2f}",
            foreground=color_if_nonzero if value != 0 else self.grey_color
        )

    def update_pay_period_display(self):
        if not hasattr(self, "pay_period_label"):
            return

        period = self.current_period or self._resolve_period_for_selected_date()
        if period:
            self.current_period = period
            label = period.get("range_label") or ""
            display = period.get("display_id") or ""
            if label:
                self.pay_period_label.config(text=f"Période de paye {display}: {label}")
            else:
                self.pay_period_label.config(text=f"Période de paye: {display}")
            return

        if not self.selected_date_str:
            self.pay_period_label.config(text="Période de paye: ❌ date invalide")
            return

        self.pay_period_label.config(text="Période de paye: ❌ introuvable")

    def set_shift(self, value):
        self.shift_var.set(value)
        self.view_mode = ttk.StringVar(value="distribution")

        if value == "Matin":
            self.matin_button.config(bootstyle="primary")
            self.soir_button.config(bootstyle="outline-primary")
        elif value == "Soir":
            self.matin_button.config(bootstyle="outline-primary")
            self.soir_button.config(bootstyle="primary")

        if self.selected_date_str:
            self.date_label.config(text=f"Feuille du: {self.selected_date_str}-{value.upper()}")

        self.process()

    def show_distribution_view(self):
        # Only show Distribution columns
        self.tree["displaycolumns"] = ("number", "name", "points", "hours",
                                       "cash", "sur_paye", "frais_admin")

    def show_declaration_view(self):
        # Only show Declaration columns
        self.tree["displaycolumns"] = ("number", "name", "points", "hours",
                                       "A", "B", "D", "E", "F")

    def set_view_mode(self, mode):
        # Update the buttons’ styles + switch columns
        self.view_mode.set(mode)
        if mode == "distribution":
            self.view_dist_btn.config(bootstyle="primary")
            self.view_decl_btn.config(bootstyle="outline-primary")
            self.show_distribution_view()
        else:
            self.view_dist_btn.config(bootstyle="outline-primary")
            self.view_decl_btn.config(bootstyle="primary")
            self.show_declaration_view()

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

    def get_declaration_inputs(self):
        def parse_float(value):
            try:
                return float(value.strip().replace(",", "."))
            except ValueError:
                return 0.0

        ventes_totales = parse_float(self.declaration_fields["Ventes Totales"].get())
        clients = parse_float(self.declaration_fields["Clients"].get())
        tips_due = parse_float(self.declaration_fields["Tips due"].get())
        ventes_nourriture = parse_float(self.declaration_fields["Ventes Nourriture"].get())
        return ventes_totales, clients, tips_due, ventes_nourriture

    def inputs_valid(self):
        def is_valid(entry):
            text = entry.get().strip().replace(",", ".")
            if not text:
                return False
            try:
                float(text)
                return True
            except ValueError:
                return False

        all_entries = list(self.fields.values()) + list(self.declaration_fields.values())
        return all(is_valid(e) for e in all_entries)

    def update_export_button_state(self):
        ready = self.inputs_valid() and self.get_active_pay_period() is not None
        self.export_button.config(state=NORMAL if ready else DISABLED)

    def confirm_export(self):
        if not self.inputs_valid():
            return
        if not self.get_active_pay_period():
            messagebox.showerror("Période manquante", "Impossible de déterminer la période de paye.")
            return
        if messagebox.askyesno("Confirmation", "Êtes-vous sûr que la distribution est complète ?"):
            export_distribution_from_tab(self)

    def round_cash_down(self, value):
        """Rounds down to the configured increment (for distributing)."""
        increment = self._get_dist_setting("round_increment", 0.25)
        if increment <= 0:
            return value
        return round(math.floor(value / increment) * increment, 2)

    def round_cash_up(self, value):
        """Rounds up to the configured increment (for amounts owed)."""
        increment = self._get_dist_setting("round_increment", 0.25)
        if increment <= 0:
            return value
        return round(math.ceil(value / increment) * increment, 2)

    def distribution_net_values(self, bussboy_amount):
        ventes_net, depot_net, frais_admin, cash_initial = self.get_inputs()
        _, _, _, ventes_nourriture = self.get_declaration_inputs()

        cuisine_amount, cuisine_source = self.calculate_cuisine_distribution(ventes_nourriture, depot_net)
        cash_cuisine = cuisine_amount if cuisine_source == "cash" else 0.0
        depot_cuisine = cuisine_amount if cuisine_source == "depot" else 0.0

        if depot_net < 0:
            # depot négatif : dépôt à distribuer
            depot_available = abs(depot_net)
            service_owes_admin = 0.0

        else:
            # depot positif : le service doit remettre le dépôt à l'administration
            depot_available = 0.0
            service_owes_admin = self.round_cash_up(depot_net)


        """"Bussboys"""
        # zero si depot_available = 0 sinon combien le dépot couvre
        bussboy_sur_paye_distributed = min(bussboy_amount, (depot_available - depot_cuisine))
        # montant manquant du dépot pour couvrir bussboys, ROUND UP
        bussboy_cash_distributed = self.round_cash_up(bussboy_amount - bussboy_sur_paye_distributed)

        """Reste pour le service"""
        # dépot net apres bussboy payés ou zero si il en reste plus
        remaining_depot_for_service = max(0.0, depot_available - depot_cuisine - bussboy_sur_paye_distributed)
        # cash after paying the dépot and paying the bussboys, montant dù ou 0
        cash_available_for_service = max(0.0, cash_initial - service_owes_admin - cash_cuisine - bussboy_cash_distributed)

        """Frais admin"""
        service_ratio = self._get_dist_setting("frais_admin_service_ratio", 0.8)
        frais_admin_service = frais_admin * service_ratio

        return {
            "bussboy_sur_paye_distributed": bussboy_sur_paye_distributed,
            "bussboy_cash_distributed": bussboy_cash_distributed,
            "service_owes_admin": service_owes_admin,
            "remaining_depot_for_service": remaining_depot_for_service,
            "cash_available_for_service": cash_available_for_service,
            "frais_admin_service": frais_admin_service,
            "montant_cuisine": cuisine_amount,
            "cuisine_source": cuisine_source,
        }

    def declaration_net_values(self):
        ventes_totales, clients, tips_due, ventes_nourriture = self.get_declaration_inputs()
        tax_factor = 1.14975
        ventes_declarees = (ventes_totales - clients) / tax_factor if tax_factor != 0 else 0.0
        return {
            "ventes_declarees": ventes_declarees,
            "tips_due": tips_due,
            "ventes_nourriture": ventes_nourriture,
        }

    def _get_payroll_context(self):
        try:
            return self.shared_data.get("payroll", {}).get("context")
        except Exception:
            return None

    def _resolve_period_for_selected_date(self):
        if not self.selected_date_str:
            return None
        context = self._get_payroll_context()
        if not context:
            return None
        try:
            target_date = datetime.strptime(self.selected_date_str, "%d-%m-%Y").date()
        except ValueError:
            return None
        try:
            return context.period_for_local_date(target_date)
        except Exception:
            return None

    def get_active_pay_period(self):
        if self.current_period:
            return self.current_period
        period = self._resolve_period_for_selected_date()
        if period:
            self.current_period = period
        return period

    def on_payroll_context_updated(self):
        self.current_period = self._resolve_period_for_selected_date()
        self.update_pay_period_display()
        self.update_export_button_state()

    def calculate_cuisine_distribution(self, ventes_nourriture, depot_net):
        """Determine how cuisine amount is distributed (cash or depot)."""
        cuisine_pct = self._get_dist_setting("cuisine_percentage", 0.01)
        amount_cuisine = ventes_nourriture * cuisine_pct
        if depot_net < 0 and abs(depot_net) >= amount_cuisine:
            return amount_cuisine, "depot"
        return self.round_cash_up(amount_cuisine), "cash"

    def get_bussboy_percentage_and_amount(self):
        # Count bussboys
        bb_count = 0
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
                    bb_count += 1
                except (ValueError, TypeError):
                    continue

        base_percentage = self._get_dist_setting("bussboy_percentage", 0.025)
        bussboy_percentage = base_percentage if bb_count >= 1 else 0.0


        # Calculate amount
        ventes_net, _, _, _ = self.get_inputs()
        bussboy_amount = ventes_net * bussboy_percentage

        return bussboy_percentage, bussboy_amount

    def build_distribution_weights(self):
        """Extract weights (points*hours) for Service/Bussboy from the single tree."""
        self.dist_weights = {
            "Service": {"total": 0.0, "rows": {}},
            "Bussboy": {"total": 0.0, "rows": {}},
        }
        current = None

        def fnum(x):
            try:
                return float(str(x).strip().replace(",", "."))
            except Exception:
                return 0.0

        for item in self.tree.get_children():
            vals = self.tree.item(item)["values"]
            if not vals:
                continue
            name = vals[1] if len(vals) > 1 else ""
            if isinstance(name, str) and name.startswith("---"):
                if "Service" in name:
                    current = "Service"
                elif "Bussboy" in name:
                    current = "Bussboy"
                else:
                    current = None
                continue

            if not current:
                continue

            points = fnum(vals[2] if len(vals) > 2 else 0)
            hours = fnum(vals[3] if len(vals) > 3 else 0)
            w = points * hours
            key = (str(vals[0]), str(vals[1]))  # (number, name)
            self.dist_weights[current]["rows"][key] = w
            self.dist_weights[current]["total"] += w

    def distribution_bussboys(self):
        # Calculate totals and get net values
        _, bussboy_amount = self.get_bussboy_percentage_and_amount()
        net_values = self.distribution_net_values(bussboy_amount)

        # Ensure weights are built
        if not hasattr(self, "dist_weights"):
            self.build_distribution_weights()

        rows = self.dist_weights["Bussboy"]["rows"]
        total_w = self.dist_weights["Bussboy"]["total"]
        if total_w <= 0:
            return

        def fset(item, col, val):
            self.tree.set(item, col, f"{val:.2f}")

        # Walk tree and update bussboys using the stored weights
        current = None
        for item in self.tree.get_children():
            vals = self.tree.item(item)["values"]
            if not vals:
                continue
            name = vals[1] if len(vals) > 1 else ""
            if isinstance(name, str) and name.startswith("---"):
                current = "Bussboy" if "Bussboy" in name else None
                continue
            if current != "Bussboy":
                continue

            key = (str(vals[0]), str(vals[1]))
            w = rows.get(key, 0.0)
            if w <= 0:
                continue
            proportion = w / total_w
            sur_paye = proportion * net_values["bussboy_sur_paye_distributed"]
            cash = self.round_cash_down(proportion * net_values["bussboy_cash_distributed"])

            fset(item, "cash", sur_paye and cash or cash)  # set both
            fset(item, "sur_paye", sur_paye)

    def distribution_service(self):
        # Get distribution values
        _, bussboy_amount = self.get_bussboy_percentage_and_amount()
        net_values = self.distribution_net_values(bussboy_amount)
        remaining_depot = net_values["remaining_depot_for_service"]
        available_cash = net_values["cash_available_for_service"]
        frais_admin_service = net_values["frais_admin_service"]

        # Ensure weights are built
        if not hasattr(self, "dist_weights"):
            self.build_distribution_weights()

        rows = self.dist_weights["Service"]["rows"]
        total_w = self.dist_weights["Service"]["total"]
        if total_w <= 0:
            return

        def fset(item, col, val):
            self.tree.set(item, col, f"{val:.2f}")

        # Walk tree and update service using the stored weights
        current = None
        for item in self.tree.get_children():
            vals = self.tree.item(item)["values"]
            if not vals:
                continue
            name = vals[1] if len(vals) > 1 else ""
            if isinstance(name, str) and name.startswith("---"):
                current = "Service" if "Service" in name else None
                continue
            if current != "Service":
                continue

            key = (str(vals[0]), str(vals[1]))
            w = rows.get(key, 0.0)
            if w <= 0:
                continue
            proportion = w / total_w
            sur_paye = proportion * remaining_depot
            cash = self.round_cash_down(proportion * available_cash)
            admin = proportion * frais_admin_service

            fset(item, "cash", cash)
            fset(item, "sur_paye", sur_paye)
            fset(item, "frais_admin", admin)

    def update_declaration_values(self):
        """
        Service rows:
          A_i = Ventes déclarées * w_i / W_service
          B_i = Tips due         * w_i / W_service
          E_i = (Bussboy + cuisine) amount * w_i / W_service
          D_i = 0
          F_i = B_i + D_i - E_i = B_i - E_i
        Bussboy rows:
          A=B=E=0
          D = cash + sur_paye  (live from tree)
          F = B + D - E = D
        """
        if not hasattr(self, "dist_weights"):
            self.build_distribution_weights()

        svc = self.dist_weights["Service"]
        W_service = svc["total"]

        def fnum(x):
            try:
                return float(str(x).strip().replace(",", "."))
            except Exception:
                return 0.0

        def fset(item, col, val):
            self.tree.set(item, col, f"{val:.2f}")

        # Totals from inputs
        decl = self.declaration_net_values()
        ventes_decl_total = decl.get("ventes_declarees", 0.0)
        tips_due_total = decl.get("tips_due", 0.0)
        # Bussboy amount total from your existing rule
        _, bussboy_amount_total = self.get_bussboy_percentage_and_amount()

        # Cuisine amount total
        net_vals = self.distribution_net_values(bussboy_amount_total)
        cuisine_amount_total = net_vals.get("montant_cuisine", 0.0)

        # Ensure cuisine amount is still distributed even when bussboy amount is 0
        total_e_amount = cuisine_amount_total + bussboy_amount_total


        # First pass: locate section
        current = None
        for item in self.tree.get_children():
            vals = self.tree.item(item)["values"]
            if not vals:
                continue
            name = vals[1] if len(vals) > 1 else ""
            if isinstance(name, str) and name.startswith("---"):
                if "Service" in name:
                    current = "Service"
                elif "Bussboy" in name:
                    current = "Bussboy"
                else:
                    current = None
                continue

            if current == "Service":
                key = (str(vals[0]), str(vals[1]))
                w = svc["rows"].get(key, 0.0)
                if W_service > 0 and w > 0:
                    A = ventes_decl_total * (w / W_service)
                    B = tips_due_total * (w / W_service)
                    E = total_e_amount * (w / W_service)
                else:
                    A = B = E = 0.0
                D = 0.0
                F = B + D - E

                fset(item, "A", A)
                fset(item, "B", B)
                fset(item, "D", D)
                fset(item, "E", E)
                fset(item, "F", F)

            elif current == "Bussboy":
                cash = fnum(vals[4] if len(vals) > 4 else 0)
                surp = fnum(vals[5] if len(vals) > 5 else 0)
                D = cash + surp
                A = B = E = 0.0
                F = D

                fset(item, "A", A)
                fset(item, "B", B)
                fset(item, "D", D)
                fset(item, "E", E)
                fset(item, "F", F)

    def load_day_sheet_data(self):
        """Load timesheet data from shared_data with enhanced bundled app support"""
        transfer_data = self.shared_data.get("transfer")
        if not transfer_data:
            return

        entries = transfer_data.get("entries", [])
        selected_date = transfer_data.get("date", "??-??-????")
        
        self.selected_date_str = selected_date
        transfer_period = transfer_data.get("pay_period")
        if transfer_period:
            self.current_period = transfer_period
        else:
            self.current_period = self._resolve_period_for_selected_date()

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

        # Clear the tree completely
        self.tree.delete(*self.tree.get_children())
        
        # Update the date label
        self.date_label.config(text=f"Feuille du: {self.selected_date_str}")
        
        # Update pay period display
        self.update_pay_period_display()

        # Populate the tree with organized data
        tree_items = []
        for entry in organized_data:
            if entry.get("is_section"):
                item = self.tree.insert("", "end",
                                 values=("", entry["name"], "", "", "", "", "", "", "", "", "", ""),
                                 tags=("section",))
                tree_items.append(item)
            else:
                item = self.tree.insert("", "end", values=(
                    entry.get("number", ""),
                    entry.get("name", ""),
                    entry.get("points", ""),
                    entry.get("hours", ""),
                    "",  # CASH
                    "",  # Sur paye
                    "",  # Frais Admin
                    "",  # A
                    "",  # B
                    "",  # D
                    "",  # E
                    "",  # F
                ))
                tree_items.append(item)
        
        # Process the data
        try:
            self.process()
        except Exception as e:
            # Silently ignore processing errors to avoid console noise during UI flow
            pass

    def process(self):
        self.update_export_button_state()
        self._refresh_distribution_settings()

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

        self.update_label(self.service_owes_admin_label, net_values["service_owes_admin"], "À remettre", self.cash_color)

        self.update_label(self.service_sur_paye_label, net_values["remaining_depot_for_service"], "Sur Paye",self.sur_paye_color)
        self.update_label(self.service_cash_label, net_values["cash_available_for_service"], "Cash", self.cash_color)
        self.update_label(self.service_admin_fees_label, net_values["frais_admin_service"], "Frais Admin",self.sur_paye_color)

        cuisine_prefix = "CASH cuisine" if net_values["cuisine_source"] == "cash" else "ME DOIT cuisine"
        cuisine_color = self.cash_color if net_values["cuisine_source"] == "cash" else self.depot_color
        self.service_owes_cuisine_label.config(
            text=f"{cuisine_prefix}: {net_values['montant_cuisine']:.2f} $",
            foreground=cuisine_color if net_values["montant_cuisine"] != 0 else self.grey_color,
        )

        # 1) Use current rows to rebuild weights
        self.build_distribution_weights()

        # 2) Apply distribution values (cash/sur_paye/frais_admin)
        self.distribution_bussboys()
        self.distribution_service()

        # 3) Compute declaration values on the same rows (A,B,D,E,F)
        self.update_declaration_values()

        # 4) Update declaration summary label (already in your code)
        decl = self.declaration_net_values()
        self.ventes_declarees_label.config(text=f"Ventes déclarées: {decl['ventes_declarees']:.2f} $")
