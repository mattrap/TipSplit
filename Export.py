from datetime import datetime
from PayPeriods import get_selected_period
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from tkinter import messagebox
import os
import json
import subprocess
import traceback
import sys
import platform

# -------------------- Utility --------------------
def get_unique_filename(base_path):
    if not os.path.exists(base_path):
        return base_path
    base, ext = os.path.splitext(base_path)
    i = 2
    while True:
        new_path = f"{base} - ({i}){ext}"
        if not os.path.exists(new_path):
            return new_path
        i += 1

# helper
def open_file_cross_platform(path):
    system = platform.system().lower()
    try:
        if system == "windows":
            # best: os.startfile if available; fallback to 'start'
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except AttributeError:
                subprocess.Popen(["start", "", path], shell=True)
        elif system == "darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # linux / other unix
            subprocess.Popen(["xdg-open", path])
    except Exception:
        # swallow failures; user can open manually
        pass


def parse_float_safe(value):
    try:
        return float(str(value).strip().replace(",", "."))
    except:
        return 0.0

# -------------------- PDF Helper Draw Methods (Distribution page) --------------------
def draw_input_section(c, y, fields):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Valeurs entrées:")
    y -= 20
    c.setFont("Helvetica", 10)
    for label in ["Ventes Nettes", "Dépot Net", "Frais Admin", "Cash"]:
        raw = str(fields.get(label, ""))
        c.drawString(50, y, f"{label:<15}: {raw} $")
        y -= 18
    return y - 10

def draw_table_header(c, y):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "#")
    c.drawString(90, y, "Nom")
    c.drawString(250, y, "Heures")
    c.drawString(320, y, "Cash")
    c.drawString(400, y, "Sur Paye")
    c.drawString(490, y, "Frais Admin")
    y -= 15
    c.line(50, y, 550, y)
    return y - 10

def draw_table_body(c, y, entries, height):
    c.setFont("Helvetica", 10)
    total_hours = total_cash = total_sur = total_admin = 0.0
    for entry in entries:
        employee_id = entry["employee_id"]
        name = entry["name"]
        hours = entry["hours"]
        cash = entry["cash"]
        sur_paye = entry["sur_paye"]
        frais_admin = entry["frais_admin"]

        if y < 100:
            c.showPage()
            y = height - inch

        if isinstance(name, str) and name.startswith("---"):
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, name)
            c.setFont("Helvetica", 10)
        else:
            c.drawString(50, y, str(employee_id))
            c.drawString(90, y, name)
            c.drawRightString(290, y, f"{float(hours):.2f}")
            c.drawRightString(370, y, f"{float(cash):.2f} $")
            c.drawRightString(460, y, f"{float(sur_paye):.2f} $")
            c.drawRightString(550, y, f"{float(frais_admin):.2f} $")

            total_hours += float(hours)
            total_cash += float(cash)
            total_sur += float(sur_paye)
            total_admin += float(frais_admin)
        y -= 16
    return y, total_hours, total_cash, total_sur, total_admin

def draw_totals(c, y, totals):
    total_hours, total_cash, total_sur, total_admin = totals
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "TOTAL")
    c.drawRightString(290, y, f"{total_hours:.2f}")
    c.drawRightString(370, y, f"{total_cash:.2f} $")
    c.drawRightString(460, y, f"{total_sur:.2f} $")
    c.drawRightString(550, y, f"{total_admin:.2f} $")
    return y - 30

def draw_distribution_panels(c, y, tab):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Résumé des valeures de distribution:")
    y -= 20

    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "SERVICE")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, tab.service_sur_paye_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.service_admin_fees_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.service_cash_label.cget("text"))
    y -= 25

    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "BUSSBOYS")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, tab.bussboy_percentage_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.bussboy_amount_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.bussboy_sur_paye_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.bussboy_cash_label.cget("text"))
    y -= 25

    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "DÉPOT")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, tab.service_owes_admin_label.cget("text"))
    return y

# -------------------- NEW: Declaration PDF helpers (Page 2) --------------------
def draw_declaration_input_section(c, y, decl_fields, ventes_declarees):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Paramètres de déclaration:")
    y -= 20

    c.setFont("Helvetica", 10)
    for label in ["Ventes Totales", "Clients", "Arrondi comptant", "Tips due"]:
        raw = str(decl_fields.get(label, ""))
        c.drawString(50, y, f"{label:<18}: {raw}")
        y -= 18

    c.drawString(50, y, f"Ventes déclarées: {ventes_declarees:.2f}")
    return y - 20

