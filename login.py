"""Modal login dialog displayed before the main UI."""

from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox

from AppConfig import (
    get_remember_login_email,
    set_remember_login_email,
)
from auth import (
    AccountStatusError,
    AuthManager,
    AuthenticationError,
    InvalidCredentialsError,
    SupabaseConfigurationError,
    SupabaseSyncError,
)


class LoginDialog:
    """Login modal that blocks until authentication succeeds or is cancelled."""

    MAX_ATTEMPTS = 5

    def __init__(self, parent, auth_manager: AuthManager):
        self.parent = parent
        self.auth_manager = auth_manager
        self.result = None
        self._attempts = 0
        self._offline = False

        self.window = ttk.Toplevel(parent)
        self.window.title("Connexion requise")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Layout
        frame = ttk.Frame(self.window, padding=20)
        frame.grid(column=0, row=0, sticky=(N, S, E, W))
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        ttk.Label(frame, text="Veuillez vous connecter pour continuer", font=("Helvetica", 13, "bold")).grid(
            column=0, row=0, columnspan=2, pady=(0, 10)
        )

        ttk.Label(frame, text="Courriel").grid(column=0, row=1, sticky=W, padx=(0, 10))
        ttk.Label(frame, text="Mot de passe").grid(column=0, row=2, sticky=W, padx=(0, 10))

        self.email_var = tk.StringVar(value=get_remember_login_email())
        self.password_var = tk.StringVar()
        self.remember_var = tk.BooleanVar(value=bool(self.email_var.get()))

        email_entry = ttk.Entry(frame, textvariable=self.email_var, width=32)
        email_entry.grid(column=1, row=1, sticky=(W, E))
        password_entry = ttk.Entry(frame, textvariable=self.password_var, width=32, show="•")
        password_entry.grid(column=1, row=2, sticky=(W, E))

        self.remember_check = ttk.Checkbutton(
            frame,
            text="Se souvenir de moi",
            variable=self.remember_var,
            bootstyle="round-toggle",
        )
        self.remember_check.grid(column=1, row=3, sticky=W, pady=(5, 10))

        self.status_var = tk.StringVar(value="Synchronisation en cours…")
        self.status_label = ttk.Label(frame, textvariable=self.status_var, wraplength=280)
        self.status_label.grid(column=0, row=4, columnspan=2, sticky=W, pady=(0, 10))

        button_frame = ttk.Frame(frame)
        button_frame.grid(column=0, row=5, columnspan=2, sticky=(E, W))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)
        button_frame.columnconfigure(2, weight=0)

        self.retry_button = ttk.Button(
            button_frame,
            text="Rafraîchir",
            command=self._retry_sync,
            bootstyle=SECONDARY,
        )
        self.retry_button.grid(column=0, row=0, sticky=W)

        self.login_button = ttk.Button(
            button_frame,
            text="Se connecter",
            command=self._on_submit,
            bootstyle=SUCCESS,
        )
        self.login_button.grid(column=1, row=0, padx=(10, 0))

        cancel_button = ttk.Button(
            button_frame,
            text="Quitter",
            command=self._on_cancel,
            bootstyle=DANGER,
        )
        cancel_button.grid(column=2, row=0, padx=(10, 0))

        frame.columnconfigure(1, weight=1)

        self.window.bind("<Return>", lambda *_: self._on_submit())
        self.window.bind("<Escape>", lambda *_: self._on_cancel())

        # Center dialog
        self.parent.update_idletasks()
        x = self.parent.winfo_rootx()
        y = self.parent.winfo_rooty()
        w = self.parent.winfo_width()
        h = self.parent.winfo_height()
        self.window.update_idletasks()
        ww = self.window.winfo_reqwidth()
        wh = self.window.winfo_reqheight()
        self.window.geometry(f"{ww}x{wh}+{x + (w - ww) // 2}+{y + (h - wh) // 2}")

        # Attempt initial sync (non-blocking for offline usage)
        self.window.after(100, self._initial_sync)

        email_entry.focus_set()

    # ----------------------------
    def _initial_sync(self):
        try:
            count = self.auth_manager.sync()
            self.status_var.set(f"Liste des accès synchronisée ({count} utilisateurs).")
            self._offline = False
        except SupabaseConfigurationError as exc:
            self._offline = True
            if self.auth_manager.has_cached_users():
                self.status_var.set("Supabase non configuré. Mode hors ligne avec la dernière liste connue.")
            else:
                self.status_var.set("Supabase non configuré. Configurez-le avant de pouvoir vous connecter.")
                self.login_button.configure(state=DISABLED)
        except SupabaseSyncError as exc:
            self._offline = True
            if self.auth_manager.has_cached_users():
                self.status_var.set(f"⚠️ Impossible de joindre Supabase ({exc}). Utilisation hors ligne.")
            else:
                self.status_var.set("Aucune donnée en cache et connexion à Supabase impossible.")
                self.login_button.configure(state=DISABLED)

    def _retry_sync(self):
        try:
            count = self.auth_manager.sync()
            self.status_var.set(f"Synchronisation réussie ({count} utilisateurs).")
            self.login_button.configure(state=NORMAL)
            self._offline = False
        except (SupabaseConfigurationError, SupabaseSyncError) as exc:
            self._offline = True
            self.status_var.set(f"⚠️ Synchronisation impossible: {exc}")

    def _on_submit(self):
        if self.login_button.cget("state") == DISABLED:
            return

        email = self.email_var.get().strip()
        password = self.password_var.get()
        if not email or not password:
            self.status_var.set("Entrez votre courriel et mot de passe.")
            return

        try:
            result = self.auth_manager.authenticate(email, password)
        except AccountStatusError as exc:
            self._attempts += 1
            self.status_var.set("Accès refusé: votre compte est désactivé ou révoqué.")
            messagebox.showerror("Accès bloqué", "Votre accès est désactivé. Contactez l’administrateur.")
            self._check_attempts()
            return
        except InvalidCredentialsError as exc:
            self._attempts += 1
            self.status_var.set(str(exc))
            self._check_attempts()
            return
        except AuthenticationError as exc:
            self._attempts += 1
            self.status_var.set(str(exc))
            self._check_attempts()
            return

        if self.remember_var.get():
            set_remember_login_email(email)
        else:
            set_remember_login_email("")

        self.result = {
            "user": result,
            "offline": self._offline,
            "last_sync": self.auth_manager.last_sync,
        }
        self.window.destroy()

    def _check_attempts(self):
        if self._attempts >= self.MAX_ATTEMPTS:
            self.login_button.configure(state=DISABLED)
            self.status_var.set("Nombre maximal de tentatives atteint. Réessayez plus tard.")

    def _on_cancel(self):
        self.result = None
        self.window.destroy()

