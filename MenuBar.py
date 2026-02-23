import os
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, BooleanVar
from tkinter.simpledialog import askfloat
from datetime import datetime

# Config helpers
from AppConfig import (
    get_pdf_dir, set_pdf_dir,
    get_auto_check_updates, set_auto_check_updates,  # toggle for auto updates
    get_ui_scale, set_ui_scale,
)

from updater import check_for_update
from app_version import APP_NAME, APP_VERSION
from datetime import datetime
from distribution_settings import open_distribution_settings
from payroll.ui import open_payroll_settings_dialog, open_pay_calendar_dialog


class ManagerProgress:
    """
    Small progress indicator shown in the menu bar that reflects the
    manager workflow and shows the next step to complete. Steps:
      1) Enter date (Time Sheet)
      2) Enter hours (Time Sheet)
      3) Confirmer! (Time Sheet)
      4) sélectionnez un shift (Matin ou Soir)
      5) Enter distribution and Déclaration values (Distribution)
      6) Exporter! (Export clicked)
    """

    STEPS = [
        "Entrer la date (Time Sheet)",
        "Entrer les heures (Time Sheet)",
        "Confirmer!",
        "Sélectionner un shift (Matin ou Soir)",
        "Entrez les valeures de Distribution et Déclaration (Distribution)",
        "Exporter!",
    ]

    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self.frame.pack(side=LEFT, padx=10)

        # Label showing next step text
        self.next_label = ttk.Label(self.frame, text="", font=("Helvetica", 10))
        self.next_label.pack(side=TOP, anchor=W)

        # Green progress bar
        self.pb = ttk.Progressbar(
            self.frame,
            orient=HORIZONTAL,
            length=260,
            mode="determinate",
            bootstyle="success-striped",
            maximum=len(self.STEPS)
        )
        self.pb.pack(side=TOP, fill=X, expand=False)

        # Internal state
        self._last_export_token = None

        # Start periodic updates
        self._tick()

    # ---- State inspection helpers ----
    def _date_entered(self):
        try:
            ts = getattr(self.app, "timesheet_tab", None)
            if not ts:
                return False
            s = ts.date_picker.entry.get().strip()
            if not s:
                return False
            datetime.strptime(s, "%d-%m-%Y")
            return True
        except Exception:
            return False

    def _hours_entered(self):
        # Consider hours entered if any row has total > 0 (do not rely on transfer here)
        try:
            # Prefer direct check on the TimeSheet widget state
            ts = getattr(self.app, "timesheet_tab", None)
            if ts and getattr(ts, "punch_data", None):
                for v in ts.punch_data.values():
                    try:
                        if float(v.get("total", 0.0)) > 0:
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False

    def _confirmed(self):
        # True only after the Time Sheet 'Confirmer' button moved data to Distribution
        try:
            transfer = self.app.shared_data.get("transfer", {})
            entries = transfer.get("entries", [])
            date = transfer.get("date", "")
            return bool(date) and bool(entries)
        except Exception:
            return False

    def _dist_decl_values_entered(self):
        try:
            dist = self.app.shared_data.get("distribution_tab")
            if dist and hasattr(dist, "inputs_valid"):
                return bool(dist.inputs_valid())
        except Exception:
            pass
        return False

    def _distribuer_selected(self):
        try:
            dist = self.app.shared_data.get("distribution_tab")
            if dist and hasattr(dist, "shift_var"):
                return bool(dist.shift_var.get())
        except Exception:
            pass
        return False

    def _export_done_token(self):
        try:
            return self.app.shared_data.get("last_export_token")
        except Exception:
            return None

    # ---- Compute current progress ----
    def _compute(self):
        completed = 0
        checklist = [
            self._date_entered(),
            self._hours_entered(),
            self._confirmed(),
            self._distribuer_selected(),
            self._dist_decl_values_entered(),
        ]
        for done in checklist:
            if done:
                completed += 1
            else:
                break

        if completed >= len(self.STEPS):
            next_text = "Terminé"
        else:
            next_text = f"Prochaine étape: {self.STEPS[completed]}"

        export_token = self._export_done_token()
        # If export token present and we already satisfied first 5 steps, mark full
        fully_done = completed >= 5 and export_token is not None
        value = len(self.STEPS) if fully_done else completed
        return value, next_text, export_token, fully_done

    # ---- UI updates ----
    def _apply(self, value, next_text):
        try:
            self.pb.configure(value=value)
            self.next_label.configure(text=next_text)
        except Exception:
            pass

    def _tick(self):
        value, next_text, export_token, fully_done = self._compute()

        if fully_done:
            # Lock bar filled and show final message
            try:
                self.pb.configure(mode="determinate", value=len(self.STEPS))
                self.next_label.configure(text="🎉 Distribution terminéee! 🎉")
            except Exception:
                pass
            self._last_export_token = export_token
        else:
            self._apply(value, next_text)

        # Schedule next update
        self.frame.after(700, self._tick)


def _choose_pdf_export_dir(parent):
    """Let the user pick a new PDF export folder and persist it."""
    current = get_pdf_dir()
    initialdir = current if (current and os.path.isdir(current)) else os.path.expanduser("~")
    new_dir = filedialog.askdirectory(parent=parent, initialdir=initialdir, title="Choisir le dossier d’exportation PDF")
    if new_dir:
        try:
            os.makedirs(new_dir, exist_ok=True)
            set_pdf_dir(new_dir)
            messagebox.showinfo("Dossier mis à jour", f"Dossier d’exportation PDF:\n{new_dir}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d’enregistrer le dossier:\n{e}")