def draw_declaration_header(c, y):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50,  y, "#")
    c.drawString(90,  y, "Nom")
    c.drawString(250, y, "Heures")
    c.drawString(320, y, "A")
    c.drawString(360, y, "B")
    c.drawString(400, y, "D")
    c.drawString(440, y, "E")
    c.drawString(480, y, "F")
    y -= 15
    c.line(50, y, 550, y)
    return y - 10

def draw_declaration_body(c, y, entries_decl, height):
    c.setFont("Helvetica", 10)
    for entry in entries_decl:
        name = entry["name"]

        if y < 100:
            c.showPage()
            y = height - inch

        if isinstance(name, str) and name.startswith("---"):
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, name)
            c.setFont("Helvetica", 10)
        else:
            c.drawString(50, y, str(entry["employee_id"]))
            c.drawString(90, y, name)
            c.drawRightString(290, y, f"{float(entry['hours']):.2f}")

            def fmt(v):
                return "" if v in ("", None, "") else f"{float(v):.2f}"

            c.drawRightString(350, y, fmt(entry.get("A")))
            c.drawRightString(390, y, fmt(entry.get("B")))
            c.drawRightString(430, y, fmt(entry.get("D")))
            c.drawRightString(470, y, fmt(entry.get("E")))
            c.drawRightString(510, y, fmt(entry.get("F")))
        y -= 16
    return y

# -------------------- Export Functions --------------------
def pdf_export(date, shift, pay_period, fields, entries_dist, entries_decl, distribution_tab, decl_fields_raw):
    period_folder = f"{pay_period[0].replace('/', '-')}_au_{pay_period[1].replace('/', '-')}"
    pdf_dir = os.path.join("exports", "pdf", period_folder)
    os.makedirs(pdf_dir, exist_ok=True)

    base_pdf_path = os.path.join(pdf_dir, f"{date}-{shift}_distribution.pdf")
    final_pdf_path = get_unique_filename(base_pdf_path)

    c = canvas.Canvas(final_pdf_path, pagesize=letter)
    width, height = letter

    # -------------- PAGE 1: Distribution --------------
    y = height - inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Résumé de la distribution — {date} — {shift}")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Période de paye: {pay_period[0]} au {pay_period[1]}")
    y -= 30

    y = draw_input_section(c, y, fields)
    y = draw_table_header(c, y)
    y, *totals = draw_table_body(c, y, entries_dist, height)
    y = draw_totals(c, y, totals)
    draw_distribution_panels(c, y, distribution_tab)

    # -------------- PAGE 2: Declaration --------------
    c.showPage()
    y = height - inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Déclaration — {date} — {shift}")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Période de paye: {pay_period[0]} au {pay_period[1]}")
    y -= 30

    decl_vals = distribution_tab.declaration_net_values()
    ventes_declarees = decl_vals.get("ventes_declarees", 0.0)

    y = draw_declaration_input_section(c, y, decl_fields_raw, ventes_declarees)
    y = draw_declaration_header(c, y)
    y = draw_declaration_body(c, y, entries_decl, height)

    c.save()
    return final_pdf_path

def json_export(date, shift, pay_period, fields_sanitized, decl_fields_raw, entries_dist, entries_decl):
    period_folder = f"{pay_period[0].replace('/', '-')}_au_{pay_period[1].replace('/', '-')}"
    json_dir = os.path.join("exports", "json", period_folder)
    os.makedirs(json_dir, exist_ok=True)

    base_json_path = os.path.join(json_dir, f"{date}-{shift}_distribution.json")
    final_json_path = get_unique_filename(base_json_path)

    # map distribution rows by (employee_id, name)
    dist_map = {}
    for e in entries_dist:
        key = (e["employee_id"], e["name"])
        dist_map[key] = {
            "hours": e["hours"],
            "cash": e["cash"],
            "sur_paye": e["sur_paye"],
            "frais_admin": e["frais_admin"],
            "section": e.get("section", "")
        }

    merged_employees = []
    for e in entries_decl:
        if isinstance(e["name"], str) and e["name"].startswith("---"):
            continue  # skip section headers in JSON

        key = (e["employee_id"], e["name"])
        base = dist_map.get(key, {})
        section = base.get("section", "")

        emp = {
            "employee_id": e["employee_id"],
            "name": e["name"],
            "section": section,
            "hours": base.get("hours", 0.0),
            "cash": base.get("cash", 0.0),
            "sur_paye": base.get("sur_paye", 0.0),
            "frais_admin": base.get("frais_admin", 0.0),
        }

        # Service: include A, B, E, F. Bussboy: include D only.
        def _num_or_zero(val):
            return 0.0 if val in ("", None) else float(val)

        if section == "Service":
            emp["A"] = _num_or_zero(e.get("A"))
            emp["B"] = _num_or_zero(e.get("B"))
            emp["E"] = _num_or_zero(e.get("E"))
            emp["F"] = _num_or_zero(e.get("F"))
        elif section == "Bussboy":
            emp["D"] = _num_or_zero(e.get("D"))
        # else: unknown section -> no extra declaration fields

        merged_employees.append(emp)

    decl_vals_out = {
        "Ventes Totales": str(decl_fields_raw.get("Ventes Totales", "")),
        "Clients": str(decl_fields_raw.get("Clients", "")),
        "Arrondi comptant": str(decl_fields_raw.get("Arrondi comptant", "")),
        "Tips due": str(decl_fields_raw.get("Tips due", "")),
    }

    data = {
        "date": date,
        "shift": shift,
        "pay_period": {"start": pay_period[0], "end": pay_period[1]},
        "inputs": fields_sanitized,          # distribution inputs
        "declaration_inputs": decl_vals_out, # raw declaration inputs
        "employees": merged_employees
    }

    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return final_json_path

