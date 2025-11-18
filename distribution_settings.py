import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import Toplevel, StringVar, messagebox

from AppConfig import (
    DEFAULT_DISTRIBUTION_SETTINGS,
    get_distribution_settings,
    update_distribution_settings,
    reset_distribution_settings,
)
from icon_helper import set_app_icon

_dialog_instance = None

FIELD_DEFS = [
    {
        "key": "round_increment",
        "label": "Arrondi comptant (cash)",
        "hint": "Plus petite devise pour les paiements en espèces.",
        "options": [0.05, 0.25],
    },
    {
        "key": "cuisine_percentage",
        "label": "% Cuisine sur ventes nourriture",
        "hint": "Pourcentage des ventes nourriture remise à la cuisine. Exemple: 0.01 (1%)",
    },
    {
        "key": "bussboy_percentage",
        "label": "% Bussboys sur ventes nettes",
        "hint": "Fraction des ventes nettes allouée aux bussboys lorsqu'ils sont présents.",
    },
    {
        "key": "frais_admin_service_ratio",
        "label": "Part des frais admin pour le service",
        "hint": "Pourcentage des frais administratifs qui sont remis au service.",
    },
]


def open_distribution_settings(parent, app=None):
    global _dialog_instance
    if _dialog_instance and _dialog_instance.winfo_exists():
        _dialog_instance.lift()
        _dialog_instance.focus_force()
        return
    _dialog_instance = DistributionSettingsDialog(parent, app)


class DistributionSettingsDialog(Toplevel):
    def __init__(self, parent, app=None):
        super().__init__(parent)
        self.app = app
        self.title("Paramètres de distribution")
        self.resizable(False, False)
        try:
            set_app_icon(self)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.vars = {}
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.grid(row=0, column=0, sticky=NSEW)

        for idx, field in enumerate(FIELD_DEFS):
            ttk.Label(container, text=field["label"]).grid(row=idx * 2, column=0, sticky=W)
            var = StringVar()
            if "options" in field:
                values = [f"{opt:.2f}" for opt in field["options"]]
                entry = ttk.Combobox(container, width=16, textvariable=var, values=values, state="readonly")
                entry.grid(row=idx * 2, column=1, sticky=W)
            else:
                entry = ttk.Entry(container, width=18, textvariable=var)
                entry.grid(row=idx * 2, column=1, sticky=W)
            hint = ttk.Label(container, text=field["hint"], bootstyle="secondary")
            hint.grid(row=idx * 2 + 1, column=0, columnspan=2, sticky=W, pady=(0, 8))
            self.vars[field["key"]] = var

        button_row = ttk.Frame(container)
        button_row.grid(row=len(FIELD_DEFS) * 2, column=0, columnspan=2, pady=(10, 0), sticky=E)

        ttk.Button(
            button_row,
            text="Restaurer défauts",
            bootstyle="warning-outline",
            command=self._reset_defaults,
        ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(
            button_row,
            text="Enregistrer",
            bootstyle="success",
            command=self._save,
        ).pack(side=LEFT)

        ttk.Button(
            button_row,
            text="Fermer",
            bootstyle="secondary",
            command=self.destroy,
        ).pack(side=LEFT, padx=(10, 0))

    def _load_values(self):
        settings = get_distribution_settings()
        for field in FIELD_DEFS:
            key = field["key"]
            val = settings.get(key, DEFAULT_DISTRIBUTION_SETTINGS.get(key, 0.0))
            if "options" in field:
                self.vars[key].set(f"{val:.2f}")
            else:
                self.vars[key].set(f"{val:.6g}")

    def _save(self):
        updates = {}
        errors = []
        for field in FIELD_DEFS:
            raw = self.vars[field["key"]].get().strip()
            if not raw:
                errors.append(f"{field['label']}: valeur requise")
                continue
            raw_normalized = raw.replace(",", ".")
            if "options" in field:
                allowed_str = {f"{opt:.2f}" for opt in field["options"]}
                if raw not in allowed_str and raw_normalized not in allowed_str:
                    errors.append(f"{field['label']}: choisir 0.05 ou 0.25")
                    continue
            try:
                value = float(raw_normalized)
            except ValueError:
                errors.append(f"{field['label']}: valeur numérique invalide")
                continue
            if field.get("positive") and value <= 0:
                errors.append(f"{field['label']}: doit être > 0")
                continue
            updates[field["key"]] = value

        if errors:
            messagebox.showerror("Erreurs de validation", "\n".join(errors), parent=self)
            return

        update_distribution_settings(updates)
        messagebox.showinfo("Paramètres enregistrés", "Les paramètres de distribution ont été mis à jour.", parent=self)
        self._notify_distribution_changed()

    def _reset_defaults(self):
        if not messagebox.askyesno(
            "Restaurer les paramètres",
            "Voulez-vous restaurer les paramètres de distribution par défaut ?",
            parent=self,
        ):
            return
        reset_distribution_settings()
        self._load_values()
        self._notify_distribution_changed()

    def destroy(self):
        global _dialog_instance
        _dialog_instance = None
        super().destroy()

    def _notify_distribution_changed(self):
        if not self.app:
            return
        try:
            if hasattr(self.app, "reload_distribution_tab") and callable(self.app.reload_distribution_tab):
                self.app.reload_distribution_tab()
            elif hasattr(self.app, "distribution_tab") and hasattr(self.app.distribution_tab, "process"):
                self.app.distribution_tab.process()
        except Exception:
            pass