def create_menu_bar(root, app):
    # Create themed top-level menu bar (same row as clock)
    menu_bar = ttk.Frame(root, padding=(10, 5))
    try:
        menu_bar.pack(fill=X, side=TOP, before=root.winfo_children()[0])
    except Exception:
        menu_bar.pack(fill=X, side=TOP)

    # ----- Admin -----
    open_button = ttk.Menubutton(menu_bar, text="Admin")
    open_menu = ttk.Menu(open_button, tearoff=0)
    open_menu.add_command(label="Feuille d'employés", command=app.authenticate_and_show_master)
    open_button["menu"] = open_menu
    open_button.pack(side=LEFT, padx=5)

    # ----- Réglages -----
    settings_button = ttk.Menubutton(menu_bar, text="Réglages")
    settings_menu = ttk.Menu(settings_button, tearoff=0)

    # ----- UI scale override -----
    def _adjust_ui_scale(parent):
        current = get_ui_scale()
        initial = current if current > 0 else 1.0
        value = askfloat(
            "Échelle de l'interface",
            "Facteur de mise à l'échelle (0 = auto).\nEx: 1.25 pour 125%",
            parent=parent,
            initialvalue=initial,
            minvalue=0.5,
            maxvalue=4.0,
        )
        if value is not None:
            try:
                set_ui_scale(0.0 if value == 0 else value)
                messagebox.showinfo(
                    "Échelle enregistrée",
                    "Redémarrez l'application pour appliquer la nouvelle échelle.",
                )
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d’enregistrer:\n{e}")

    settings_menu.add_separator()
    settings_menu.add_command(
        label="Paramètres de distribution",
        command=lambda: open_distribution_settings(root, app)
    )
    settings_menu.add_separator()
    settings_menu.add_command(
        label="Paramètres de paie",
        command=lambda: open_payroll_settings_dialog(root, app)
    )
    settings_menu.add_separator()
    settings_menu.add_command(
        label="Calendrier de paie",
        command=lambda: open_pay_calendar_dialog(root, app)
    )
    settings_menu.add_separator()
    settings_menu.add_command(
        label="Ajuster l'échelle de l'interface…",
        command=lambda: _adjust_ui_scale(root),
    )
    settings_menu.add_separator()
    # PDF export root
    settings_menu.add_command(
        label="Modifier le dossier d’exportation PDF…",
        command=lambda: _choose_pdf_export_dir(root)
    )
    settings_menu.add_separator()
    # ---- Auto-update toggle ----
    _auto_updates_var = BooleanVar(value=get_auto_check_updates())

    def _toggle_auto_updates():
        try:
            set_auto_check_updates(_auto_updates_var.get())
        except Exception as e:
            _auto_updates_var.set(get_auto_check_updates())
            messagebox.showerror("Erreur", f"Impossible de sauvegarder le réglage:\n{e}")

    settings_menu.add_checkbutton(
        label="Vérifier automatiquement les mises à jour",
        variable=_auto_updates_var,
        command=_toggle_auto_updates
    )

    settings_button["menu"] = settings_menu
    settings_button.pack(side=LEFT, padx=5)

    # ----- Summary -----
    summary_button = ttk.Menubutton(menu_bar, text="Paye")
    summary_menu = ttk.Menu(summary_button, tearoff=0)

    # These call methods you added in MainApp to lazily create/show the tabs
    summary_menu.add_command(
        label="Confirmer les distributions",
        command=app.show_json_viewer_tab
    )
    summary_menu.add_separator()

    summary_menu.add_command(
        label="Rapport de paye",
        command=app.show_pay_tab
    )
    summary_menu.add_separator()
    
    summary_menu.add_command(
        label="Analyse",
        command=app.show_analyse_tab
    )

    summary_button["menu"] = summary_menu
    summary_button.pack(side=LEFT, padx=5)

    # Progress bar: manager workflow
    try:
        app.manager_progress = ManagerProgress(menu_bar, app)
    except Exception:
        # Never block the UI if progress widget fails
        pass

    # Spacer to push help/clock to the right
    ttk.Label(menu_bar).pack(side=LEFT, expand=True)

    # >>> added: Aide (About + Updater) on the right
    help_button = ttk.Menubutton(menu_bar, text="Aide", bootstyle=SECONDARY)
    help_menu = ttk.Menu(help_button, tearoff=0)
    help_menu.add_command(
        label=f"À propos de {APP_NAME} (v{APP_VERSION})",
        command=lambda: messagebox.showinfo("À propos", f"{APP_NAME} v{APP_VERSION}")
    )
    help_menu.add_separator()
    help_menu.add_command(
        label="Vérifier les mises à jour…",
        command=lambda: check_for_update(root)
    )
    help_button["menu"] = help_menu
    help_button.pack(side=RIGHT, padx=5)

    # Clock (right-aligned; stays at the far right)
    clock_label = ttk.Label(menu_bar, font=("Helvetica", 10))
    clock_label.pack(side=RIGHT, padx=10)

    def update_clock():
        now = datetime.now()
        formatted_time = now.strftime("%A %d %B %Y - %H:%M:%S")
        clock_label.config(text=formatted_time.capitalize())
        clock_label.after(1000, update_clock)

    update_clock()
    return clock_label
