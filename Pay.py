# Pay.py
# Shows combined pay-period data by employee.
# - Left: employee list (wider panel)
# - Right: summary + a dynamic scaffold table of shifts.
#   * Date column shows the source filename (no extension), e.g. "09-08-2025-SOIR"
#   * For Service employees -> columns: A, B, E, F
#   * For Busboys         -> columns: D
#   * Badge shows which rule determined "Déclaré" (8% of A vs F for Service; D for Busboy)
#   * Far-right header buttons: "Exporter tous (PDF)" and "Créer livret (PDF)"
#
# Storage model (JSONs are internal only):
#   JSON_ROOT = AppConfig.get_backend_dir()
#   - Daily distributions:  {JSON_ROOT}/daily/{pay_period}/*.json
#   - Pay summaries:        {JSON_ROOT}/pay/{pay_period}/combined.Json   (preferred)
#   Back-compat fallback (legacy):
#   - {app}/exports/pay/{pay_period}.Json
#
# PDFs are exported by Export.py to the user-chosen PDF folder (outside app),
# never into the JSON backend.

import os
import json
import re
import ttkbootstrap as ttk
from tkinter import StringVar, END, Listbox, Text, messagebox
from ttkbootstrap.constants import *

from AppConfig import get_backend_dir  # JSON_ROOT
from ui_scale import scale

