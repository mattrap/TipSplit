"""Tk dialogs for payroll settings and calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
import traceback
from tkinter import Toplevel, messagebox, StringVar
from tkinter.simpledialog import askstring

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry, Spinbox

from AppConfig import get_payroll_setup_pending, set_payroll_setup_pending
from payroll.pay_calendar import PayCalendarError
from payroll.time_utils import get_timezone, parse_local_iso

_settings_dialog = None
_calendar_dialog = None
DEFAULT_TZ = "America/Montreal"
logger = logging.getLogger("tipsplit.pay_calendar.ui")


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
    # Backward-compatible entry point: open the calendar as a tab.
    if hasattr(app, "show_pay_calendar_tab"):
        logger.info("Open calendrier de paie (tab)")
        app.show_pay_calendar_tab()
        return
    global _calendar_dialog
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
        self.vars["timezone"].set(DEFAULT_TZ)
        self.vars["period_length_days"].set("14")
        self.vars["pay_date_offset_days"].set("4")
        self.vars["anchor_date"].set(anchor_date)
        self.vars["effective_from"].set(today.isoformat())

    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.grid(row=0, column=0, sticky=NSEW)
        ttk.Label(frame, text="Nom").grid(row=0, column=0, sticky=W, pady=(0, 4))
        ttk.Entry(frame, textvariable=self.vars["name"], width=32).grid(row=0, column=1, sticky=W, pady=(0, 4))

        ttk.Label(frame, text="Durée de période (jours)").grid(row=1, column=0, sticky=W, pady=4)
        self.period_length_spin = Spinbox(
            frame,
            from_=7,
            to=31,
            increment=1,
            width=8,
            justify="center",
            textvariable=self.vars["period_length_days"],
        )
        self.period_length_spin.grid(row=1, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Décalage de paie (jours)").grid(row=2, column=0, sticky=W, pady=4)
        self.pay_offset_spin = Spinbox(
            frame,
            from_=0,
            to=30,
            increment=1,
            width=8,
            justify="center",
            textvariable=self.vars["pay_date_offset_days"],
        )
        self.pay_offset_spin.grid(row=2, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Ancre (dimanche)").grid(row=3, column=0, sticky=W, pady=4)
        anchor_row = ttk.Frame(frame)
        anchor_row.grid(row=3, column=1, sticky=W, pady=4)
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

        ttk.Label(frame, text="Entrée en vigueur").grid(row=4, column=0, sticky=W, pady=4)
        self.effective_date_picker = DateEntry(
            frame,
            bootstyle="primary",
            dateformat=self._date_format,
            width=14,
        )
        self.effective_date_picker.entry.configure(textvariable=self.vars["effective_from"])
        self.effective_date_picker.entry.bind("<Key>", lambda e: "break")
        self.effective_date_picker.grid(row=4, column=1, sticky=W, pady=4)

        ttk.Label(frame, text="Fuseau horaire").grid(row=5, column=0, sticky=W, pady=4)
        self.tz_combo = ttk.Combobox(
            frame,
            textvariable=self.vars["timezone"],
            values=self._common_timezones,
            state="disabled",
            width=29,
        )
        self.tz_combo.grid(row=5, column=1, sticky=W, pady=4)

        ttk.Label(
            frame,
            text="Le fuseau horaire est fixé à America/Montreal pour stabiliser les périodes.",
            wraplength=360,
            bootstyle="secondary",
        ).grid(row=6, column=0, columnspan=2, pady=(2, 8), sticky=W)

        ttk.Label(
            frame,
            text="L'ancre est fixe à 06:00 le dimanche. Le nouvel horaire ne modifie pas les périodes passées.",
            wraplength=360,
            bootstyle="secondary",
        ).grid(row=7, column=0, columnspan=2, pady=(0, 12), sticky=W)
        btns = ttk.Frame(frame)
        btns.grid(row=8, column=0, columnspan=2, sticky=E)
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
        self.vars["timezone"].set(DEFAULT_TZ)
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
        tz_name = DEFAULT_TZ
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
        # Guard against changing settings that would affect periods with distributions
        try:
            context = self.app.get_payroll_context()
            if context:
                context.ensure_window()
                anchor_period = context.period_for_local_date(anchor_dt.date())
                rows = context.list_periods(limit=500)
                sorted_rows = sorted(rows, key=lambda r: r.get("start_date_iso") or "")
                row_by_id = {row.get("id"): row for row in sorted_rows}
                current = row_by_id.get(anchor_period.get("id"))
                if current:
                    is_blocked = current.get("has_data") or current.get("status") in ("OPEN", "LOCKED")
                else:
                    is_blocked = False
                if is_blocked:
                    next_empty_start = None
                    current_index = None
                    for idx, row in enumerate(sorted_rows):
                        if row.get("id") == anchor_period.get("id"):
                            current_index = idx
                            break
                    start_idx = (current_index + 1) if current_index is not None else 0
                    for row in sorted_rows[start_idx:]:
                        if row.get("start_date_iso") and row.get("status_display") == "EMPTY":
                            next_empty_start = row.get("start_date_iso")
                            break
                    if next_empty_start:
                        messagebox.showerror(
                            "Paramètres",
                            f"La date d’effet doit être au plus tôt le {next_empty_start} (première période vide).",
                        )
                    else:
                        messagebox.showerror(
                            "Paramètres",
                            "La date d’effet doit être après la prochaine période vide.",
                        )
                    return
        except Exception:
            messagebox.showerror("Paramètres", "Impossible de valider la date d’effet.")
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


class PayCalendarTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.periods = []
        self.tree = None
        self.status_var = StringVar(value="")
        self.setup_frame = None
        self.setup_anchor_var = StringVar()
        self._in_select = False
        self._active_tree = None
        self._refreshing = False
        self._build_ui()
        if get_payroll_setup_pending():
            self.status_var.set("Configuration requise: choisissez l’ancre de paie.")
        else:
            self.refresh_periods()

    def _build_ui(self):
        if get_payroll_setup_pending():
            self._build_setup_banner()
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
        self.revert_btn = ttk.Button(toolbar, text="Rétablir à verrouillé", command=self.revert_payed_selected)
        self.revert_btn.pack(side=LEFT, padx=4)

        columns = ("display_id", "range", "pay_date", "status")
        headings = {
            "display_id": "ID",
            "range": "Période",
            "pay_date": "Date de paye",
            "status": "Statut",
        }

        def _build_section(parent, label, height):
            section = ttk.Frame(parent)
            section.pack(fill=BOTH, expand=True, padx=10, pady=(0, 6))
            ttk.Label(section, text=label, bootstyle="secondary").pack(anchor=W, pady=(0, 2))
            tree = ttk.Treeview(section, columns=columns, show="headings", height=height)
            for col in columns:
                tree.heading(col, text=headings[col])
                tree.column(col, anchor=W, width=160 if col == "range" else 120, stretch=True)
            tree.pack(fill=BOTH, expand=True)
            tree.bind("<<TreeviewSelect>>", lambda _evt, t=tree: self._on_select(t))
            return tree

        self.past_tree = _build_section(self, "Passées", 6)
        self.open_tree = _build_section(self, "Ouvertes", 6)
        self.upcoming_tree = _build_section(self, "À venir", 6)

        ttk.Label(self, textvariable=self.status_var, bootstyle="secondary", anchor=W).pack(fill=X, padx=10, pady=(0, 10))
        self._update_buttons()

    def _default_anchor_date(self) -> str:
        today = date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        anchor_date = today - timedelta(days=days_since_sunday)
        return anchor_date.isoformat()

    def _build_setup_banner(self):
        if self.setup_frame and self.setup_frame.winfo_exists():
            return
        logger.info("Affiche la bannière de configuration du calendrier de paie")
        frame = ttk.Frame(self, padding=10, bootstyle="info")
        frame.pack(fill=X, padx=10, pady=(10, 0))
        self.setup_frame = frame
        ttk.Label(
            frame,
            text="Première configuration: choisissez l’ancre de la période de paie (dimanche).",
            bootstyle="info",
            wraplength=760,
            anchor=W,
        ).pack(fill=X)
        row = ttk.Frame(frame)
        row.pack(fill=X, pady=(6, 0))
        ttk.Label(row, text="Ancre (dimanche):").pack(side=LEFT)
        self.setup_anchor_var.set(self._default_anchor_date())
        self.setup_anchor_picker = DateEntry(
            row,
            bootstyle="primary",
            dateformat="%Y-%m-%d",
            width=14,
        )
        self.setup_anchor_picker.entry.configure(textvariable=self.setup_anchor_var)
        self.setup_anchor_picker.entry.bind("<Key>", lambda e: "break")
        self.setup_anchor_picker.pack(side=LEFT, padx=(6, 6))
        ttk.Label(row, text="à 06:00").pack(side=LEFT)
        ttk.Button(
            row,
            text="Appliquer l’ancre",
            bootstyle="success",
            command=self._apply_setup_anchor,
        ).pack(side=LEFT, padx=(12, 0))

    def _hide_setup_banner(self):
        if self.setup_frame and self.setup_frame.winfo_exists():
            self.setup_frame.destroy()
        self.setup_frame = None

    def _apply_setup_anchor(self):
        logger.info("Tentative d'application de l'ancre de paie (setup)")
        if not get_payroll_setup_pending():
            self._hide_setup_banner()
            return
        anchor_text = (self.setup_anchor_var.get() or "").strip()
        try:
            anchor_date = date.fromisoformat(anchor_text)
        except ValueError:
            logger.warning("Ancre invalide (format): %s", anchor_text)
            messagebox.showerror("Ancre", "Format invalide (AAAA-MM-JJ)", parent=self)
            return
        if anchor_date.weekday() != 6:
            logger.warning("Ancre invalide (pas dimanche): %s", anchor_text)
            messagebox.showerror("Ancre", "L’ancre doit être un dimanche.", parent=self)
            return
        context = self.app.get_payroll_context()
        if not context:
            logger.error("Contexte de paie indisponible pendant le setup")
            messagebox.showerror("Ancre", "Contexte de paie indisponible.", parent=self)
            return
        try:
            schedule = context.get_schedule()
            anchor_dt = datetime.combine(anchor_date, time(hour=6, minute=0))
            anchor_str = anchor_dt.isoformat(timespec="seconds")
            logger.info("Création d'un nouvel horaire via setup: anchor=%s", anchor_str)
            new_schedule = self.app.pay_calendar_service.create_schedule_version(
                name=schedule.get("name") or "Horaire",
                timezone_name=schedule["timezone"],
                period_length_days=int(schedule["period_length_days"]),
                pay_date_offset_days=int(schedule["pay_date_offset_days"]),
                anchor_start_local=anchor_str,
                effective_from=anchor_date,
                group_key=getattr(self.app.payroll_context, "group_key", "default"),
            )
            today = date.today()
            logger.info("Génération des périodes (setup) autour de %s", today.isoformat())
            self.app.pay_calendar_service.ensure_periods(
                new_schedule["id"],
                today - timedelta(days=180),
                today + timedelta(days=365),
            )
        except PayCalendarError as exc:
            logger.exception("Erreur PayCalendar lors de l'application de l'ancre: %s", exc)
            messagebox.showerror("Ancre", str(exc), parent=self)
            return
        except Exception as exc:
            logger.exception("Erreur inattendue lors de l'application de l'ancre")
            messagebox.showerror("Ancre", f"Erreur inattendue: {exc}", parent=self)
            return
        logger.info("Ancre appliquée avec succès")
        self.app.payroll_context.set_schedule(new_schedule)
        self.app.refresh_payroll_context()
        set_payroll_setup_pending(False)
        self._hide_setup_banner()
        self.refresh_periods()
        if hasattr(self.app, "on_payroll_setup_completed"):
            self.app.on_payroll_setup_completed()

    def refresh_periods(self):
        if self._refreshing:
            logger.warning(
                "refresh_periods déjà en cours; appel ignoré.\n%s",
                "".join(traceback.format_stack(limit=6)),
            )
            return
        if get_payroll_setup_pending():
            self.status_var.set("Configuration requise: choisissez l’ancre de paie.")
            self._update_buttons()
            return
        context = self.app.get_payroll_context()
        if not context:
            logger.error("Contexte de paie indisponible lors du refresh")
            self.status_var.set("Contexte de paie indisponible")
            return
        try:
            self._refreshing = True
            logger.info("Chargement des périodes de paie")
            rows = context.list_periods(limit=200)
        except PayCalendarError as exc:
            logger.exception("Erreur PayCalendar lors du chargement des périodes: %s", exc)
            self.status_var.set(str(exc))
            return
        finally:
            self._refreshing = False
        self.periods = rows
        for tree in (self.past_tree, self.open_tree, self.upcoming_tree):
            for item in tree.get_children():
                tree.delete(item)

        past = []
        open_rows = []
        upcoming = []
        for row in rows:
            status = row.get("status")
            display = row.get("status_display") or status
            if status == "PAYED":
                past.append(row)
            elif display == "EMPTY":
                upcoming.append(row)
            else:
                open_rows.append(row)

        def _insert_rows(tree, group_rows):
            for row in group_rows:
                tree.insert(
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

        _insert_rows(self.past_tree, past)
        _insert_rows(self.open_tree, open_rows)
        _insert_rows(self.upcoming_tree, upcoming)
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
        selection = None
        if self._active_tree is not None:
            selection = self._active_tree.selection()
        if not selection:
            for tree in (self.past_tree, self.open_tree, self.upcoming_tree):
                sel = tree.selection()
                if sel:
                    selection = sel
                    self._active_tree = tree
                    break
        if not selection:
            return None
        period_id = selection[0]
        for row in self.periods:
            if row["id"] == period_id:
                return row
        return None

    def _on_select(self, active_tree):
        self._active_tree = active_tree
        if self._in_select:
            return
        self._in_select = True
        try:
            self._update_buttons()
        finally:
            self._in_select = False

    def _update_buttons(self):
        period = self._selected_period()
        has_period = period is not None
        if not has_period:
            self.lock_btn.configure(state=DISABLED, text="Verrouiller")
            self.pay_btn.configure(state=DISABLED)
            self.override_btn.configure(state=DISABLED)
            self.revert_btn.configure(state=DISABLED)
            return
        status = period.get("status")
        if status == "LOCKED":
            self.lock_btn.configure(text="Déverrouiller")
        else:
            self.lock_btn.configure(text="Verrouiller")
        if status == "PAYED":
            self.lock_btn.configure(state=DISABLED)
            self.pay_btn.configure(state=DISABLED)
            self.revert_btn.configure(state=NORMAL)
        else:
            self.lock_btn.configure(state=NORMAL)
            self.pay_btn.configure(state=NORMAL)
            self.revert_btn.configure(state=DISABLED)
        self.override_btn.configure(state=NORMAL)

    def lock_selected(self):
        period = self._selected_period()
        if not period:
            return
        if period.get("status") == "LOCKED":
            return self.unlock_selected()
        if period.get("status") == "PAYED":
            return
        if hasattr(self.app, "require_manager_password"):
            if not self.app.require_manager_password("verrouiller une période de paie"):
                return
        try:
            logger.info("Verrouiller période %s", period.get("id"))
            self.app.pay_calendar_service.lock_period(period["id"])
        except PayCalendarError as exc:
            logger.exception("Erreur verrouillage période %s: %s", period.get("id"), exc)
            messagebox.showerror("Période", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def mark_payed_selected(self):
        period = self._selected_period()
        if not period:
            return
        if period.get("status") == "PAYED":
            return
        if hasattr(self.app, "require_manager_password"):
            if not self.app.require_manager_password("marquer une période comme payée"):
                return
        try:
            logger.info("Marquer payé période %s", period.get("id"))
            self.app.pay_calendar_service.mark_payed(period["id"])
        except PayCalendarError as exc:
            logger.exception("Erreur marquer payé période %s: %s", period.get("id"), exc)
            messagebox.showerror("Période", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def revert_payed_selected(self):
        period = self._selected_period()
        if not period:
            return
        if period.get("status") != "PAYED":
            return
        if hasattr(self.app, "require_manager_password"):
            if not self.app.require_manager_password("rétablir une période à verrouillée"):
                return
        try:
            logger.info("Rétablir période %s à verrouillée", period.get("id"))
            self.app.pay_calendar_service.revert_payed(period["id"])
        except PayCalendarError as exc:
            logger.exception("Erreur rétablir période %s: %s", period.get("id"), exc)
            messagebox.showerror("Période", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def unlock_selected(self):
        period = self._selected_period()
        if not period:
            return
        if period.get("status") != "LOCKED":
            return
        if hasattr(self.app, "require_manager_password"):
            if not self.app.require_manager_password("déverrouiller une période de paie"):
                return
        try:
            logger.info("Déverrouiller période %s", period.get("id"))
            self.app.pay_calendar_service.unlock_period(period["id"])
        except PayCalendarError as exc:
            logger.exception("Erreur déverrouiller période %s: %s", period.get("id"), exc)
            messagebox.showerror("Période", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

    def override_pay_date(self):
        if not self.app.is_admin():
            messagebox.showerror("Accès", "Seuls les administrateurs peuvent modifier la date de paye.")
            return
        if hasattr(self.app, "require_manager_password"):
            if not self.app.require_manager_password("modifier la date de paie"):
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
            logger.info("Override date de paye période %s -> %s", period.get("id"), new_date)
            self.app.pay_calendar_service.admin_override_period(
                period["id"],
                {"pay_date_local": new_date.strip()},
                reason=reason.strip(),
                admin_actor=getattr(self.app, "user_email", None),
            )
        except PayCalendarError as exc:
            logger.exception("Erreur override période %s: %s", period.get("id"), exc)
            messagebox.showerror("Override", str(exc), parent=self)
            return
        self.app.refresh_payroll_context()
        self.refresh_periods()

class PayCalendarDialog(Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Calendrier de paie")
        self.geometry("720x420")
        self.tab = PayCalendarTab(self, app)
        self.tab.pack(fill=BOTH, expand=True)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        global _calendar_dialog
        _calendar_dialog = None
        self.destroy()
