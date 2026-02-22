# JsonViewerTab.py — distribution review & confirmation (SQLite-backed)

import ttkbootstrap as ttk
from tkinter import messagebox
from tkinter import StringVar, END, Listbox
from tkinter.scrolledtext import ScrolledText
from ttkbootstrap.constants import *

from ui_scale import scale
from tree_utils import fit_columns
from db.distributions_repo import (
    delete_distribution,
    get_distribution,
    list_distributions,
    list_period_ids_with_distributions,
    set_distribution_status,
)

try:
    from payroll.context import PayrollContext
    from payroll.pay_calendar import PayCalendarService
except Exception:
    PayrollContext = None
    PayCalendarService = None


class JsonViewerTab:
    def __init__(self, master, shared_data=None):
        self.master = master
        self.frame = ttk.Frame(master)
        self.shared_data = shared_data or {}
        self.payroll_context = self._resolve_payroll_context()

        # UI state
        self.pay_period_var = StringVar()
        self.json_file_var = StringVar()
        self.current_dist_id = None
        self.current_file_source = None  # 'unconfirmed' or 'confirmed'
        self.view_mode = StringVar(value="distribution")

        # Map pay-period label -> period info
        self.period_map = {}
        self.current_period = None

        # Cached distribution lists (index aligned to listbox entries)
        self.unconfirmed_entries = []
        self.confirmed_entries = []

        self._build_ui()
        self.refresh_pay_periods()
        self.frame.pack(fill="both", expand=True)

    def _resolve_payroll_context(self):
        try:
            payroll = self.shared_data.get("payroll", {})
            ctx = payroll.get("context")
            if ctx:
                return ctx
        except Exception:
            pass
        if PayrollContext and PayCalendarService:
            try:
                return PayrollContext(PayCalendarService())
            except Exception:
                return None
        return None

    def _format_local_ts(self, ts: str) -> str:
        """Convert ISO UTC timestamps to local time for display."""
        if not ts:
            return ""
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_local = dt.astimezone()
            return dt_local.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ts

    def _build_ui(self):
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=X, pady=5, padx=10)

        ttk.Label(header_frame, text="Période de paye:").pack(side=LEFT)
        self.period_menu = ttk.Combobox(header_frame, textvariable=self.pay_period_var, state="readonly", width=28)
        self.period_menu.pack(side=LEFT, padx=5)
        self.period_menu.bind("<<ComboboxSelected>>", self.on_period_select)

        ttk.Button(
            header_frame,
            text="Rafraîchir",
            command=self.refresh_pay_periods,
            bootstyle=INFO,
        ).pack(side=LEFT, padx=5)

        # View toggle (right side)
        view_frame = ttk.Frame(header_frame)
        view_frame.pack(side=RIGHT)
        self.view_dist_btn = ttk.Button(
            view_frame, text="Vue Distribution", bootstyle="primary",
            command=lambda: self.set_view_mode("distribution")
        )
        self.view_decl_btn = ttk.Button(
            view_frame, text="Vue Déclaration", bootstyle="outline-primary",
            command=lambda: self.set_view_mode("declaration")
        )
        self.view_dist_btn.pack(side=LEFT)
        self.view_decl_btn.pack(side=LEFT, padx=6)

        # Distribution lists (unconfirmed vs confirmed)
        list_frame = ttk.Frame(self.frame)
        list_frame.pack(fill=X, padx=10, pady=(2, 0))

        # Unconfirmed files
        unconf_frame = ttk.Frame(list_frame)
        unconf_frame.pack(side=LEFT, fill=BOTH, expand=True)
        ttk.Label(unconf_frame, text="Nouvelles distributions NON-vérifiés").pack(anchor=W)
        unconf_lb_frame = ttk.Frame(unconf_frame)
        unconf_lb_frame.pack(fill=X, pady=5)
        self.unconfirmed_listbox = Listbox(unconf_lb_frame, height=6)
        self.unconfirmed_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        unconf_scroll = ttk.Scrollbar(unconf_lb_frame, orient=VERTICAL, command=self.unconfirmed_listbox.yview)
        unconf_scroll.pack(side=RIGHT, fill=Y)
        self.unconfirmed_listbox.config(yscrollcommand=unconf_scroll.set)
        self.unconfirmed_listbox.bind(
            "<<ListboxSelect>>", lambda e: self.on_file_select(e, source="unconfirmed")
        )

        self.delete_btn = ttk.Button(
            unconf_frame,
            text="Supprimer cette distribution",
            bootstyle=DANGER,
            command=self.delete_selected_file,
            state=DISABLED,
        )
        self.delete_btn.pack(fill=X, pady=(0, 5))

        # Transfer button between lists
        transfer_frame = ttk.Frame(list_frame)
        transfer_frame.pack(side=LEFT, fill=Y, padx=5)
        self.transfer_btn = ttk.Button(
            transfer_frame,
            text="-->",
            command=self.confirm_selected_file,
            state=DISABLED,
            width=3,
            bootstyle=SUCCESS,
        )
        self.transfer_btn.pack(pady=(20, 5))
        self.transfer_back_btn = ttk.Button(
            transfer_frame,
            text="<--",
            command=self.unconfirm_selected_file,
            state=DISABLED,
            width=3,
            bootstyle=WARNING,
        )
        self.transfer_back_btn.pack()

        # Confirmed files
        conf_frame = ttk.Frame(list_frame)
        conf_frame.pack(side=LEFT, fill=BOTH, expand=True)
        ttk.Label(conf_frame, text="Distributions confirmées").pack(anchor=W)
        conf_lb_frame = ttk.Frame(conf_frame)
        conf_lb_frame.pack(fill=X, pady=5)
        self.confirmed_listbox = Listbox(conf_lb_frame, height=6)
        self.confirmed_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        conf_scroll = ttk.Scrollbar(conf_lb_frame, orient=VERTICAL, command=self.confirmed_listbox.yview)
        conf_scroll.pack(side=RIGHT, fill=Y)
        self.confirmed_listbox.config(yscrollcommand=conf_scroll.set)
        self.confirmed_listbox.bind(
            "<<ListboxSelect>>", lambda e: self.on_file_select(e, source="confirmed")
        )

        ttk.Label(
            conf_frame,
            text="(Le fichier combiné n'est plus requis)",
            bootstyle="secondary",
        ).pack(fill=X)

        self.file_info_var = StringVar(value="Aucune distribution sélectionné")

        ttk.Label(
            self.frame, textvariable=self.file_info_var, bootstyle="info"
        ).pack(anchor=W, padx=10, pady=(5, 5))

        # Input summaries shown side by side
        inputs_wrapper = ttk.Frame(self.frame)
        inputs_wrapper.pack(fill=X, expand=False, padx=10, pady=(0, 5))

        input_frame = ttk.LabelFrame(inputs_wrapper, text="Valeurs entrées (Distribution)")
        input_frame.pack(side=LEFT, fill=BOTH, expand=True)
        self.inputs_text = ScrolledText(input_frame, height=6, wrap="none")
        self.inputs_text.pack(fill=BOTH, expand=True)

        decl_input_frame = ttk.LabelFrame(inputs_wrapper, text="Paramètres de déclaration")
        decl_input_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0))
        self.decl_inputs_text = ScrolledText(decl_input_frame, height=6, wrap="none")
        self.decl_inputs_text.pack(fill=BOTH, expand=True)

        # Employees Treeview
        emp_frame = ttk.LabelFrame(self.frame, text="Données des employés")
        emp_frame.pack(fill=BOTH, expand=True, padx=10, pady=(5, 10))

        columns = (
            "id",
            "name",
            "hours",
            "cash",
            "sur_paye",
            "frais_admin",
            "A",
            "B",
            "D",
            "E",
            "F",
            "section",
        )

        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=scale(25))
        tree_container = ttk.Frame(emp_frame)
        tree_container.pack(fill=BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_container, columns=columns, show="headings", style="Custom.Treeview"
        )
        headings = {
            "id": "Numéro",
            "name": "Nom",
            "hours": "Heures",
            "cash": "Cash",
            "sur_paye": "Sur Paye",
            "frais_admin": "Frais Admin",
            "A": "A",
            "B": "B",
            "D": "D",
            "E": "E",
            "F": "F",
            "section": "Section",
        }
        self._width_map = {}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "w" if col in ("name", "section") else "center"
            width = 180 if col == "name" else (90 if col not in ("section",) else 110)
            scaled_width = scale(width)
            self._width_map[col] = scaled_width
            self.tree.column(col, anchor=anchor, width=scaled_width, minwidth=scale(20), stretch=True)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_scroll_y = ttk.Scrollbar(tree_container, orient=VERTICAL, command=self.tree.yview)
        tree_scroll_y.pack(side=RIGHT, fill=Y)
        tree_scroll_x = ttk.Scrollbar(emp_frame, orient=HORIZONTAL, command=self.tree.xview)
        tree_scroll_x.pack(fill=X)
        self.tree.config(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        fit_columns(self.tree, self._width_map)

        # Default to Distribution view
        self.show_distribution_view()

    # -----------------------
    # View switching
    # -----------------------
    def show_distribution_view(self):
        self.tree["displaycolumns"] = ("id", "name", "hours", "cash", "sur_paye", "frais_admin", "section")
        self.view_mode.set("distribution")
        self.view_dist_btn.config(bootstyle="primary")
        self.view_decl_btn.config(bootstyle="outline-primary")

    def show_declaration_view(self):
        self.tree["displaycolumns"] = ("id", "name", "hours", "A", "B", "D", "E", "F", "section")
        self.view_mode.set("declaration")
        self.view_dist_btn.config(bootstyle="outline-primary")
        self.view_decl_btn.config(bootstyle="primary")

    def set_view_mode(self, mode):
        if mode == "declaration":
            self.show_declaration_view()
        else:
            self.show_distribution_view()

    # -----------------------
    # Pay period loading
    # -----------------------
    def refresh_pay_periods(self):
        self.period_map = {}
        period_ids = list_period_ids_with_distributions()
        periods = []
        for pid in period_ids:
            info = {"id": pid}
            if self.payroll_context:
                try:
                    info = self.payroll_context.get_period(pid)
                except Exception:
                    info = {"id": pid}
            range_label = info.get("range_label")
            label = range_label or info.get("display_id") or pid
            periods.append((label, info))

        periods.sort(key=lambda item: item[1].get("start_at_utc", ""), reverse=True)
        self.period_menu["values"] = [label for label, _ in periods]
        for label, info in periods:
            self.period_map[label] = info

        # Preserve selection if possible, otherwise select first available
        current = (self.pay_period_var.get() or "").strip()
        if current in self.period_map:
            self.pay_period_var.set(current)
        elif self.period_map:
            self.pay_period_var.set(list(self.period_map.keys())[0])
        else:
            self.pay_period_var.set("")

        # Trigger list refresh
        self.on_period_select()

    def on_period_select(self, event=None):
        # Reset lists and current selection
        self.unconfirmed_listbox.delete(0, END)
        self.confirmed_listbox.delete(0, END)
        self.clear_treeviews()
        self.file_info_var.set("Aucune distribution sélectionnée!")
        self.current_dist_id = None
        self.current_file_source = None
        self.delete_btn.config(state=DISABLED)
        self.transfer_btn.config(state=DISABLED)
        self.transfer_back_btn.config(state=DISABLED)
        self.unconfirmed_entries = []
        self.confirmed_entries = []

        label = (self.pay_period_var.get() or "").strip()
        if not label:
            self.current_period = None
            return

        self.current_period = self.period_map.get(label)
        if not self.current_period:
            return

        period_id = self.current_period.get("id")
        unconfirmed = list_distributions(pay_period_id=period_id, status="UNCONFIRMED")
        confirmed = list_distributions(pay_period_id=period_id, status="CONFIRMED")

        self.unconfirmed_entries = unconfirmed
        self.confirmed_entries = confirmed

        for row in unconfirmed:
            shift = row.get("shift", "")
            inst = row.get("shift_instance", 1)
            shift_label = f"{shift} #{inst}" if inst and int(inst) > 1 else shift
            display = f"{row.get('date_local', '')} {shift_label} — {row.get('dist_ref', '')}"
            self.unconfirmed_listbox.insert(END, display)

        for row in confirmed:
            shift = row.get("shift", "")
            inst = row.get("shift_instance", 1)
            shift_label = f"{shift} #{inst}" if inst and int(inst) > 1 else shift
            display = f"{row.get('date_local', '')} {shift_label} — {row.get('dist_ref', '')}"
            self.confirmed_listbox.insert(END, display)

    # -----------------------
    # File selection & display
    # -----------------------
    def on_file_select(self, event, source):
        # Ensure only one listbox has a selection
        if source == "unconfirmed":
            selection = self.unconfirmed_listbox.curselection()
            self.confirmed_listbox.selection_clear(0, END)
            entries = self.unconfirmed_entries
        else:
            selection = self.confirmed_listbox.curselection()
            self.unconfirmed_listbox.selection_clear(0, END)
            entries = self.confirmed_entries

        if not selection or not entries:
            return

        idx = selection[0]
        if idx < 0 or idx >= len(entries):
            return
        dist_id = entries[idx].get("id")
        self.current_dist_id = dist_id
        self.current_file_source = source
        dist = get_distribution(dist_id)
        if not dist:
            messagebox.showerror("Erreur", "Distribution introuvable.")
            return
        ts = dist.get("created_at") or ""
        ts_local = self._format_local_ts(ts)
        dist_ref = dist.get("dist_ref") or ""
        self.file_info_var.set(f"Distribution sélectionnée: {dist_ref} // Créée le: {ts_local}")

        try:
            self.clear_treeviews()

            # Distribution inputs
            inputs = dist.get("inputs", {})
            self.inputs_text.delete("1.0", END)
            for key, val in inputs.items():
                self.inputs_text.insert(END, f"{key}: {val}\n")

            # Declaration inputs
            decl_inputs = dist.get("declaration_inputs", {})
            self.decl_inputs_text.delete("1.0", END)
            if decl_inputs:
                for key, val in decl_inputs.items():
                    self.decl_inputs_text.insert(END, f"{key}: {val}\n")
            else:
                self.decl_inputs_text.insert(END, "(Aucune donnée de déclaration)")

            # Employees rows (supports both views)
            for emp in dist.get("employees", []):
                if not isinstance(emp, dict):
                    continue

                def _fmt(x):
                    return "" if x in ("", None) else str(x)

                self.tree.insert(
                    "",
                    END,
                    values=(
                        emp.get("employee_number", ""),
                        emp.get("employee_name", ""),
                        emp.get("hours", 0.0),
                        emp.get("cash", 0.0),
                        emp.get("sur_paye", 0.0),
                        emp.get("frais_admin", 0.0),
                        _fmt(emp.get("A", "")),
                        _fmt(emp.get("B", "")),
                        _fmt(emp.get("D", "")),
                        _fmt(emp.get("E", "")),
                        _fmt(emp.get("F", "")),
                        emp.get("section", ""),
                    ),
                )

            # Keep current view mode after loading
            if self.view_mode.get() == "declaration":
                self.show_declaration_view()
            else:
                self.show_distribution_view()

            if source == "unconfirmed":
                self.delete_btn.config(state=NORMAL)
                self.transfer_btn.config(state=NORMAL)
                self.transfer_back_btn.config(state=DISABLED)
            else:
                self.delete_btn.config(state=DISABLED)
                self.transfer_btn.config(state=DISABLED)
                self.transfer_back_btn.config(state=NORMAL)

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d’afficher la distribution:\n{type(e).__name__}: {e}")

    def clear_treeviews(self):
        self.inputs_text.delete("1.0", END)
        self.decl_inputs_text.delete("1.0", END)
        for item in self.tree.get_children():
            self.tree.delete(item)

    # -----------------------
    # Delete action
    # -----------------------
    def delete_selected_file(self):
        if not self.current_dist_id or self.current_file_source != "unconfirmed":
            messagebox.showwarning(
                "Sélection requise",
                "Veuillez sélectionner une distribution NON-vérifié à supprimer.",
            )
            return
        confirm = messagebox.askyesno(
            "Confirmer la suppression",
            "Êtes-vous sûr de vouloir supprimer cette distribution ?"
        )
        if confirm:
            try:
                delete_distribution(self.current_dist_id)
                messagebox.showinfo("Supprimé", "Distribution supprimée avec succès.")
                self.on_period_select(None)
                self.current_dist_id = None
                self.current_file_source = None
                self.file_info_var.set("Aucune distribution sélectionnée")
                self.clear_treeviews()
                self.transfer_btn.config(state=DISABLED)
                self.transfer_back_btn.config(state=DISABLED)
                self.delete_btn.config(state=DISABLED)
            except Exception as e:
                messagebox.showerror("Erreur", f"Échec de la suppression:\n{str(e)}")

    def confirm_selected_file(self):
        """Mark the selected distribution as confirmed."""
        if not self.current_dist_id or self.current_file_source != "unconfirmed":
            messagebox.showwarning(
                "Sélection requise",
                "Veuillez sélectionner une distribution NON-vérifiée à confirmer.",
            )
            return
        try:
            set_distribution_status(self.current_dist_id, "CONFIRMED")
            messagebox.showinfo("Confirmé", "Distribution confirmée.")
            self.on_period_select(None)
            self.current_dist_id = None
            self.current_file_source = None
            self.file_info_var.set("Aucune distribution sélectionnée")
            self.clear_treeviews()
            self.transfer_btn.config(state=DISABLED)
            self.transfer_back_btn.config(state=DISABLED)
            self.delete_btn.config(state=DISABLED)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec du transfert:\n{e}")

    def unconfirm_selected_file(self):
        """Mark the selected distribution as unconfirmed."""
        if not self.current_dist_id or self.current_file_source != "confirmed":
            messagebox.showwarning(
                "Sélection requise",
                "Veuillez sélectionner un fichier confirmé à retourner.",
            )
            return
        try:
            set_distribution_status(self.current_dist_id, "UNCONFIRMED")
            messagebox.showinfo("Retourné", "Distribution retournée aux NON-vérifiées.")
            self.on_period_select(None)
            self.current_dist_id = None
            self.current_file_source = None
            self.file_info_var.set("Aucun fichier sélectionné")
            self.clear_treeviews()
            self.transfer_btn.config(state=DISABLED)
            self.transfer_back_btn.config(state=DISABLED)
            self.delete_btn.config(state=DISABLED)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec du transfert:\n{e}")
