from datetime import datetime, timedelta
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import json
import subprocess


def get_pay_period(current_dt):
    known_start = datetime(2025, 6, 8, 6, 0)
    delta = current_dt - known_start
    total_seconds = delta.total_seconds()
    period_seconds = 14 * 24 * 3600  # 2 weeks
    period_index = int(total_seconds // period_seconds)
    period_start = known_start + timedelta(seconds=period_index * period_seconds)
    period_end = period_start + timedelta(days=13, hours=23, minutes=59)
    return period_start.strftime("%d/%m/%Y"), period_end.strftime("%d/%m/%Y")

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

        if name.startswith("---"):
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

def generate_pdf_summary(date, shift, pay_period, fields, entries, output_path, distribution_tab):
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    y = height - inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Résumé de la distribution — {date} — {shift}")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Période de paye: {pay_period[0]} au {pay_period[1]}")
    y -= 30

    y = draw_input_section(c, y, fields)
    y = draw_table_header(c, y)
    y, *totals = draw_table_body(c, y, entries, height)
    y = draw_totals(c, y, totals)
    draw_distribution_panels(c, y, distribution_tab)

    c.save()

def export_json_summary(date, shift, pay_period, fields_sanitized, entries):
    data = {
        "date": date,
        "shift": shift,
        "pay_period": {
            "start": pay_period[0],
            "end": pay_period[1]
        },
        "inputs": fields_sanitized,
        "employees": entries
    }
    json_dir = os.path.join("exports", "json")
    os.makedirs(json_dir, exist_ok=True)
    base_path = os.path.join(json_dir, f"{date}-{shift}_distribution.json")
    final_path = get_unique_filename(base_path)
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def export_distribution_from_tab(distribution_tab):
    from tkinter import messagebox

    date = distribution_tab.selected_date_str
    shift = distribution_tab.shift_var.get().upper()

    if not date or not shift:
        messagebox.showerror("Erreur", "Assurez-vous de sélectionner une date et un shift.")
        return

    try:
        distribution_tab.root.update_idletasks()

        raw_input_values = {label: entry.get() for label, entry in distribution_tab.fields.items()}

        def parse_float_safe(value):
            try:
                return float(value.strip().replace(",", "."))
            except:
                return 0.0

        sanitized_inputs = {
            label: parse_float_safe(value)
            for label, value in raw_input_values.items()
        }

        entries = []
        for item in distribution_tab.tree.get_children():
            values = distribution_tab.tree.item(item)["values"]
            name = values[1]
            if name.startswith("---"):
                continue
            try:
                employee_id = int(values[0])
                hours = parse_float_safe(values[3])
                cash = parse_float_safe(values[4])
                sur_paye = parse_float_safe(values[5])
                frais_admin = parse_float_safe(values[6])
                entries.append({
                    "employee_id": employee_id,
                    "name": name,
                    "hours": hours,
                    "cash": cash,
                    "sur_paye": sur_paye,
                    "frais_admin": frais_admin
                })
            except (ValueError, IndexError):
                continue

        now = datetime.now()
        pay_period = get_pay_period(now)

        pdf_dir = os.path.join("exports", "pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        base_pdf_path = os.path.join(pdf_dir, f"{date}-{shift}_distribution.pdf")
        final_pdf_path = get_unique_filename(base_pdf_path)

        generate_pdf_summary(
            date=date,
            shift=shift,
            pay_period=pay_period,
            fields=raw_input_values,
            entries=entries,
            output_path=final_pdf_path,
            distribution_tab=distribution_tab
        )

        export_json_summary(
            date=date,
            shift=shift,
            pay_period=pay_period,
            fields_sanitized=sanitized_inputs,
            entries=entries
        )

        messagebox.showinfo("Exporté", f"PDF généré avec succès:\n{os.path.basename(final_pdf_path)}")
        subprocess.Popen(["start", "", final_pdf_path], shell=True)
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec de l'exportation:\n{e}")
