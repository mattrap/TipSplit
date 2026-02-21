from datetime import datetime
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from tkinter import messagebox
import os
import subprocess
import traceback
import sys
import platform
from typing import Dict, List
from AppConfig import get_pdf_dir
import time
from db.distributions_repo import create_distribution

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

def _ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def _fallback_pdf_root() -> str:
    """Safe fallback if user skipped choosing a folder."""
    return os.path.expanduser("~/TipSplitExports")

def _pdf_root() -> str:
    """User-chosen PDF export root, or a safe fallback."""
    return get_pdf_dir() or _fallback_pdf_root()

def _safe_slug(value: str) -> str:
    return (value or "").replace("/", "-").replace(":", "-")

def _period_folder_from_info(period_info: dict) -> str:
    if not period_info:
        return "periode_inconnue"
    slug = period_info.get("folder_slug")
    if slug:
        return _safe_slug(slug)
    display_id = period_info.get("display_id") or "periode"
    start_iso = period_info.get("start_date_iso") or period_info.get("start_label") or ""
    end_iso = period_info.get("end_date_iso") or period_info.get("end_label") or ""
    parts = [_safe_slug(display_id)]
    if start_iso:
        parts.append(_safe_slug(start_iso))
    if end_iso:
        parts.append(_safe_slug(end_iso))
    return "_".join(parts)

def _period_folder_from_label(period_label: str) -> str:
    """
    Accepts strings like:
      '2025-06-08 au 2025-06-21'   or   '2025-06-08 - 2025-06-21'
    Falls back safely if format differs.
    """
    label = (period_label or "").strip()
    if " au " in label:
        a, b = label.split(" au ", 1)
    elif " - " in label:
        a, b = label.split(" - ", 1)
    else:
        # unknown format: just sanitize the label
        return label.replace("/", "-").replace(":", "-")
    a = a.strip().replace("/", "-")
    b = b.strip().replace("/", "-")
    return f"{a}_au_{b}"

def _pdf_period_dir(category: str, period_info: dict) -> str:
    """
    category: 'daily' -> Résumé de shift
              'pay'   -> Paye
    """
    root = _pdf_root()
    period_folder = _period_folder_from_info(period_info)
    if category == "daily":
        target = os.path.join(root, "Résumé de shift", period_folder)
    else:
        target = os.path.join(root, "Paye", period_folder)
    _ensure_dir(target)
    return target


def _period_label_dates(period_info: dict) -> tuple[str, str]:
    info = period_info or {}
    start = info.get("start_label") or info.get("start_date_iso") or ""
    end = info.get("end_label") or info.get("end_date_iso") or ""
    return start, end

def _period_metadata(period_info: dict) -> dict:
    info = period_info or {}
    return {
        "id": info.get("id"),
        "display_id": info.get("display_id"),
        "start_date": info.get("start_date_iso") or info.get("start_label"),
        "end_date": info.get("end_date_iso") or info.get("end_label"),
        "pay_date": info.get("pay_date_local"),
        "status": info.get("status"),
    }

# -------------- Logging helpers --------------

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

    # ---- Depot panels first ----
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "DÉPOT")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, tab.service_owes_admin_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.service_owes_cuisine_label.cget("text"))
    y -= 25

    # ---- Bussboys next ----
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

    # ---- Service (cuisine) last ----
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "SERVICE")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, tab.service_sur_paye_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.service_admin_fees_label.cget("text"))
    y -= 15
    c.drawString(70, y, tab.service_cash_label.cget("text"))
    return y

# -------------------- NEW: Declaration PDF helpers (Page 2) --------------------
def draw_declaration_input_section(c, y, decl_fields, ventes_declarees):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Paramètres de déclaration:")
    y -= 20

    c.setFont("Helvetica", 10)
    for label in ["Ventes Totales", "Clients", "Tips due", "Ventes Nourriture"]:
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

# -------------------- Export Functions (Distribution+Declaration) --------------------
def _format_recorded_date(created_at: str) -> str:
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d")
    except Exception:
        created_at = str(created_at)
        return created_at.split("T", 1)[0] if "T" in created_at else created_at


