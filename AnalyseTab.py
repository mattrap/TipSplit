import os
import json
import re
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import Listbox, END, BROWSE

from AppConfig import get_backend_dir
from ui_scale import scale

# Reuse helpers from Pay if available
try:
    from Pay import amount_declared, to_float, safe_str
except Exception:
    # Minimal fallbacks
    def amount_declared(totals: dict, role: str) -> float:
        role_lower = (role or "").lower()
        if "service" in role_lower:
            return max(0.08 * float(totals.get("A_sum", 0.0)), float(totals.get("F_sum", 0.0)))
        elif "bussboy" in role_lower or "busboy" in role_lower:
            return float(totals.get("D_sum", 0.0))
        return 0.0

    def to_float(x):
        try:
            if x is None:
                return 0.0
            if isinstance(x, (int, float)):
                return float(x)
            s = str(x).strip().replace(",", ".")
            s = re.sub(r"[^0-9\.\-]+", "", s)
            if s in ("", "-", ".", "-.", ".-"):
                return 0.0
            return float(s)
        except Exception:
            return 0.0

    def safe_str(x):
        return "" if x is None else str(x)


class AnalyseTab:
    def __init__(self, master):
        self.master = master
        self.frame = ttk.Frame(master)

        # Backend root and pay dir
        self.backend_root = get_backend_dir()
        self.pay_dir = os.path.join(self.backend_root, "pay")

        # Map: period_label -> combined.Json path (read-only)
        self._period_to_path = {}
        self.current_period_label = None
        self.current_combined = None

        self._build_ui()
        self.refresh_periods()
        self.frame.pack(fill=BOTH, expand=True)

    # ----------------------- UI -----------------------
    def _build_ui(self):
        # Header with refresh
        header = ttk.Frame(self.frame)
        header.pack(fill=X, padx=10, pady=(10, 6))

        left_box = ttk.Frame(header)
        left_box.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(left_box, text="Sélectionnez une période de paye").pack(side=LEFT)
        ttk.Button(left_box, text="Rafraîchir", command=self.refresh_periods).pack(side=LEFT, padx=6)

        # Main layout: left list, right content with two stacked chart areas
        paned = ttk.Panedwindow(self.frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        # Left list (single-select)
        left = ttk.Frame(paned, width=scale(260))
        left.pack_propagate(False)
        paned.add(left, weight=1)

        ttk.Label(left, text="Périodes disponibles").pack(anchor=W, padx=2, pady=(2, 4))
        self.period_list = Listbox(left, height=24, selectmode=BROWSE)
        self.period_list.pack(fill=BOTH, expand=True)
        self.period_list.bind("<<ListboxSelect>>", self.on_selection_change)

        # Right content -> single chart
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        chart_group = ttk.LabelFrame(right, text="Ventes Nettes — Par jour")
        chart_group.pack(fill=BOTH, expand=True)
        self.chart_canvas = tk.Canvas(chart_group, height=scale(420), background="#fafafa", highlightthickness=0)
        self.chart_canvas.pack(fill=BOTH, expand=True, padx=6, pady=6)

        # Initial placeholder
        self._draw_placeholder(self.chart_canvas, "Sélectionnez une période à analyser…")

    # ----------------------- Data discovery -----------------------
    def refresh_periods(self):
        self._period_to_path = {}
        try:
            if os.path.isdir(self.pay_dir):
                for period in os.listdir(self.pay_dir):
                    pdir = os.path.join(self.pay_dir, period)
                    if not os.path.isdir(pdir):
                        continue
                    preferred = os.path.join(pdir, "combined.Json")
                    if os.path.isfile(preferred):
                        self._period_to_path[period] = preferred
                    else:
                        candidates = [f for f in os.listdir(pdir) if f.endswith(".Json")]
                        if candidates:
                            self._period_to_path[period] = os.path.join(pdir, sorted(candidates)[0])
        except Exception:
            pass

        periods = sorted(self._period_to_path.keys())
        self.period_list.delete(0, END)
        for p in periods:
            self.period_list.insert(END, p)

        # Clear selection and canvas on refresh
        self.current_period_label = None
        self.current_combined = None
        self._draw_placeholder(self.chart_canvas, "Sélectionnez une période à analyser…")

    # ----------------------- Interaction -----------------------
    def on_selection_change(self, event=None):
        self.read_selected_pay_file()
        self.update_daily_chart()

    # ----------------------- Core functions -----------------------
    def read_selected_pay_file(self):
        """Read the selected pay period's combined.Json into memory."""
        sel = self.period_list.curselection()
        if not sel:
            self.current_period_label = None
            self.current_combined = None
            return None
        label = self.period_list.get(sel[0])
        path = self._period_to_path.get(label)
        if not path or not os.path.isfile(path):
            self.current_period_label = None
            self.current_combined = None
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                combined = json.load(f)
        except Exception:
            self.current_period_label = None
            self.current_combined = None
            return None
        self.current_period_label = label
        self.current_combined = combined
        return combined

    def _collect_daily_ventes_nettes(self, combined: dict) -> dict:
        """Return dict date_str -> ventes_nettes (float) using filename as date source."""
        per_day = {}
        if not isinstance(combined, dict):
            return per_day
        dists = combined.get("distributions", [])
        for item in dists:
            if not isinstance(item, dict) or "error" in item:
                continue
            filename = safe_str(item.get("filename", ""))
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue
            # Date from filename
            date, _shift = self._parse_date_shift_from_filename(os.path.splitext(filename)[0])
            if not date:
                continue
            # Ventes Nettes from inputs
            inputs = content.get("inputs", {}) if isinstance(content.get("inputs", {}), dict) else {}
            ventes_nettes = to_float(inputs.get("Ventes Nettes", 0.0))
            per_day[date] = per_day.get(date, 0.0) + ventes_nettes
        return per_day

    def update_daily_chart(self):
        """Compute daily Ventes Nettes for the selected period and draw bars for each day in the period."""
        c = self.chart_canvas
        c.delete("all")
        if not self.current_combined or not self.current_period_label:
            self._draw_placeholder(c, "Sélectionnez une période à analyser…")
            return

        per_day = self._collect_daily_ventes_nettes(self.current_combined)
        start_dt, end_dt = self._parse_period_bounds(self.current_period_label)
        if start_dt is None or end_dt is None:
            # Fallback: draw only available dates
            self._draw_daily_bars(per_day, None, None)
        else:
            self._draw_daily_bars(per_day, start_dt, end_dt)

    # ----------------------- Analysis -----------------------
    # ----------------------- Drawing helpers -----------------------
    def _draw_placeholder(self, canvas: tk.Canvas, text: str):
        canvas.delete("all")
        w = canvas.winfo_width() or 600
        h = canvas.winfo_height() or 260
        x = w // 2
        y = h // 2
        canvas.create_text(x, y, text=text, fill="#666666", font=("Helvetica", 12))

    def _draw_daily_bars(self, per_day_map: dict, start_dt, end_dt):
        c = self.chart_canvas
        w = c.winfo_width() or 900
        h = c.winfo_height() or 420

        # Build ordered list of days
        days = []
        if start_dt and end_dt:
            from datetime import timedelta
            cur = start_dt
            while cur <= end_dt:
                days.append(cur)
                cur += timedelta(days=1)
        else:
            # Fallback: infer from keys present
            keys = sorted(per_day_map.keys())
            from datetime import datetime
            for k in keys:
                try:
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", k):
                        days.append(datetime.strptime(k, "%Y-%m-%d"))
                    elif re.match(r"^\d{2}-\d{2}-\d{4}$", k):
                        days.append(datetime.strptime(k, "%d-%m-%Y"))
                except Exception:
                    continue

        if not days:
            self._draw_placeholder(c, "Aucune donnée quotidienne trouvée")
            return

        # Values in order
        values = []
        for d in days:
            key = d.strftime("%Y-%m-%d")
            alt = d.strftime("%d-%m-%Y")
            val = per_day_map.get(key)
            if val is None:
                val = per_day_map.get(alt, 0.0)
            values.append(float(val or 0.0))

        vmax = max(values) if values else 1.0
        if vmax <= 0:
            vmax = 1.0

        # margins
        left, right, top, bottom = 50, 20, 20, 60
        plot_w = max(10, w - left - right)
        plot_h = max(10, h - top - bottom)

        # axes
        c.create_line(left, h - bottom, w - right, h - bottom, fill="#444")
        c.create_line(left, h - bottom, left, top, fill="#444")

        # Bar geometry
        n = len(values)
        gap = 6
        bar_w = max(8, int((plot_w - gap * (n + 1)) / max(1, n)))
        x = left + gap

        for i, val in enumerate(values):
            bh = int((val / vmax) * plot_h)
            x0 = x
            y0 = h - bottom - bh
            x1 = x + bar_w
            y1 = h - bottom
            c.create_rectangle(x0, y0, x1, y1, fill="#4e79a7", outline="")
            # value label
            c.create_text((x0 + x1)//2, y0 - 10, text=f"{val:.0f}", fill="#333", font=("Helvetica", 9))
            # x label — show MM-DD
            lab = days[i].strftime("%m-%d")
            c.create_text((x0 + x1)//2, y1 + 12, text=lab, angle=0, font=("Helvetica", 9))
            x += bar_w + gap

        # y scale labels (0 and max)
        c.create_text(left - 10, h - bottom, text="0", anchor=E, font=("Helvetica", 9))
        c.create_text(left - 10, top, text=f"{vmax:.0f}", anchor=E, font=("Helvetica", 9))

    # ----------------------- Date parsing helpers -----------------------
    def _parse_date_shift_from_filename(self, filename: str):
        try:
            m_iso = re.search(r"(\d{4}-\d{2}-\d{2})[_\-]([A-Za-zÀ-ÖØ-öø-ÿ]+)", filename)
            if m_iso:
                return m_iso.group(1), m_iso.group(2)
            m_alt = re.search(r"(\d{2}-\d{2}-\d{4})[_\-]([A-Za-zÀ-ÖØ-öø-ÿ]+)", filename)
            if m_alt:
                return m_alt.group(1), m_alt.group(2)
        except Exception:
            pass
        return "", ""

    def _parse_date_to_ordinal(self, date_str: str):
        # Try YYYY-MM-DD then DD-MM-YYYY
        try:
            from datetime import datetime
            if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.toordinal()
            if re.match(r"^\d{2}-\d{2}-\d{4}$", date_str):
                dt = datetime.strptime(date_str, "%d-%m-%Y")
                return dt.toordinal()
        except Exception:
            return None
        return None

    def _parse_period_bounds(self, label: str):
        """Parse period label to (start_dt, end_dt). Accepts 'YYYY-MM-DD_au_YYYY-MM-DD' or 'YYYY-MM-DD au YYYY-MM-DD'."""
        from datetime import datetime
        try:
            if "_au_" in label:
                a, b = label.split("_au_", 1)
            elif " au " in label:
                a, b = label.split(" au ", 1)
            elif " - " in label:
                a, b = label.split(" - ", 1)
            else:
                return None, None
            a = a.strip()
            b = b.strip()
            # Normalize possible slashes
            a = a.replace("/", "-")
            b = b.replace("/", "-")
            start = datetime.strptime(a, "%Y-%m-%d")
            end = datetime.strptime(b, "%Y-%m-%d")
            return start, end
        except Exception:
            return None, None
