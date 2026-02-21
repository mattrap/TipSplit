"""Tk dialogs for payroll settings and calendar."""

from __future__ import annotations

from datetime import date, timedelta
from tkinter import Toplevel, messagebox, StringVar
from tkinter.simpledialog import askstring

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry, Spinbox

from payroll.pay_calendar import PayCalendarError
from payroll.time_utils import get_timezone, parse_local_iso

_settings_dialog = None
_calendar_dialog = None


def _ensure_manager(app, purpose: str = "cette action") -> bool:
    if hasattr(app, "require_manager_password"):
        return app.require_manager_password(purpose)
    if hasattr(app, "is_manager") and not app.is_manager():
        messagebox.showerror("Accès refusé", "Seuls les gestionnaires peuvent modifier ces paramètres.")
        return False
    return True


def open_payroll_settings_dialog(parent, app):
    global _settings_dialog
    if not _ensure_manager(app, "modifier les paramètres de paie"):
        return
    if _settings_dialog and _settings_dialog.winfo_exists():
        _settings_dialog.focus_force()
        return
    _settings_dialog = PayrollSettingsDialog(parent, app)


def open_pay_calendar_dialog(parent, app):
    global _calendar_dialog
    if not _ensure_manager(app, "consulter le calendrier de paie"):
        return
    if _calendar_dialog and _calendar_dialog.winfo_exists():
        _calendar_dialog.focus_force()
        return
    _calendar_dialog = PayCalendarDialog(parent, app)