def pdf_export(date, shift, period_info, fields, entries_dist, entries_decl, distribution_tab, decl_fields_raw, dist_ref, recorded_at):
    """
    Create a 2-page PDF:
      - Page 1: Distribution
      - Page 2: Declaration
    The distribution reference and recorded date are printed under the pay-period line on both pages.
    PDF is saved under: {PDF_ROOT}/Résumé de shift/{period}/...
    """
    pdf_dir = _pdf_period_dir("daily", period_info)
    base_pdf_path = os.path.join(pdf_dir, f"{date}-{shift}_distribution.pdf")
    final_pdf_path = get_unique_filename(base_pdf_path)

    c = canvas.Canvas(final_pdf_path, pagesize=letter)
    width, height = letter

    # -------------- PAGE 1: Distribution --------------
    y = height - inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Résumé de la distribution — {date} — {shift}")
    y -= 20
    start_label, end_label = _period_label_dates(period_info)
    c.setFont("Helvetica", 11)
    if start_label and end_label:
        c.drawString(50, y, f"Période de paye: {start_label} au {end_label}")
    else:
        c.drawString(50, y, "Période de paye: (inconnue)")
    y -= 18
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, f"Référence distribution: {dist_ref}")
    y -= 14
    recorded_label = _format_recorded_date(recorded_at)
    c.drawString(50, y, f"Date d'enregistrement: {recorded_label or '—'}")
    y -= 16

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
    if start_label and end_label:
        c.drawString(50, y, f"Période de paye: {start_label} au {end_label}")
    else:
        c.drawString(50, y, "Période de paye: (inconnue)")
    y -= 18
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, f"Référence distribution: {dist_ref}")
    y -= 14
    c.drawString(50, y, f"Date d'enregistrement: {recorded_label or '—'}")
    y -= 16

    decl_vals = distribution_tab.declaration_net_values()
    ventes_declarees = decl_vals.get("ventes_declarees", 0.0)

    y = draw_declaration_input_section(c, y, decl_fields_raw, ventes_declarees)
    y = draw_declaration_header(c, y)
    y = draw_declaration_body(c, y, entries_decl, height)

    c.save()
    return final_pdf_path

def db_export(date, shift, period_info, fields_sanitized, decl_fields_raw, entries_dist, entries_decl, created_by: str = ""):
    """
    Persist the distribution & declaration into SQLite.
    Returns (dist_id, dist_ref, created_at).
    """
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
            continue  # skip section headers

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

        def _num_or_zero(val):
            return 0.0 if val in ("", None) else float(val)

        if section == "Service":
            emp["A"] = _num_or_zero(e.get("A"))
            emp["B"] = _num_or_zero(e.get("B"))
            emp["E"] = _num_or_zero(e.get("E"))
            emp["F"] = _num_or_zero(e.get("F"))
        elif section == "Bussboy":
            emp["D"] = _num_or_zero(e.get("D"))

        merged_employees.append(emp)

    decl_vals_out = {
        "Ventes Totales": decl_fields_raw.get("Ventes Totales", ""),
        "Clients": decl_fields_raw.get("Clients", ""),
        "Tips due": decl_fields_raw.get("Tips due", ""),
        "Ventes Nourriture": decl_fields_raw.get("Ventes Nourriture", ""),
    }

    result = create_distribution(
        pay_period_id=period_info.get("id"),
        date_local=date,
        shift=shift,
        inputs=fields_sanitized,
        declaration_inputs=decl_vals_out,
        employees=merged_employees,
        created_by=created_by or "",
    )
    return result["id"], result["dist_ref"], result.get("created_at", "")

# ===================================================================== #
#                     Employee Résumé + Booklet                         #
# ===================================================================== #

def _fmt_num(x, hours: bool = False) -> str:
    try:
        val = float(x)
        if hours:
            return f"{val:.4f}".rstrip("0").rstrip(".") if abs(val) < 10 else f"{val:.2f}"
        return f"{val:.2f}"
    except Exception:
        return str(x)

