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

        chart_group = ttk.LabelFrame(right, text="Analyse — Période sélectionnée")
        chart_group.pack(fill=BOTH, expand=True)

        # UI state
        self.agg_mode = tk.StringVar(value="day")  # 'day' or 'day_shift' or 'weekday'
        self.metric_choice = tk.StringVar(value="Ventes Nettes")

        # Controls above canvas
        controls = ttk.Frame(chart_group)
        controls.pack(fill=X, padx=6, pady=(6, 0))
        ttk.Label(controls, text="Regrouper:").pack(side=LEFT)
        ttk.Radiobutton(controls, text="Par jour", variable=self.agg_mode, value="day", command=self.update_chart).pack(side=LEFT, padx=(6, 0))
        ttk.Radiobutton(controls, text="Par jour + quart (MATIN/SOIR)", variable=self.agg_mode, value="day_shift", command=self.update_chart).pack(side=LEFT, padx=(6, 0))
        ttk.Radiobutton(controls, text="Par jour de semaine", variable=self.agg_mode, value="weekday", command=self.update_chart).pack(side=LEFT, padx=(6, 0))
        ttk.Label(controls, text="  |  Metric:").pack(side=LEFT, padx=(10, 0))
        self.metric_combo = ttk.Combobox(controls, textvariable=self.metric_choice, width=28, state="readonly",
                                         values=["Ventes Nettes", "Ventes / heure Service", "Tip %"])
        self.metric_combo.pack(side=LEFT, padx=(6, 0))
        self.metric_combo.bind("<<ComboboxSelected>>", lambda e: self.update_chart())

        self.chart_canvas = tk.Canvas(chart_group, height=scale(420), background="#fafafa", highlightthickness=0)
        self.chart_canvas.pack(fill=BOTH, expand=True, padx=6, pady=6)

        # Initial placeholder
        self._draw_placeholder(self.chart_canvas, "Sélectionnez une période à analyser…")

        # Summary table below chart
        summary_group = ttk.LabelFrame(right, text="Résumé — Période sélectionnée")
        summary_group.pack(fill=X, expand=False, padx=0, pady=(0, 10))
        cols = [
            "Scope",
            "Ventes Nettes",
            "Heures Service",
            "Ventes / Heure Service",
            "Pourboires (ajustés)",
            "Tip %",
        ]
        # Summary controls (weekday summary popup)
        summary_controls = ttk.Frame(summary_group)
        summary_controls.pack(fill=X, padx=6, pady=(6, 0))
        ttk.Button(summary_controls, text="Résumé par jour de semaine", command=self._open_weekday_summary_popup).pack(side=LEFT)

        self.summary_tree = ttk.Treeview(summary_group, columns=cols, show="headings", height=3)
        for c in cols:
            anchor = tk.W if c == "Scope" else tk.E
            width = 160 if c == "Scope" else 140
            self.summary_tree.heading(c, text=c)
            self.summary_tree.column(c, width=scale(width), anchor=anchor, stretch=True)
        self.summary_tree.pack(fill=X, padx=6, pady=6)

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
        self.update_chart()
        self._update_summary_table(self.current_combined)

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

    def update_chart(self):
        """
        Read current_combined and UI state (aggregation mode + metric),
        compute the series, and draw bars.
        Metrics supported: 'ventes_nettes', 'ventes_per_hr_service', 'tip_pct'.
        """
        c = self.chart_canvas
        c.delete("all")
        if not self.current_combined or not self.current_period_label:
            self._draw_placeholder(c, "Sélectionnez une période à analyser…")
            return

        metric_key = {
            "Ventes Nettes": "ventes_nettes",
            "Ventes / heure Service": "ventes_per_hr_service",
            "Tip %": "tip_pct",
        }.get(self.metric_choice.get(), "ventes_nettes")

        agg_mode = self.agg_mode.get()
        start_dt, end_dt = self._parse_period_bounds(self.current_period_label)

        if agg_mode == "day":
            data = self._aggregate_per_day(self.current_combined)
            x_labels = []
            values = []
            from datetime import datetime, timedelta
            if start_dt and end_dt:
                cur = start_dt
                while cur <= end_dt:
                    key = cur.strftime("%Y-%m-%d")
                    rec = data.get(key, {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0})
                    val = self._metric_from_record(rec, metric_key)
                    x_labels.append(cur.strftime("%m-%d"))
                    values.append(val)
                    cur += timedelta(days=1)
            else:
                keys = sorted(data.keys())
                for k in keys:
                    try:
                        dt = datetime.strptime(k, "%Y-%m-%d")
                    except Exception:
                        continue
                    rec = data.get(k, {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0})
                    val = self._metric_from_record(rec, metric_key)
                    x_labels.append(dt.strftime("%m-%d"))
                    values.append(val)
            y_suffix = "%" if metric_key == "tip_pct" else None
            self._draw_bars(x_labels, values, y_suffix=y_suffix)
        elif agg_mode == "weekday":
            # Aggregate per weekday and plot Monday -> Sunday
            data = self._aggregate_per_weekday(self.current_combined)
            weekdays_order = [
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
            ]
            x_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            values = []
            for name in weekdays_order:
                rec = data.get(name, {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0})
                values.append(self._metric_from_record(rec, metric_key))
            y_suffix = "%" if metric_key == "tip_pct" else None
            self._draw_bars(x_labels, values, y_suffix=y_suffix)
        else:
            data = self._aggregate_per_day_shift(self.current_combined)
            # Build labels by available keys sorted by date then shift order
            from datetime import datetime
            def sort_key(item):
                (date_iso, shift) = item[0]
                try:
                    dt = datetime.strptime(date_iso, "%Y-%m-%d")
                except Exception:
                    dt = None
                order = {"MATIN": 0, "SOIR": 1, "NA": 2}.get(shift, 2)
                return (dt.toordinal() if dt else 0, order)

            items = sorted(data.items(), key=sort_key)
            x_labels, values = [], []
            for (date_iso, shift), rec in items:
                try:
                    dt = datetime.strptime(date_iso, "%Y-%m-%d")
                    base = dt.strftime("%m-%d")
                except Exception:
                    base = date_iso
                suffix = "M" if shift == "MATIN" else ("S" if shift == "SOIR" else "?")
                x_labels.append(f"{base} {suffix}")
                values.append(self._metric_from_record(rec, metric_key))
            y_suffix = "%" if metric_key == "tip_pct" else None
            if not x_labels:
                self._draw_placeholder(c, "Aucune donnée pour ce mode")
                return
            self._draw_bars(x_labels, values, y_suffix=y_suffix)

        # Keep summary synchronized with any toggle change
        self._update_summary_table(self.current_combined)

    def _metric_from_record(self, rec: dict, metric_key: str) -> float:
        ventes = float(rec.get("ventes_nettes", 0.0) or 0.0)
        hours = float(rec.get("service_hours", 0.0) or 0.0)
        tips = float(rec.get("tips_adj", 0.0) or 0.0)
        if metric_key == "ventes_nettes":
            return ventes
        elif metric_key == "ventes_per_hr_service":
            return (ventes / hours) if hours > 0 else 0.0
        elif metric_key == "tip_pct":
            return (tips / ventes) if ventes > 0 else 0.0
        return 0.0

    # ----------------------- Analysis -----------------------
    # ----------------------- Drawing helpers -----------------------
    def _draw_placeholder(self, canvas: tk.Canvas, text: str):
        canvas.delete("all")
        w = canvas.winfo_width() or 600
        h = canvas.winfo_height() or 260
        x = w // 2
        y = h // 2
        canvas.create_text(x, y, text=text, fill="#666666", font=("Helvetica", 12))

    def _draw_bars(self, x_labels, values, y_suffix=None):
        c = self.chart_canvas
        w = c.winfo_width() or 900
        h = c.winfo_height() or 420

        if not x_labels or not values or len(x_labels) != len(values):
            self._draw_placeholder(c, "Aucune donnée à afficher")
            return

        # Prepare display values (percent scaling if needed)
        if y_suffix == "%":
            dvalues = [float(v or 0.0) * 100.0 for v in values]
        else:
            dvalues = [float(v or 0.0) for v in values]

        vmax = max(dvalues) if dvalues else 1.0
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
        n = len(dvalues)
        gap = 6
        bar_w = max(8, int((plot_w - gap * (n + 1)) / max(1, n)))
        x = left + gap

        for i, val in enumerate(dvalues):
            bh = int((val / vmax) * plot_h) if vmax > 0 else 0
            x0 = x
            y0 = h - bottom - bh
            x1 = x + bar_w
            y1 = h - bottom
            c.create_rectangle(x0, y0, x1, y1, fill="#4e79a7", outline="")
            # value label
            if y_suffix == "%":
                label_text = f"{val:.1f}%"
            else:
                label_text = f"{val:.0f}"
            c.create_text((x0 + x1)//2, y0 - 10, text=label_text, fill="#333", font=("Helvetica", 9))
            # x label
            lab = x_labels[i]
            c.create_text((x0 + x1)//2, y1 + 12, text=lab, angle=0, font=("Helvetica", 9))
            x += bar_w + gap

        # y scale labels (0 and max)
        y_max_label = f"{vmax:.1f}%" if y_suffix == "%" else f"{vmax:.0f}"
        c.create_text(left - 10, h - bottom, text="0" + ("%" if y_suffix == "%" else ""), anchor=E, font=("Helvetica", 9))
        c.create_text(left - 10, top, text=y_max_label, anchor=E, font=("Helvetica", 9))

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

    # ----------------------- New data collectors -----------------------
    def _iter_distributions(self, combined: dict):
        """Yield (date_iso, shift_upper, inputs_dict, employees_list) for each valid distribution."""
        if not isinstance(combined, dict):
            return
        dists = combined.get("distributions", [])
        if not isinstance(dists, list):
            return
        from datetime import datetime
        for item in dists:
            if not isinstance(item, dict) or "error" in item:
                continue
            filename = safe_str(item.get("filename", ""))
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue
            fname_noext = os.path.splitext(filename)[0]
            date_str, shift_raw = self._parse_date_shift_from_filename(fname_noext)
            if not date_str:
                continue
            date_iso = ""
            try:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                    date_iso = date_str
                elif re.match(r"^\d{2}-\d{2}-\d{4}$", date_str):
                    dt = datetime.strptime(date_str, "%d-%m-%Y")
                    date_iso = dt.strftime("%Y-%m-%d")
                else:
                    # Attempt generic parse
                    dt = datetime.fromisoformat(date_str)
                    date_iso = dt.strftime("%Y-%m-%d")
            except Exception:
                continue
            shift_upper = safe_str(shift_raw).strip().upper()
            if "MAT" in shift_upper:
                shift_upper = "MATIN"
            elif "SOIR" in shift_upper or shift_upper == "PM":
                shift_upper = "SOIR"
            else:
                shift_upper = "NA"
            inputs = content.get("inputs", {}) if isinstance(content.get("inputs", {}), dict) else {}
            employees = content.get("employees", []) if isinstance(content.get("employees", []), list) else []
            yield (date_iso, shift_upper, inputs, employees)

    def _collect_service_hours(self, employees: list) -> float:
        """Sum hours for section containing 'Service' (case-insensitive)."""
        total = 0.0
        if not isinstance(employees, list):
            return 0.0
        for emp in employees:
            if not isinstance(emp, dict):
                continue
            section = safe_str(emp.get("section", ""))
            hours = to_float(emp.get("hours", 0.0))
            if "service" in section.lower():
                total += float(hours or 0.0)
        return float(total)

    def _compute_adjusted_tips(self, inputs: dict) -> float:
        """(- Dépot Net) + Cash + (Frais Admin * 0.8). Use to_float for all fields."""
        depot_net = to_float(inputs.get("Dépot Net", 0.0))
        cash = to_float(inputs.get("Cash", 0.0))
        frais_admin = to_float(inputs.get("Frais Admin", 0.0))
        return (-depot_net) + cash + (frais_admin * 0.8)

    # ----------------------- Aggregations -----------------------
    def _aggregate_per_day(self, combined: dict):
        """
        Return dict keyed by date_iso -> {
            'ventes_nettes': float,
            'service_hours': float,
            'tips_adj': float
        }
        where:
          ventes_per_hr_service = ventes_nettes / max(service_hours, 0.0001)
          tip_pct = tips_adj / max(ventes_nettes, 0.0001)
        """
        out = {}
        for date_iso, _shift, inputs, employees in self._iter_distributions(combined):
            ventes = to_float(inputs.get("Ventes Nettes", 0.0))
            hours = self._collect_service_hours(employees)
            tips = self._compute_adjusted_tips(inputs)
            rec = out.get(date_iso)
            if not rec:
                rec = {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0}
                out[date_iso] = rec
            rec["ventes_nettes"] += float(ventes or 0.0)
            rec["service_hours"] += float(hours or 0.0)
            rec["tips_adj"] += float(tips or 0.0)
        return out

    def _aggregate_per_day_shift(self, combined: dict):
        """
        Return dict keyed by (date_iso, shift_upper) -> same value dict as above.
        shift_upper is 'MATIN' or 'SOIR' (normalize unknown shift to 'NA').
        """
        out = {}
        for date_iso, shift, inputs, employees in self._iter_distributions(combined):
            ventes = to_float(inputs.get("Ventes Nettes", 0.0))
            hours = self._collect_service_hours(employees)
            tips = self._compute_adjusted_tips(inputs)
            key = (date_iso, shift)
            rec = out.get(key)
            if not rec:
                rec = {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0}
                out[key] = rec
            rec["ventes_nettes"] += float(ventes or 0.0)
            rec["service_hours"] += float(hours or 0.0)
            rec["tips_adj"] += float(tips or 0.0)
        return out

    def _aggregate_per_weekday(self, combined: dict):
        """
        Return dict keyed by weekday_name ("Monday".."Sunday") -> {
            'ventes_nettes': float,
            'service_hours': float,
            'tips_adj': float
        }
        where:
          ventes_per_hr_service = ventes_nettes / max(service_hours, 0.0001)
          tip_pct = tips_adj / max(ventes_nettes, 0.0001)
        """
        from datetime import datetime
        out = {}
        for date_iso, _shift, inputs, employees in self._iter_distributions(combined):
            try:
                dt = datetime.strptime(date_iso, "%Y-%m-%d")
                weekday_name = dt.strftime("%A")
            except Exception:
                continue
            ventes = to_float(inputs.get("Ventes Nettes", 0.0))
            hours = self._collect_service_hours(employees)
            tips = self._compute_adjusted_tips(inputs)
            rec = out.get(weekday_name)
            if not rec:
                rec = {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0}
                out[weekday_name] = rec
            rec["ventes_nettes"] += float(ventes or 0.0)
            rec["service_hours"] += float(hours or 0.0)
            rec["tips_adj"] += float(tips or 0.0)
        return out

    # ----------------------- Summary table -----------------------
    def _update_summary_table(self, combined: dict):
        """
        Compute totals for the whole period and split by shift (MATIN, SOIR).
        Fill the Treeview with three rows.
        """
        # Clear existing
        try:
            for iid in self.summary_tree.get_children():
                self.summary_tree.delete(iid)
        except Exception:
            pass

        if not isinstance(combined, dict):
            return

        totals = {
            "ALL": {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0},
            "MATIN": {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0},
            "SOIR": {"ventes_nettes": 0.0, "service_hours": 0.0, "tips_adj": 0.0},
        }

        for _date_iso, shift, inputs, employees in self._iter_distributions(combined):
            ventes = to_float(inputs.get("Ventes Nettes", 0.0))
            hours = self._collect_service_hours(employees)
            tips = self._compute_adjusted_tips(inputs)
            for bucket in ("ALL", shift if shift in ("MATIN", "SOIR") else None):
                if not bucket:
                    continue
                totals[bucket]["ventes_nettes"] += float(ventes or 0.0)
                totals[bucket]["service_hours"] += float(hours or 0.0)
                totals[bucket]["tips_adj"] += float(tips or 0.0)

        def fmt_row(scope, rec):
            ventes = float(rec.get("ventes_nettes", 0.0) or 0.0)
            hours = float(rec.get("service_hours", 0.0) or 0.0)
            tips = float(rec.get("tips_adj", 0.0) or 0.0)
            per_hr = (ventes / hours) if hours > 0 else 0.0
            tip_pct = (tips / ventes) if ventes > 0 else 0.0
            return [
                scope,
                f"{ventes:.2f}",
                f"{hours:.2f}",
                f"{per_hr:.2f}",
                f"{tips:.2f}",
                f"{tip_pct*100:.1f}%",
            ]

        rows = [
            fmt_row("Total (Période)", totals["ALL"]),
            fmt_row("MATIN", totals["MATIN"]),
            fmt_row("SOIR", totals["SOIR"]),
        ]
        for r in rows:
            self.summary_tree.insert("", END, values=r)

    # ----------------------- Weekday summary popup -----------------------
    def _open_weekday_summary_popup(self):
        if not self.current_combined:
            return
        data = self._aggregate_per_weekday(self.current_combined)

        top = tk.Toplevel(self.frame)
        top.title("Résumé par jour de semaine")
        try:
            top.geometry(f"{scale(800)}x{scale(360)}")
        except Exception:
            pass

        cols = [
            "Weekday",
            "Ventes Nettes",
            "Heures Service",
            "Ventes / Heure Service",
            "Pourboires (ajustés)",
            "Tip %",
        ]
        tree = ttk.Treeview(top, columns=cols, show="headings")
        for c in cols:
            anchor = tk.W if c == "Weekday" else tk.E
            width = 150 if c == "Weekday" else 140
            tree.heading(c, text=c)
            tree.column(c, width=scale(width), anchor=anchor, stretch=True)
        tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        weekdays_order = [
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
        ]
        for name in weekdays_order:
            rec = data.get(name)
            if not rec:
                continue  # only present weekdays
            ventes = float(rec.get("ventes_nettes", 0.0) or 0.0)
            hours = float(rec.get("service_hours", 0.0) or 0.0)
            tips = float(rec.get("tips_adj", 0.0) or 0.0)
            per_hr = (ventes / hours) if hours > 0 else 0.0
            tip_pct = (tips / ventes) if ventes > 0 else 0.0
            tree.insert("", END, values=[
                name,
                f"{ventes:.2f}",
                f"{hours:.2f}",
                f"{per_hr:.2f}",
                f"{tips:.2f}",
                f"{tip_pct*100:.1f}%",
            ])

        btns = ttk.Frame(top)
        btns.pack(fill=X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Fermer", command=top.destroy).pack(side=RIGHT)
