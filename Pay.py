import os
import json
import re
import ttkbootstrap as ttk
from tkinter import StringVar, END, Listbox, Text, messagebox
from ttkbootstrap.constants import *

class PayTab:
    def __init__(self, master):
        self.master = master
        self.frame = ttk.Frame(master)

        # Folder structure
        self.exports_root = "exports"
        self.export_folders = {
            "pdf": os.path.join(self.exports_root, "pdf"),
            "json": os.path.join(self.exports_root, "json"),
            "pay": os.path.join(self.exports_root, "pay"),
        }
        for p in self.export_folders.values():
            os.makedirs(p, exist_ok=True)

        # UI state
        self.selected_payfile_var = StringVar()
        self.current_payfile_path = None
        self.current_period_label = None

        # Data built from the selected combined file
        self.employees_index = {}
        self.employee_keys_sorted = []

        self._build_ui()
        self.refresh_pay_files()
        self.frame.pack(fill=BOTH, expand=True)

    # -----------------------
    # UI
    # -----------------------
    def _build_ui(self):
        header = ttk.Frame(self.frame)
        header.pack(fill=X, padx=10, pady=(10, 6))

        ttk.Label(header, text="Fichier combiné (exports/pay):").pack(side=LEFT)
        self.pay_file_menu = ttk.Combobox(header, textvariable=self.selected_payfile_var, state="readonly", width=44)
        self.pay_file_menu.pack(side=LEFT, padx=6)
        self.pay_file_menu.bind("<<ComboboxSelected>>", self.on_payfile_select)

        ttk.Button(header, text="Rafraîchir", command=self.refresh_pay_files).pack(side=LEFT, padx=6)

        body = ttk.Frame(self.frame)
        body.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(body)
        left.pack(side=LEFT, fill=Y, padx=(0, 8))

        ttk.Label(left, text="Employés").pack(anchor=W)
        self.employee_list = Listbox(left, height=20)
        self.employee_list.pack(fill=Y, expand=True)
        self.employee_list.bind("<<ListboxSelect>>", self.on_employee_select)

        right = ttk.Frame(body)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        summary_group = ttk.LabelFrame(right, text="Résumé — Employé sélectionné")
        summary_group.pack(fill=X, padx=0, pady=(0, 8))
        self.summary_text = Text(summary_group, height=4, wrap="word")
        self.summary_text.pack(fill=X, padx=6, pady=6)

        scaffold_group = ttk.LabelFrame(right, text="Quarts (scaffold)")
        scaffold_group.pack(fill=BOTH, expand=True)
        self.scaffold_text = Text(scaffold_group, height=18, wrap="none")
        try:
            self.scaffold_text.configure(font=("Courier New", 10))  # monospace if available
        except Exception:
            pass
        self.scaffold_text.pack(fill=BOTH, expand=True, padx=6, pady=6)

    # -----------------------
    # Load combined files
    # -----------------------
    def refresh_pay_files(self):
        pay_dir = self.export_folders["pay"]
        files = []
        try:
            for name in os.listdir(pay_dir):
                if name.endswith(".Json") and os.path.isfile(os.path.join(pay_dir, name)):
                    files.append(name)
        except FileNotFoundError:
            pass

        files.sort()
        current = (self.selected_payfile_var.get() or "").strip()
        self.pay_file_menu["values"] = files

        if current in files:
            self.selected_payfile_var.set(current)
        elif files:
            self.selected_payfile_var.set(files[0])
        else:
            self.selected_payfile_var.set("")

        self.on_payfile_select()

    def on_payfile_select(self, event=None):
        self._clear_employees()
        self._clear_detail()

        label = (self.selected_payfile_var.get() or "").strip()
        if not label:
            return

        path = os.path.join(self.export_folders["pay"], label)
        if not os.path.isfile(path):
            return

        self.current_payfile_path = path
        self.current_period_label = os.path.splitext(os.path.basename(path))[0]

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
        self.employees_index.clear()
        self.employee_keys_sorted.clear()

        dists = combined.get("distributions", [])
        for item in dists:
            if "error" in item:
                continue
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue

            meta = content.get("meta", {})
            date = safe_str(meta.get("date"))
            shift = safe_str(meta.get("shift"))

            if not date or not shift:
                fname = item.get("filename", "")
                parsed_date, parsed_shift = _parse_date_shift_from_filename(fname)
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

                self.employees_index[key]["shifts"].append({
                    "date": date, "shift": shift,
                    "hours": hours, "cash": cash, "sur_paye": sur_paye,
                    "frais_admin": frais_admin,
                    "A": A_val, "B": emp.get("B", ""), "D": D_val, "E": emp.get("E", ""), "F": F_val
                })

                t = self.employees_index[key]["totals"]
                t["hours"] += hours
                t["cash"] += cash
                t["sur_paye"] += sur_paye
                t["frais_admin"] += frais_admin
                t["A_sum"] += A_val
                t["F_sum"] += F_val
                t["D_sum"] += D_val

        for key in self.employees_index:
            self.employees_index[key]["shifts"].sort(key=lambda s: (safe_str(s["date"]), safe_str(s["shift"])))

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
        declared_calc = amount_declared(t, info["role"])

        self.summary_text.delete("1.0", END)
        lines = [
            f"Employé: {info['name']}  (ID: {info['id'] or '—'}  |  Rôle: {info['role'] or '—'})",
            f"Période: {self.current_period_label or '—'}",
            f"Quarts: {len(info['shifts'])}",
            f"Totaux → Heures: {fmt_num(t['hours'], hours=True)} | Cash: {fmt_num(t['cash'])} | "
            f"Sur Paye: {fmt_num(t['sur_paye'])} | Frais Admin: {fmt_num(t['frais_admin'])} | "
            f"Déclaré: {fmt_num(declared_calc)}"
        ]
        self.summary_text.insert(END, "\n".join(lines))

        self.scaffold_text.delete("1.0", END)
        role_lower = (info["role"] or "").lower()
        header = "Date        / Hours    / Cash     / SurPaye  / FraisAdm  / Extras"
        self.scaffold_text.insert(END, header + "\n")
        self.scaffold_text.insert(END, "-" * len(header) + "\n")

        for s in info["shifts"]:
            date = safe_str(s["date"])
            hours = fmt_num(s["hours"], hours=True)
            cash = fmt_num(s["cash"])
            sp = fmt_num(s["sur_paye"])
            fa = fmt_num(s["frais_admin"])

            if "service" in role_lower:
                extras = _format_server_extras(s)
            elif "bussboy" in role_lower or "busboy" in role_lower:
                extras = _format_bussboy_extras(s)
            else:
                extras = _format_any_extras(s)

            line = f"{date:<12}/ {hours:<8}/ {cash:<8}/ {sp:<8}/ {fa:<9}/ {extras}"
            self.scaffold_text.insert(END, line + "\n")

    # -----------------------
    # Clearing helpers
    # -----------------------
    def _clear_employees(self):
        self.employee_list.delete(0, END)
        self.employees_index.clear()
        self.employee_keys_sorted.clear()

    def _clear_detail(self):
        self.summary_text.delete("1.0", END)
        self.scaffold_text.delete("1.0", END)

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
        m = re.search(r"(\d{4}-\d{2}-\d{2})_([A-Za-zÀ-ÖØ-öø-ÿ]+)", filename)
        if m:
            return m.group(1), m.group(2)
    except Exception:
        pass
    return "", ""

def safe_str(x):
    return "" if x is None else str(x)

def to_float(x):
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

def _format_server_extras(shift: dict) -> str:
    parts = []
    for label in ("A", "B", "E", "F"):
        v = shift.get(label, "")
        if isinstance(v, (int, float)):
            if v != 0:
                parts.append(f"{label}:{fmt_num(v)}")
        else:
            if str(v).strip() not in ("", "0"):
                parts.append(f"{label}:{v}")
    return " ".join(parts) if parts else "-"

def _format_bussboy_extras(shift: dict) -> str:
    v = shift.get("D", "")
    if isinstance(v, (int, float)):
        return f"D:{fmt_num(v)}" if v != 0 else "-"
    return f"D:{v}" if str(v).strip() not in ("", "0") else "-"

def _format_any_extras(shift: dict) -> str:
    parts = []
    for label in ("A", "B", "D", "E", "F"):
        v = shift.get(label, "")
        if isinstance(v, (int, float)):
            if v != 0:
                parts.append(f"{label}:{fmt_num(v)}")
        else:
            if str(v).strip() not in ("", "0"):
                parts.append(f"{label}:{v}")
    return " ".join(parts) if parts else "-"