def _amount_declared_and_label(totals: dict, role: str):
    """
    Returns (declared_value, declared_source_label)
    - Service: max( F_sum, 8% of A_sum ) with label 'F' or '8% de A'
    - Bussboy: D_sum with label 'D'
    """
    role_lower = (role or "").lower()
    if "service" in role_lower:
        a_sum = float(totals.get("A_sum", 0.0))
        f_sum = float(totals.get("F_sum", 0.0))
        a_floor = 0.08 * a_sum
        if f_sum >= a_floor:
            return f_sum, "F"
        else:
            return a_floor, "8% des ventes"
    if "bussboy" in role_lower or "busboy" in role_lower:
        d_sum = float(totals.get("D_sum", 0.0))
        return d_sum, "D"
    # Fallback
    return 0.0, "—"

def _safe_text(x) -> str:
    return "" if x is None else str(x)

def _safe_key(info: dict) -> str:
    """Filename-safe employee key: prefer ID, else name."""
    base = _safe_text(info.get("id") or info.get("name") or "employee")
    for ch in ["/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        base = base.replace(ch, "_")
    return base.strip() or "employee"

def _col_centers(left: int, widths: List[int]) -> List[float]:
    """Return x-centers for each column given left start and widths."""
    centers = []
    x = left
    for w in widths:
        centers.append(x + w / 2.0)
        x += w
    return centers

def _draw_employee_pdf(out_path: str, period_label: str, info: dict):
    """
    Render one employee PDF with TWO sections on the SAME PAGE:
      1) DÉTAILLÉ: Cash / Sur paye / Frais admin détaillé par quart + Total (all columns centered)
      2) DÉCLARATION: A/B/E/F (Service) or D (Bussboy) détaillé par quart + Total + 'Déclaré selon ...' (centered)
    'info' must match PayTab.employees_index[...] = {id,name,role,shifts[],totals{}}
    Each shift item should include 'display_name' (filename without extension),
    and numeric fields hours, cash, sur_paye, frais_admin, plus A/B/E/F or D.
    """
    page_w, page_h = map(int, letter)
    margin = 50
    left = margin
    right = page_w - margin
    y = page_h - margin

    # Spacing constants
    h1_gap = 24
    sub_gap = 30
    sec_title_gap = 22
    line_h = 18
    hdr_gap = 18
    row_gap = 18
    rule_gap = 12
    bottom_margin = 80

    def new_canvas(path):
        c = canvas.Canvas(path, pagesize=letter)
        c.setLineWidth(1)
        return c

    def draw_header(cnv):
        nonlocal y
        cnv.setFont("Helvetica-Bold", 14)
        cnv.drawString(left, y, f"{_safe_text(info.get('name'))} — ID: {_safe_text(info.get('id') or '—')}")
        y -= h1_gap
        cnv.setFont("Helvetica", 11)
        cnv.drawString(left, y, f"Période: {period_label}   |   Rôle: {_safe_text(info.get('role') or '—')}")
        y -= sub_gap

    def paginate_if_needed(cnv):
        nonlocal y
        if y < bottom_margin:
            cnv.showPage()
            y = page_h - margin
            cnv.setLineWidth(1)
            draw_header(cnv)

    def draw_rule(cnv):
        nonlocal y
        cnv.line(left, int(y), right, int(y))
        y -= rule_gap

    c = new_canvas(out_path)
    draw_header(c)

    # =========================
    # Section 1: DÉTAILLÉ (centered columns)
    # =========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "DÉTAILLÉ:")
    y -= sec_title_gap

    # columns: Date, Cash, Sur paye, Frais admin, Total quart
    c.setFont("Helvetica-Bold", 10)
    col_w_det = [150, 80, 90, 90, 90]
    headers_det = ["Date (quart)", "Cash", "Sur paye", "Frais admin", "Total quart"]
    centers_det = _col_centers(left, col_w_det)

    # Header row (centered)
    for cx, h in zip(centers_det, headers_det):
        c.drawCentredString(int(cx), int(y), h)
    y -= hdr_gap
    draw_rule(c)
    c.setFont("Helvetica", 10)

    # Rows
    total_cash = 0.0
    total_sur = 0.0
    total_admin = 0.0

    for s in info.get("shifts", []):
        paginate_if_needed(c)
        shift_total = float(s.get("cash") or 0.0) + float(s.get("sur_paye") or 0.0) + float(s.get("frais_admin") or 0.0)
        vals = [
            _safe_text(s.get("display_name") or s.get("date") or ""),
            _fmt_num(s.get("cash") or 0.0),
            _fmt_num(s.get("sur_paye") or 0.0),
            _fmt_num(s.get("frais_admin") or 0.0),
            _fmt_num(shift_total),
        ]
        for cx, v in zip(centers_det, vals):
            c.drawCentredString(int(cx), int(y), v)
        y -= row_gap

        total_cash += float(s.get("cash") or 0.0)
        total_sur += float(s.get("sur_paye") or 0.0)
        total_admin += float(s.get("frais_admin") or 0.0)

    # Totals line for DÉTAILLÉ (centered in numeric columns)
    y -= 2
    draw_rule(c)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Total:")
    # Put totals under their columns
    c.drawCentredString(int(centers_det[1]), int(y), _fmt_num(total_cash))
    c.drawCentredString(int(centers_det[2]), int(y), _fmt_num(total_sur))
    c.drawCentredString(int(centers_det[3]), int(y), _fmt_num(total_admin))
    grand_total = total_cash + total_sur + total_admin
    c.drawCentredString(int(centers_det[4]), int(y), _fmt_num(grand_total))
    y -= sub_gap

    paginate_if_needed(c)

    # =========================
    # Section 2: DÉCLARATION (centered columns)
    # =========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "DÉCLARATION:")
    y -= sec_title_gap

    role_lower = (_safe_text(info.get("role"))).lower()
    is_service = "service" in role_lower
    is_bus = ("bussboy" in role_lower) or ("busboy" in role_lower)

    # Columns
    if is_service:
        headers_dec = ["Date (quart)", "A", "B", "E", "F"]
        col_w_dec = [150, 90, 90, 90, 90]
    elif is_bus:
        headers_dec = ["Date (quart)", "D"]
        col_w_dec = [300, 110]
    else:
        headers_dec = ["Date (quart)", "A", "B", "D", "E", "F"]
        col_w_dec = [150, 70, 70, 70, 70, 70]

    centers_dec = _col_centers(left, col_w_dec)

    # Header row (centered)
    c.setFont("Helvetica-Bold", 10)
    for cx, h in zip(centers_dec, headers_dec):
        c.drawCentredString(int(cx), int(y), h)
    y -= hdr_gap
    draw_rule(c)
    c.setFont("Helvetica", 10)

    # Totals accumulators
    A_sum = B_sum = D_sum = E_sum = F_sum = 0.0

    # Rows
    for s in info.get("shifts", []):
        paginate_if_needed(c)
        date_label = _safe_text(s.get("display_name") or s.get("date") or "")
        A = float(s.get("A") or 0.0)
        B = _safe_text(s.get("B") if s.get("B") not in (None, "") else "")
        D = float(s.get("D") or 0.0)
        E = _safe_text(s.get("E") if s.get("E") not in (None, "") else "")
        F = float(s.get("F") or 0.0)

        if is_service:
            row_vals = [date_label, _fmt_num(A), B, E, _fmt_num(F)]
        elif is_bus:
            row_vals = [date_label, _fmt_num(D)]
        else:
            row_vals = [date_label, _fmt_num(A), B, _fmt_num(D), E, _fmt_num(F)]

        for cx, v in zip(centers_dec, row_vals):
            c.drawCentredString(int(cx), int(y), v)
        y -= row_gap

        A_sum += A
        D_sum += D
        F_sum += F

    # Totals line for DÉCLARATION (centered)
    y -= 2
    draw_rule(c)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Total:")

    if is_service:
        # centers_dec indices: 0=date, 1=A, 2=B, 3=E, 4=F
        c.drawCentredString(int(centers_dec[1]), int(y), _fmt_num(A_sum))
        # B/E totals intentionally blank
        c.drawCentredString(int(centers_dec[4]), int(y), _fmt_num(F_sum))
        totals_for_decl = {"A_sum": A_sum, "F_sum": F_sum}
    elif is_bus:
        c.drawCentredString(int(centers_dec[1]), int(y), _fmt_num(D_sum))
        totals_for_decl = {"D_sum": D_sum}
    else:
        # 0=date, 1=A, 2=B, 3=D, 4=E, 5=F
        c.drawCentredString(int(centers_dec[1]), int(y), _fmt_num(A_sum))
        c.drawCentredString(int(centers_dec[3]), int(y), _fmt_num(D_sum))
        c.drawCentredString(int(centers_dec[5]), int(y), _fmt_num(F_sum))
        totals_for_decl = {"A_sum": A_sum, "D_sum": D_sum, "F_sum": F_sum}

    y -= 12  # line_h

    # Declared line with source label
    declared_val, declared_src = _amount_declared_and_label(totals_for_decl, info.get("role"))
    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Déclaré selon {declared_src}: {_fmt_num(declared_val)}")
    y -= sub_gap

    c.save()

def export_all_employee_pdfs(period_label: str, employees_index: Dict[str, dict], out_dir: str) -> List[str]:
    """
    Create one PDF per employee.
    Per your rule, PDFs are written under:
        {PDF_ROOT}/Paye/{period}/
    'out_dir' is ignored for placement to avoid accidental misroutes; we still keep it in signature
    for backward-compat with existing callers.
    Returns sorted list of created file paths.
    """
    period_folder = _period_folder_from_label(period_label)
    target_dir = os.path.join(_pdf_root(), "Paye", period_folder)
    _ensure_dir(target_dir)

    paths: List[str] = []
    for _, info in employees_index.items():
        safe_name = _safe_key(info) + ".pdf"
        out_path = os.path.join(target_dir, safe_name)
        _draw_employee_pdf(out_path, period_label, info)
        paths.append(out_path)
    return sorted(paths)

def make_booklet(period_label: str, pdf_paths: List[str], out_file: str) -> str:
    """
    Merge per-employee PDFs into a single booklet PDF.
    Requires PyPDF2.
    The booklet is saved under:
        {PDF_ROOT}/Paye/{period}/livret_...pdf
    """
    try:
        from PyPDF2 import PdfMerger
    except Exception as e:
        raise RuntimeError("PyPDF2 is required to build the booklet") from e

    period_folder = _period_folder_from_label(period_label)
    target_dir = os.path.join(_pdf_root(), "Paye", period_folder)
    _ensure_dir(target_dir)

    booklet_name = os.path.basename(out_file) if out_file else f"livret_{period_folder}.pdf"
    target_path = os.path.join(target_dir, booklet_name)

    merger = PdfMerger()
    for p in pdf_paths:
        if os.path.isfile(p):
            merger.append(p)
    merger.write(target_path)
    merger.close()
    return target_path

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
        period_info = None
        if hasattr(distribution_tab, "get_active_pay_period"):
            period_info = distribution_tab.get_active_pay_period()
        if not period_info:
            messagebox.showerror("Période introuvable", "Impossible de déterminer la période de paye pour cette date.")
            return

        dist_id, dist_ref, created_at = db_export(
            date, shift, period_info, sanitized_inputs, raw_decl_inputs, entries_dist, entries_decl,
            created_by=getattr(distribution_tab, "current_user", "")
        )

        # ---- Export PDF, including the distribution reference and recorded date on each page ----
        pdf_path = pdf_export(
            date, shift, period_info, raw_inputs, entries_dist, entries_decl,
            distribution_tab, raw_decl_inputs, dist_ref, created_at
        )

        # Mark export success for progress UI (menu bar)
        try:
            distribution_tab.shared_data["last_export_token"] = time.time()
            distribution_tab.shared_data["last_export_path"] = pdf_path
        except Exception:
            pass

        messagebox.showinfo(
            "Exporté",
            f"PDF généré avec succès:\n{os.path.basename(pdf_path)}"
        )
        open_file_cross_platform(pdf_path)

    except Exception as e:
        traceback_str = traceback.format_exc()
        messagebox.showerror("Erreur", f"Échec de l'exportation:\n{traceback_str}")
        print("❌ Export failed with exception:")
        print(traceback_str)

'''
PDF DESTINATIONS (user-visible):
- Daily distribution PDFs:
    {PDF_ROOT}/Résumé de shift/{pay_period}/{date}-{shift}_distribution.pdf

- Employee pay summaries (per-employee PDFs) via export_all_employee_pdfs():
    {PDF_ROOT}/Paye/{pay_period}/{employee}.pdf

- Booklet via make_booklet():
    {PDF_ROOT}/Paye/{pay_period}/{booklet_name}.pdf

DB DESTINATION (internal only):
- SQLite database (tipsplit.db) under the app data directory.
'''