class PayrollSettingsDialog(Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Paramètres de paie")
        self.resizable(False, False)
        self.vars = {
            "name": StringVar(),
            "timezone": StringVar(),
            "period_length_days": StringVar(),
            "pay_date_offset_days": StringVar(),
            "anchor_date": StringVar(),
            "effective_from": StringVar(),
        }
        self._date_format = "%Y-%m-%d"
        self._common_timezones = [
            "America/Montreal",
            "America/Toronto",
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "UTC",
        ]
        self._initial_state = {}
        self._dirty = False
        self._apply_defaults()
        self._build_ui()
        self._load_current()
        self._bind_changes()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _apply_defaults(self):
        today = date.today()
        # Anchor defaults to the most recent Sunday (including today).
        days_since_sunday = (today.weekday() + 1) % 7
        anchor_date = (today - timedelta(days=days_since_sunday)).isoformat()
        self.vars["name"].set("Horaire")
        self.vars["timezone"].set("America/Montreal")
        self.vars["period_length_days"].set("14")
        self.vars["pay_date_offset_days"].set("4")
        self.vars["anchor_date"].set(anchor_date)
        self.vars["effective_from"].set(today.isoformat())

    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.grid(row=0, column=0, sticky=NSEW)
        ttk.Label(frame, text="Nom").grid(row=0, column=0, sticky=W, pady=4)
        ttk.Entry(frame, textvariable=self.vars["name"], width=32).grid(row=0, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Fuseau horaire").grid(row=1, column=0, sticky=W, pady=4)
        self.tz_combo = ttk.Combobox(
            frame,
            textvariable=self.vars["timezone"],
            values=self._common_timezones,
            state="readonly",
            width=29,
        )
        self.tz_combo.grid(row=1, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Durée de période (jours)").grid(row=2, column=0, sticky=W, pady=4)
        self.period_length_spin = Spinbox(
            frame,
            from_=7,
            to=31,
            increment=1,
            width=8,
            justify="center",
            textvariable=self.vars["period_length_days"],
        )
        self.period_length_spin.grid(row=2, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Décalage Paye (jours)").grid(row=3, column=0, sticky=W, pady=4)
        self.pay_offset_spin = Spinbox(
            frame,
            from_=0,
            to=30,
            increment=1,
            width=8,
            justify="center",
            textvariable=self.vars["pay_date_offset_days"],
        )
        self.pay_offset_spin.grid(row=3, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Ancre (dimanche)").grid(row=4, column=0, sticky=W, pady=4)
        anchor_row = ttk.Frame(frame)
        anchor_row.grid(row=4, column=1, sticky=W, pady=4)
        self.anchor_date_picker = DateEntry(
            anchor_row,
            bootstyle="primary",
            dateformat=self._date_format,
            width=14,
        )
        self.anchor_date_picker.entry.configure(textvariable=self.vars["anchor_date"])
        self.anchor_date_picker.entry.bind("<Key>", lambda e: "break")
        self.anchor_date_picker.pack(side=LEFT)
        ttk.Label(anchor_row, text="à 06:00").pack(side=LEFT, padx=(6, 0))

        ttk.Label(frame, text="Entrée en vigueur").grid(row=5, column=0, sticky=W, pady=4)
        self.effective_date_picker = DateEntry(
            frame,
            bootstyle="primary",
            dateformat=self._date_format,
            width=14,
        )
        self.effective_date_picker.entry.configure(textvariable=self.vars["effective_from"])
        self.effective_date_picker.entry.bind("<Key>", lambda e: "break")
        self.effective_date_picker.grid(row=5, column=1, sticky=W, pady=4)

        ttk.Label(
            frame,
            text="L'ancre est fixe à 06:00 le dimanche. Le nouvel horaire ne modifie pas les périodes passées.",
            wraplength=360,
            bootstyle="secondary",
        ).grid(row=6, column=0, columnspan=2, pady=(6, 12), sticky=W)
        btns = ttk.Frame(frame)
        btns.grid(row=7, column=0, columnspan=2, sticky=E)
        ttk.Button(btns, text="Annuler", command=self._close, bootstyle="secondary").pack(side=RIGHT, padx=4)
        self.save_btn = ttk.Button(btns, text="Enregistrer", command=self._save, bootstyle="success")
        self.save_btn.pack(side=RIGHT, padx=4)

    def _load_current(self):
        context = self.app.get_payroll_context()
        schedule = None
        if context:
            try:
                schedule = context.get_schedule()
            except PayCalendarError:
                schedule = None
        if not schedule:
            messagebox.showerror("Paie", "Horaire actif introuvable. Valeurs par défaut affichées.")
            self._capture_initial_state()
            self._set_dirty(False)
            return
        self.vars["name"].set(schedule.get("name", "Horaire"))
        tz_value = schedule.get("timezone", "America/Montreal")
        if tz_value not in self._common_timezones:
            self._common_timezones.insert(0, tz_value)
            self.tz_combo.configure(values=self._common_timezones)
        self.vars["timezone"].set(tz_value)
        self.vars["period_length_days"].set(str(schedule.get("period_length_days", 14)))
        self.vars["pay_date_offset_days"].set(str(schedule.get("pay_date_offset_days", 4)))
        anchor_raw = schedule.get("anchor_start_local", "")
        anchor_date = anchor_raw.split("T")[0] if anchor_raw else ""
        self.vars["anchor_date"].set(anchor_date)
        today = date.today().isoformat()
        self.vars["effective_from"].set(today)
        self._capture_initial_state()
        self._set_dirty(False)

    def _bind_changes(self):
        for var in self.vars.values():
            var.trace_add("write", lambda *_: self._on_change())

    def _capture_initial_state(self):
        self._initial_state = {key: var.get() for key, var in self.vars.items()}

    def _set_dirty(self, value: bool):
        self._dirty = value
        if hasattr(self, "save_btn"):
            self.save_btn.configure(state=NORMAL if self._dirty else DISABLED)

    def _on_change(self):
        current = {key: var.get() for key, var in self.vars.items()}
        self._set_dirty(current != self._initial_state)

    def _save(self):
        if not self._dirty:
            return
        if not messagebox.askyesno("Confirmer", "Enregistrer les modifications de l'horaire de paie?"):
            return
        schedule = self.app.get_payroll_context()
        if not schedule:
            messagebox.showerror("Paie", "Horaire impossible à récupérer.")
            return
        tz_name = self.vars["timezone"].get().strip() or "America/Montreal"
        try:
            get_timezone(tz_name)
        except Exception as exc:
            messagebox.showerror("Fuseau horaire", f"Timezone invalide: {exc}")
            return
        try:
            period_length = int(self.vars["period_length_days"].get())
        except ValueError:
            messagebox.showerror("Durée", "Durée invalide")
            return
        try:
            pay_offset = int(self.vars["pay_date_offset_days"].get())
        except ValueError:
            messagebox.showerror("Décalage", "Décalage invalide")
            return
        anchor_date_str = self.vars["anchor_date"].get().strip()
        anchor_str = f"{anchor_date_str}T06:00"
        eff_str = self.vars["effective_from"].get().strip()
        try:
            eff_date = date.fromisoformat(eff_str)
        except ValueError:
            messagebox.showerror("Date", "Format de date invalide (AAAA-MM-JJ)")
            return
        try:
            tzinfo = get_timezone(tz_name)
            anchor_dt = parse_local_iso(anchor_str, tzinfo)
        except Exception as exc:
            messagebox.showerror("Ancre", f"Datetime invalide: {exc}")
            return
        if anchor_dt.weekday() != 6 or (anchor_dt.hour, anchor_dt.minute) != (6, 0):
            messagebox.showerror("Ancre", "L'ancre doit tomber un dimanche 06:00.")
            return
        name = self.vars["name"].get().strip() or "Horaire"
        service = self.app.pay_calendar_service
        try:
            new_schedule = service.create_schedule_version(
                name=name,
                timezone_name=tz_name,
                period_length_days=period_length,
                pay_date_offset_days=pay_offset,
                anchor_start_local=anchor_str,
                effective_from=eff_date,
                group_key=getattr(self.app.payroll_context, "group_key", "default"),
            )
            today = date.today()
            service.ensure_periods(
                new_schedule["id"],
                today - timedelta(days=180),
                today + timedelta(days=365),
            )
        except PayCalendarError as exc:
            messagebox.showerror("Horaire", str(exc))
            return
        if hasattr(self.app, "refresh_payroll_context"):
            self.app.payroll_context.set_schedule(new_schedule)
            self.app.refresh_payroll_context()
        messagebox.showinfo("Paramètres", "Nouvel horaire créé. Les périodes futures seront générées automatiquement.")
        self._capture_initial_state()
        self._set_dirty(False)
        self._close()

    def _close(self):
        global _settings_dialog
        _settings_dialog = None
        self.destroy()


class PayCalendarDialog(Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Calendrier de paie")
        self.geometry("720x420")
        self.periods = []
        self.tree = None
        self.status_var = StringVar(value="")
        self._build_ui()
        self.refresh_periods()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Rafraîchir", command=self.refresh_periods).pack(side=LEFT, padx=4)
        ttk.Button(toolbar, text="Générer 18 mois", command=self.ensure_window).pack(side=LEFT, padx=4)
        self.lock_btn = ttk.Button(toolbar, text="Verrouiller", command=self.lock_selected)
        self.lock_btn.pack(side=LEFT, padx=4)
        self.pay_btn = ttk.Button(toolbar, text="Marquer payé", command=self.mark_payed_selected)
        self.pay_btn.pack(side=LEFT, padx=4)
        self.override_btn = ttk.Button(toolbar, text="Modifier date de paie", command=self.override_pay_date)
        self.override_btn.pack(side=LEFT, padx=4)

        columns = ("display_id", "range", "pay_date", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        headings = {
            "display_id": "ID",
            "range": "Période",
            "pay_date": "Date de paye",
            "status": "Statut",
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, anchor=W, width=160 if col == "range" else 120, stretch=True)
        self.tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 5))
        self.tree.bind("<<TreeviewSelect>>", lambda *_: self._update_buttons())
        ttk.Label(self, textvariable=self.status_var, bootstyle="secondary", anchor=W).pack(fill=X, padx=10, pady=(0, 10))
        self._update_buttons()

    def refresh_periods(self):
        context = self.app.get_payroll_context()
        if not context:
            self.status_var.set("Contexte de paie indisponible")
            return
        try:
            rows = context.list_periods(limit=200)
        except PayCalendarError as exc:
            self.status_var.set(str(exc))
            return
        self.periods = rows
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=row["id"],
                values=(
                    row["display_id"],
                    row["range_label"],
                    row["pay_date_local"],
                    row.get("status_display") or row.get("status"),
                ),
            )
        self.status_var.set(f"{len(rows)} périodes chargées")
        self._update_buttons()

    def ensure_window(self):
        context = self.app.get_payroll_context()
        if not context:
            return
        context.ensure_window()
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def _selected_period(self):
        selection = self.tree.selection()
        if not selection:
            return None
        period_id = selection[0]
        for row in self.periods:
            if row["id"] == period_id:
                return row
        return None

    def _update_buttons(self):
        period = self._selected_period()
        has_period = period is not None
        manager = self.app.is_manager()
        admin = self.app.is_admin()
        state = NORMAL if (has_period and manager) else DISABLED
        self.lock_btn.configure(state=state)
        self.pay_btn.configure(state=state)
        self.override_btn.configure(state=NORMAL if (has_period and admin) else DISABLED)

    def lock_selected(self):
        period = self._selected_period()
        if not period:
            return
        try:
            self.app.pay_calendar_service.lock_period(period["id"])
        except PayCalendarError as exc:
            messagebox.showerror("Période", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def mark_payed_selected(self):
        period = self._selected_period()
        if not period:
            return
        try:
            self.app.pay_calendar_service.mark_payed(period["id"])
        except PayCalendarError as exc:
            messagebox.showerror("Période", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def override_pay_date(self):
        if not self.app.is_admin():
            messagebox.showerror("Accès", "Seuls les administrateurs peuvent modifier la date de paye.")
            return
        period = self._selected_period()
        if not period:
            return
        new_date = askstring("Nouvelle date", "Nouvelle date de paye (AAAA-MM-JJ):", parent=self)
        if not new_date:
            return
        try:
            date.fromisoformat(new_date.strip())
        except ValueError:
            messagebox.showerror("Date", "Format invalide (AAAA-MM-JJ)", parent=self)
            return
        reason = askstring("Raison", "Expliquez la raison de ce changement:", parent=self)
        if not reason:
            return
        try:
            self.app.pay_calendar_service.admin_override_period(
                period["id"],
                {"pay_date_local": new_date.strip()},
                reason=reason.strip(),
                admin_actor=getattr(self.app, "user_email", None),
            )
        except PayCalendarError as exc:
            messagebox.showerror("Override", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def _close(self):
        global _calendar_dialog
        _calendar_dialog = None
        self.destroy()