# -------------------- Main Trigger --------------------
def export_distribution_from_tab(distribution_tab):
    date = distribution_tab.selected_date_str
    shift = distribution_tab.shift_var.get().upper()

    if not date or not shift:
        messagebox.showerror("Erreur", "Assurez-vous de sélectionner une date et un shift.")
        return

    try:
        distribution_tab.root.update_idletasks()

        # Inputs (distribution)
        raw_inputs = {label: entry.get() for label, entry in distribution_tab.fields.items()}
        sanitized_inputs = {label: parse_float_safe(value) for label, value in raw_inputs.items()}

        # Declaration inputs (raw text)
        raw_decl_inputs = {label: entry.get() for label, entry in distribution_tab.declaration_fields.items()}

        # Collect both Distribution rows and Declaration rows from the same tree
        entries_dist = []
        entries_decl = []
        current_section = None

        for item in distribution_tab.tree.get_children():
            values = distribution_tab.tree.item(item)["values"]
            if not values:
                continue

            name = values[1]
            if isinstance(name, str) and name.startswith("---"):
                current_section = "Service" if "Service" in name else ("Bussboy" if "Bussboy" in name else None)
                # Keep a section header row for the Declaration page
                entries_decl.append({
                    "section": current_section or "",
                    "employee_id": "",
                    "name": name,
                    "hours": "",
                    "A": "", "B": "", "D": "", "E": "", "F": ""
                })
                continue

            try:
                emp_id = int(values[0])
            except Exception:
                continue

            # Distribution row
            try:
                entries_dist.append({
                    "employee_id": emp_id,
                    "name": values[1],
                    "hours": parse_float_safe(values[3]),
                    "cash": parse_float_safe(values[4]),
                    "sur_paye": parse_float_safe(values[5]),
                    "frais_admin": parse_float_safe(values[6]),
                    "section": current_section or ""
                })
            except (ValueError, IndexError):
                continue

            # Declaration row
            def _get(v, idx):
                try:
                    val = v[idx]
                    return "" if (val in ("", None, "")) else parse_float_safe(val)
                except Exception:
                    return ""

            entries_decl.append({
                "section": current_section or "",
                "employee_id": emp_id,
                "name": values[1],
                "hours": parse_float_safe(values[3]),
                "A": _get(values, 7),
                "B": _get(values, 8),
                "D": _get(values, 9),
                "E": _get(values, 10),
                "F": _get(values, 11),
            })

        # Pay period
        selected_dt = datetime.strptime(date, "%d-%m-%Y")
        _, pay_period_data = get_selected_period(selected_dt)
        start_str, end_str = pay_period_data["range"].split(" - ")
        pay_period = (start_str, end_str)

        # Exports
        pdf_path = pdf_export(date, shift, pay_period, raw_inputs, entries_dist, entries_decl,
                              distribution_tab, raw_decl_inputs)
        json_path = json_export(date, shift, pay_period, sanitized_inputs, raw_decl_inputs,
                                entries_dist, entries_decl)

        messagebox.showinfo("Exporté", f"PDF généré avec succès:\n{os.path.basename(pdf_path)}")
        open_file_cross_platform(pdf_path)

    except Exception as e:
        traceback_str = traceback.format_exc()
        messagebox.showerror("Erreur", f"Échec de l'exportation:\n{traceback_str}")
        print("❌ Export failed with exception:")
        print(traceback_str)

'''
All PDFs are saved under:
exports/pdf/{pay_period_folder}/{filename}.pdf

All JSONs are saved under:
exports/json/{pay_period_folder}/{filename}.json
'''