class PayTab:
    def __init__(self, master):
        self.master = master
        self.frame = ttk.Frame(master)

        # JSON backend root (internal, user shouldn't need to browse here)
        self.json_root = get_backend_dir()
        self.pay_root_new = os.path.join(self.json_root, "pay")

        # Legacy fallback (read-only)
        self.legacy_backend_root = "exports"
        self.legacy_pay_dir = os.path.join(self.legacy_backend_root, "pay")

        # UI state
        self.selected_period_var = StringVar()   # shows the period label (e.g., "2025-06-08 au 2025-06-21")
        self.current_period_label = None
        self.current_payfile_path = None

        # Data built from the selected combined file
        self.employees_index = {}
        self.employee_keys_sorted = []

        # Discovered mapping: period_label -> absolute path to combined file
        self._period_to_path = {}

        self._build_ui()
        self.refresh_pay_files()
        self.frame.pack(fill=BOTH, expand=True)

    # -----------------------
    # UI
    # -----------------------
    def _build_ui(self):
        header = ttk.Frame(self.frame)
        header.pack(fill=X, padx=10, pady=(10, 6))

        # LEFT side of header (selector + refresh)
        left_box = ttk.Frame(header)
        left_box.pack(side=LEFT, fill=X, expand=True)

        ttk.Label(left_box, text="Période (JSON interne):").pack(side=LEFT)
        self.pay_file_menu = ttk.Combobox(left_box, textvariable=self.selected_period_var, state="readonly", width=44)
        self.pay_file_menu.pack(side=LEFT, padx=6)
        self.pay_file_menu.bind("<<ComboboxSelected>>", self.on_period_select)

        ttk.Button(left_box, text="Rafraîchir", command=self.refresh_pay_files).pack(side=LEFT, padx=6)

        # RIGHT side of header (export buttons pinned to far right)
        right_box = ttk.Frame(header)
        right_box.pack(side=RIGHT)

        ttk.Button(
            right_box, text="Créer livret (PDF)", bootstyle="primary", command=self.on_make_booklet
        ).pack(side=RIGHT, padx=6)
        ttk.Button(
            right_box, text="Exporter tous (PDF)", bootstyle="secondary", command=self.on_export_all
        ).pack(side=RIGHT, padx=6)

        # Paned layout so the employee panel is wider and resizable
        paned = ttk.Panedwindow(self.frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        # Left (Employee panel) — wider default width
        left = ttk.Frame(paned, width=scale(340))
        left.pack_propagate(False)
        paned.add(left, weight=1)

        ttk.Label(left, text="Employés").pack(anchor=W, padx=2, pady=(2, 4))
        self.employee_list = Listbox(left, height=24, width=40)
        self.employee_list.pack(fill=BOTH, expand=True)
        self.employee_list.bind("<<ListboxSelect>>", self.on_employee_select)

        # Right (Details panel)
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        summary_group = ttk.LabelFrame(right, text="Résumé — Employé sélectionné")
        summary_group.pack(fill=X, padx=0, pady=(0, 8))

        self.summary_text = Text(summary_group, height=4, wrap="word")
        self.summary_text.pack(fill=X, padx=6, pady=(6, 2))

        # Declared source badge
        indicator_row = ttk.Frame(summary_group)
        indicator_row.pack(fill=X, padx=6, pady=(0, 6))
        ttk.Label(indicator_row, text="Source du montant déclaré :").pack(side=LEFT)
        self.declared_source_label = ttk.Label(indicator_row, text="—", bootstyle="secondary")
        self.declared_source_label.pack(side=LEFT, padx=6)

        # Scaffold -> pretty table with dynamic columns
        scaffold_group = ttk.LabelFrame(right, text="Détaillé par quart")
        scaffold_group.pack(fill=BOTH, expand=True)

        # Define a superset of columns; we'll switch displaycolumns per role
        self.all_cols = ("date", "hours", "cash", "sur_paye", "frais_admin", "A", "B", "E", "F", "D")
        self.shift_tree = ttk.Treeview(scaffold_group, columns=self.all_cols, show="headings", height=14)

        # Headings and base column configs
        base_headings = {
            "date": "Date (fichier)",
            "hours": "Heures",
            "cash": "Cash",
            "sur_paye": "Sur Paye",
            "frais_admin": "Frais Admin",
            "A": "A",
            "B": "B",
            "E": "E",
            "F": "F",
            "D": "D",
        }
        widths = {
            "date": 160, "hours": 100, "cash": 110,
            "sur_paye": 110, "frais_admin": 120,
            "A": 80, "B": 80, "E": 80, "F": 80, "D": 80
        }
        anchors = {
            "date": "w", "hours": "e", "cash": "e",
            "sur_paye": "e", "frais_admin": "e",
            "A": "e", "B": "e", "E": "e", "F": "e", "D": "e"
        }

        for c in self.all_cols:
            self.shift_tree.heading(c, text=base_headings[c])
            w = scale(widths[c])
            self.shift_tree.column(c, width=w, minwidth=w, anchor=anchors[c], stretch=True)

        # Zebra striping via tags
        self.shift_tree.tag_configure("odd", background="#f7f7fa")
        self.shift_tree.tag_configure("even", background="#ffffff")

        self.shift_tree.pack(fill=BOTH, expand=True, padx=6, pady=6)

    # -----------------------
    # Load combined files (new layout + legacy fallback)
    # -----------------------
    def refresh_pay_files(self):
        self._period_to_path = {}

        # New preferred layout: {JSON_ROOT}/pay/{period}/combined.Json
        try:
            if os.path.isdir(self.pay_root_new):
                for period in os.listdir(self.pay_root_new):
                    pdir = os.path.join(self.pay_root_new, period)
                    if not os.path.isdir(pdir):
                        continue
                    # Prefer 'combined.Json' if present; else any *.Json inside
                    preferred = os.path.join(pdir, "combined.Json")
                    if os.path.isfile(preferred):
                        self._period_to_path[period] = preferred
                    else:
                        candidates = [f for f in os.listdir(pdir) if f.endswith(".Json")]
                        if candidates:
                            self._period_to_path[period] = os.path.join(pdir, sorted(candidates)[0])
        except Exception:
            pass

        # Legacy fallback: exports/pay/{period}.Json (only if not found in new map)
        try:
            if os.path.isdir(self.legacy_pay_dir):
                for name in os.listdir(self.legacy_pay_dir):
                    if name.endswith(".Json"):
                        period = os.path.splitext(name)[0]
                        self._period_to_path.setdefault(period, os.path.join(self.legacy_pay_dir, name))
        except Exception:
            pass

        periods = sorted(self._period_to_path.keys())
        current = (self.selected_period_var.get() or "").strip()

        self.pay_file_menu["values"] = periods
        if current in periods:
            self.selected_period_var.set(current)
        elif periods:
            self.selected_period_var.set(periods[0])
        else:
            self.selected_period_var.set("")

        self.on_period_select()

    def on_period_select(self, event=None):
        self._clear_employees()
        self._clear_detail()

        label = (self.selected_period_var.get() or "").strip()
        if not label:
            self.current_payfile_path = None
            self.current_period_label = None
            return

        path = self._period_to_path.get(label)
        if not path or not os.path.isfile(path):
            messagebox.showerror("Erreur", f"Fichier combiné introuvable pour la période:\n{label}")
            return

        self.current_payfile_path = path
        self.current_period_label = label

        try:
            with open(path, "r", encoding="utf-8") as f:
                combined = json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier combiné:\n{e}")
            return

        self._index_employees_with_shifts(combined)

        self.employee_list.delete(0, END)
        for k in self.employee_keys_sorted:
            info = self.employees_index[k]
            self.employee_list.insert(END, _employee_display(info["id"], info["name"], info["role"]))

    # -----------------------
    # Indexing employees & shifts
    # -----------------------
    def _index_employees_with_shifts(self, combined: dict):
        """
        employees_index[key] = {
            "id","name","role",
            "shifts":[{display_name,date,shift,hours,cash,sur_paye,frais_admin,A,B,D,E,F}],
            "totals": {"hours","cash","sur_paye","frais_admin","A_sum","F_sum","D_sum"}
        }
        Accepts the structure created by JsonViewerTab or any tool that
        writes a top-level {"distributions":[{"filename":..., "content":{...}}]} array.
        """
        self.employees_index.clear()
        self.employee_keys_sorted.clear()

        dists = combined.get("distributions", [])
        for item in dists:
            if "error" in item:
                continue
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue

            # Prefer embedded meta; fallback to filename parsing
            meta = content.get("meta", {})
            date = safe_str(meta.get("date"))
            shift = safe_str(meta.get("shift"))
            fname_no_ext = os.path.splitext(item.get("filename", ""))[0]

            if not date or not shift:
                parsed_date, parsed_shift = _parse_date_shift_from_filename(fname_no_ext)
                date = date or parsed_date
                shift = shift or parsed_shift

            employees = content.get("employees", [])
            if not isinstance(employees, list):
                continue

            for emp in employees:
                if not isinstance(emp, dict):
                    continue
                emp_id = emp.get("employee_id")
                name = safe_str(emp.get("name"))
                role = safe_str(emp.get("role") or emp.get("section"))

                key = str(emp_id) if emp_id not in (None, "") else f"name::{name}"
                if key not in self.employees_index:
                    self.employees_index[key] = {
                        "id": emp_id if emp_id not in (None, "") else "",
                        "name": name,
                        "role": role,
                        "shifts": [],
                        "totals": {
                            "hours": 0.0,
                            "cash": 0.0,
                            "sur_paye": 0.0,
                            "frais_admin": 0.0,
                            "A_sum": 0.0,
                            "F_sum": 0.0,
                            "D_sum": 0.0
                        }
                    }

                hours = to_float(emp.get("hours", 0.0))
                cash = to_float(emp.get("cash", 0.0))
                sur_paye = to_float(emp.get("sur_paye", 0.0))
                frais_admin = to_float(emp.get("frais_admin", 0.0))
                A_val = to_float(emp.get("A", 0.0))
                F_val = to_float(emp.get("F", 0.0))
                D_val = to_float(emp.get("D", 0.0))
                B_val = emp.get("B", "")
                E_val = emp.get("E", "")

                self.employees_index[key]["shifts"].append({
                    "display_name": fname_no_ext,  # For the Date column
                    "date": date, "shift": shift,
                    "hours": hours, "cash": cash, "sur_paye": sur_paye,
                    "frais_admin": frais_admin,
                    "A": A_val, "B": B_val, "D": D_val, "E": E_val, "F": F_val
                })

                t = self.employees_index[key]["totals"]
                t["hours"] += hours
                t["cash"] += cash
                t["sur_paye"] += sur_paye
                t["frais_admin"] += frais_admin
                t["A_sum"] += A_val
                t["F_sum"] += F_val
                t["D_sum"] += D_val

        # Sort shifts within each employee
        for key in self.employees_index:
            self.employees_index[key]["shifts"].sort(key=lambda s: (safe_str(s["date"]), safe_str(s["shift"])))

        # Sort employees by role then name
        self.employee_keys_sorted = sorted(
            self.employees_index.keys(),
            key=lambda k: (safe_str(self.employees_index[k]["role"]).lower(),
                           safe_str(self.employees_index[k]["name"]).lower())
        )

    # -----------------------
    # Interaction
    # -----------------------
    def on_employee_select(self, event=None):
        sel = self.employee_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < 0 or idx >= len(self.employee_keys_sorted):
            return

        key = self.employee_keys_sorted[idx]
        info = self.employees_index.get(key)
        if not info:
            return

        t = info["totals"]
        declared_val = amount_declared(t, info["role"])

        # Badge source
        role_lower = (info["role"] or "").lower()
        if "service" in role_lower:
            a_floor = 0.08 * t.get("A_sum", 0.0)
            f_total = t.get("F_sum", 0.0)
            used_a_floor = a_floor >= f_total
            if used_a_floor:
                self.declared_source_label.config(text="Pourboire déclaré selon 8% des ventes", bootstyle="warning")
            else:
                self.declared_source_label.config(text="Déclaré basé sur montant F", bootstyle="info")
        elif "bussboy" in role_lower or "busboy" in role_lower:
            self.declared_source_label.config(text="Déclaré basé sur montant D", bootstyle="secondary")
        else:
            self.declared_source_label.config(text="Déclaré basé sur: —", bootstyle="secondary")

        # Summary (top)
        self.summary_text.delete("1.0", END)
        lines = [
            f"Employé: {info['name']}  (ID: {info['id'] or '—'}  |  Rôle: {info['role'] or '—'})",
            f"Période: {self.current_period_label or '—'}",
            f"Quarts: {len(info['shifts'])}",
            f"Totaux → Heures: {fmt_num(t['hours'], hours=True)} | Cash: {fmt_num(t['cash'])} | "
            f"Sur Paye: {fmt_num(t['sur_paye'])} | Frais Admin: {fmt_num(t['frais_admin'])} | "
            f"Déclaré: {fmt_num(declared_val)}"
        ]
        self.summary_text.insert(END, "\n".join(lines))

        # Fill the scaffold table, adapting columns by role
        for iid in self.shift_tree.get_children():
            self.shift_tree.delete(iid)

        if "service" in role_lower:
            display_cols = ("date", "hours", "cash", "sur_paye", "frais_admin", "A", "B", "E", "F")
        elif "bussboy" in role_lower or "busboy" in role_lower:
            display_cols = ("date", "hours", "cash", "sur_paye", "frais_admin", "D")
        else:
            # Fallback: show just the base cols if role is unknown
            display_cols = ("date", "hours", "cash", "sur_paye", "frais_admin")

        # Apply displaycolumns dynamically
        self.shift_tree["displaycolumns"] = display_cols

        # Insert rows: we always provide the superset order values;
        # only the columns in displaycolumns are shown.
        row_idx = 0
        for s in info["shifts"]:
            date_display = safe_str(s.get("display_name") or s.get("date"))
            values = (
                date_display,
                fmt_num(s["hours"], hours=True),
                fmt_num(s["cash"]),
                fmt_num(s["sur_paye"]),
                fmt_num(s["frais_admin"]),
                fmt_num(s.get("A", 0.0)) if "A" in self.all_cols else "",
                safe_str(s.get("B", "")) if "B" in self.all_cols else "",
                safe_str(s.get("E", "")) if "E" in self.all_cols else "",
                fmt_num(s.get("F", 0.0)) if "F" in self.all_cols else "",
                fmt_num(s.get("D", 0.0)) if "D" in self.all_cols else "",
            )
            tag = "even" if row_idx % 2 == 0 else "odd"
            self.shift_tree.insert("", END, values=values, tags=(tag,))
            row_idx += 1

    # -----------------------
    # Export handlers (call Export.py)
    # -----------------------
    def on_export_all(self):
        if not self.current_period_label:
            messagebox.showwarning("Export PDF", "Aucune période sélectionnée.")
            return
        if not self.employees_index:
            messagebox.showwarning("Export PDF", "Aucun employé à exporter.")
            return

        try:
            from Export import export_all_employee_pdfs
            # Export.py writes to {PDF_ROOT}/Paye/{period}/...
            paths = export_all_employee_pdfs(self.current_period_label, self.employees_index, out_dir="")
        except Exception as e:
            messagebox.showerror("Export PDF", f"Erreur d'export:\n{e}")
            return

        if paths:
            target_dir = os.path.dirname(paths[0])
            messagebox.showinfo("Export PDF", f"{len(paths)} fichiers créés dans:\n{target_dir}")
        else:
            messagebox.showinfo("Export PDF", "Aucun fichier PDF n'a été créé.")

    def on_make_booklet(self):
        if not self.current_period_label:
            messagebox.showwarning("Livret PDF", "Aucune période sélectionnée.")
            return
        if not self.employees_index:
            messagebox.showwarning("Livret PDF", "Aucun employé à inclure.")
            return

        try:
            from Export import export_all_employee_pdfs, make_booklet
            pdfs = export_all_employee_pdfs(self.current_period_label, self.employees_index, out_dir="")
            booklet_name_guess = f"{self.current_period_label}_ALL.pdf"
            booklet_path = make_booklet(self.current_period_label, pdfs, booklet_name_guess)
        except Exception as e:
            messagebox.showerror("Livret PDF", f"Erreur lors de la création du livret:\n{e}")
            return

        messagebox.showinfo("Livret PDF", f"Livret créé:\n{booklet_path}")

    # -----------------------
    # Helpers
    # -----------------------
    def _clear_employees(self):
        self.employee_list.delete(0, END)
        self.employees_index.clear()
        self.employee_keys_sorted.clear()

    def _clear_detail(self):
        self.summary_text.delete("1.0", END)
        self.declared_source_label.config(text="—", bootstyle="secondary")
        for iid in getattr(self, "shift_tree", []).get_children() if hasattr(self, "shift_tree") else []:
            self.shift_tree.delete(iid)

# -----------------------
# Utility helpers
# -----------------------
def amount_declared(totals: dict, role: str) -> float:
    """Return declared amount based on role-specific rules."""
    role_lower = (role or "").lower()
    if "service" in role_lower:
        return max(0.08 * totals.get("A_sum", 0.0), totals.get("F_sum", 0.0))
    elif "bussboy" in role_lower or "busboy" in role_lower:
        return totals.get("D_sum", 0.0)
    return 0.0

def _employee_display(emp_id, name, role):
    id_part = f"{emp_id}" if emp_id not in (None, "") else "—"
    role_part = f" ({role})" if role else ""
    return f"{id_part} — {name}{role_part}"

def _parse_date_shift_from_filename(filename: str):
    try:
        # Accept "2025-06-08_Soir" or "09-08-2025-SOIR" styles; prefer ISO if present
        m_iso = re.search(r"(\d{4}-\d{2}-\d{2})[_\-]([A-Za-zÀ-ÖØ-öø-ÿ]+)", filename)
        if m_iso:
            return m_iso.group(1), m_iso.group(2)
        m_alt = re.search(r"(\d{2}-\d{2}-\d{4})[_\-]([A-Za-zÀ-ÖØ-öø-ÿ]+)", filename)
        if m_alt:
            return m_alt.group(1), m_alt.group(2)
    except Exception:
        pass
    return "", ""

def safe_str(x):
    return "" if x is None else str(x)

def to_float(x):
    """
    Robust numeric parser:
    - Accepts numbers, '12,50', '$12.50', '  12.50  ', etc.
    - Strips everything except digits, minus, and dot; converts comma to dot first.
    """
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if not s:
            return 0.0
        s = s.replace(",", ".")
        s = re.sub(r"[^0-9\.\-]+", "", s)
        if s in ("", "-", ".", "-.", ".-"):
            return 0.0
        return float(s)
    except Exception:
        return 0.0

def fmt_num(x, hours=False):
    try:
        val = float(x)
        if hours:
            return f"{val:.4f}".rstrip("0").rstrip(".") if abs(val) < 10 else f"{val:.2f}"
        return f"{val:.2f}"
    except Exception:
        return str(x)
