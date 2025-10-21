"""Tkinter desktop application with Supabase-backed sign-in flow."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Optional

from auth_service import AuthError, AuthErrorCode, AuthService
from config import AppConfig, ConfigError, load_config


class LoginWindow(tk.Tk):
    """Login window that authenticates a user against Supabase."""

    def __init__(self, config: AppConfig, auth_service: AuthService) -> None:
        super().__init__()
        self.title(config.app_name)
        self.resizable(False, False)
        self._config = config
        self._auth_service = auth_service
        self.authenticated_user: Optional[Dict[str, str]] = None

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._email_var = tk.StringVar()
        self._password_var = tk.StringVar()
        self._status_var = tk.StringVar()

        self._build_widgets()
        self._center_window()

    def _build_widgets(self) -> None:
        padding = {"padx": 20, "pady": 10}
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Email").grid(row=0, column=0, sticky="w", **padding)
        email_entry = ttk.Entry(frame, textvariable=self._email_var, width=30)
        email_entry.grid(row=1, column=0, sticky="ew", **padding)
        email_entry.focus()

        ttk.Label(frame, text="Password").grid(row=2, column=0, sticky="w", **padding)
        password_entry = ttk.Entry(frame, textvariable=self._password_var, show="*", width=30)
        password_entry.grid(row=3, column=0, sticky="ew", **padding)

        self._login_button = ttk.Button(frame, text="Log in", command=self._handle_login)
        self._login_button.grid(row=4, column=0, sticky="ew", **padding)

        status_label = ttk.Label(frame, textvariable=self._status_var, foreground="red")
        status_label.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 10))

        self.bind("<Return>", lambda _: self._handle_login())

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width() or 320
        height = self.winfo_height() or 220
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_login(self) -> None:
        if self._login_button["state"] == "disabled":
            return

        email = self._email_var.get().strip()
        password = self._password_var.get()
        if not email or not password:
            self._status_var.set("Please enter email and password.")
            return

        self._status_var.set("")
        self._login_button.config(state="disabled")
        print("[UI] Login button pressed for", email)

        thread = threading.Thread(target=self._perform_login, args=(email, password), daemon=True)
        thread.start()

    def _perform_login(self, email: str, password: str) -> None:
        try:
            user, _session = self._auth_service.sign_in(email, password)
            profile = self._auth_service.select_own_profile(user_id=user["id"])
        except AuthError as exc:
            print("[UI] Login failed:", exc)
            if exc.code in {AuthErrorCode.ACCOUNT_DISABLED, AuthErrorCode.PROFILE_MISSING}:
                message = "Your account is disabled. Contact the owner."
            elif exc.code == AuthErrorCode.INVALID_CREDENTIALS:
                message = "Invalid email or password."
            elif exc.code == AuthErrorCode.NETWORK:
                message = "Can't reach the server. Check your connection and try again."
            else:
                message = "Can't reach the server. Check your connection and try again."
            self.after(0, self._on_login_failed, message)
            return
        except Exception as exc:  # noqa: BLE001 - fallback error mapping
            print("[UI] Unexpected error during login:", exc)
            self.after(0, self._on_login_failed, "Can't reach the server. Check your connection and try again.")
            return

        if not profile:
            print("[UI] Profile missing after successful login for", email)
            self.after(0, self._on_login_failed, "Your account is disabled. Contact the owner.")
            return

        print("[UI] Login successful for", email)
        self.authenticated_user = {"email": email, "id": user["id"]}
        self.after(0, self._on_login_success)

    def _on_login_failed(self, message: str) -> None:
        self._status_var.set(message)
        self._login_button.config(state="normal")

    def _on_login_success(self) -> None:
        self.destroy()

    def _on_close(self) -> None:
        self.authenticated_user = None
        self.destroy()


class MainAppWindow(tk.Tk):
    """Main application window displayed after successful login."""

    def __init__(self, config: AppConfig, auth_service: AuthService, user: Dict[str, str]) -> None:
        super().__init__()
        self.title(config.app_name)
        self._config = config
        self._auth_service = auth_service
        self._user = user
        self.should_relogin = False

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._status_var = tk.StringVar()

        self._build_widgets()
        self._center_window()

    def _build_widgets(self) -> None:
        padding = {"padx": 20, "pady": 10}
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, sticky="nsew")

        welcome = ttk.Label(frame, text=f"Welcome, {self._user['email']}")
        welcome.grid(row=0, column=0, sticky="w", **padding)

        check_button = ttk.Button(frame, text="Check Profile", command=self._handle_check_profile)
        check_button.grid(row=1, column=0, sticky="ew", **padding)

        logout_button = ttk.Button(frame, text="Logout", command=self._handle_logout)
        logout_button.grid(row=2, column=0, sticky="ew", **padding)

        status_label = ttk.Label(frame, textvariable=self._status_var, foreground="red")
        status_label.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 10))

        self.bind_all("<Command-q>", lambda _: self._handle_logout())
        self.bind_all("<Control-q>", lambda _: self._handle_logout())

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width() or 360
        height = self.winfo_height() or 200
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _handle_check_profile(self) -> None:
        self._status_var.set("Checking session...")
        thread = threading.Thread(target=self._perform_profile_check, daemon=True)
        thread.start()

    def _perform_profile_check(self) -> None:
        try:
            user = self._auth_service.get_user()
            if not user:
                raise AuthError("Session expired", AuthErrorCode.INVALID_CREDENTIALS)
            profile = self._auth_service.select_own_profile(user_id=user["id"])
            if not profile:
                raise AuthError(
                    "Your account is disabled. Contact the owner.", AuthErrorCode.ACCOUNT_DISABLED
                )
        except AuthError as exc:
            print("[UI] Profile check failed:", exc)
            if exc.code in {AuthErrorCode.ACCOUNT_DISABLED, AuthErrorCode.PROFILE_MISSING}:
                message = "Your account is disabled. Contact the owner."
                self.after(0, self._force_logout, message)
                return
            if exc.code == AuthErrorCode.INVALID_CREDENTIALS:
                message = "Session expired. Please log in again."
                self.after(0, self._force_logout, message)
                return
            message = "Can't reach the server. Check your connection and try again."
            self.after(0, self._update_status, message)
            return
        except Exception as exc:  # noqa: BLE001
            print("[UI] Unexpected error during profile check:", exc)
            self.after(0, self._update_status, "Can't reach the server. Check your connection and try again.")
            return

        self.after(0, self._update_status, "Session active.")

    def _update_status(self, message: str) -> None:
        self._status_var.set(message)

    def _handle_logout(self) -> None:
        print("[UI] Logout requested")
        self.should_relogin = True
        self._auth_service.sign_out()
        self.destroy()

    def _force_logout(self, message: str) -> None:
        print("[UI] Force logout triggered")
        self.should_relogin = True
        self._auth_service.sign_out()
        self._status_var.set(message)
        messagebox.showwarning("TipSplit", message)
        self.destroy()

    def _on_close(self) -> None:
        print("[UI] Main window closing")
        self._auth_service.sign_out()
        self.destroy()


def run_application() -> None:
    print("[App] Starting TipSplit desktop client")
    try:
        config = load_config()
    except ConfigError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Configuration error", str(exc))
        root.destroy()
        sys.exit(1)

    auth_service = AuthService(config.supabase_url, config.supabase_anon_key)

    while True:
        login_window = LoginWindow(config, auth_service)
        login_window.mainloop()

        if login_window.authenticated_user is None:
            print("[App] Login window closed without authentication. Exiting.")
            break

        main_window = MainAppWindow(config, auth_service, login_window.authenticated_user)
        main_window.mainloop()

        if not main_window.should_relogin:
            print("[App] Main window closed without logout. Exiting.")
            break

    auth_service.close()
    print("[App] Application shutdown complete")


if __name__ == "__main__":
    run_application()
