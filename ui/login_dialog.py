import tkinter as tk
from tkinter import messagebox
import threading
from typing import Callable, Optional

import ttkbootstrap as ttk


class LoginDialog(ttk.Window):
    """Reusable themed login dialog for TipSplit and related tools."""

    def __init__(
        self,
        *,
        sign_in_callback: Callable[[str, str], object],
        app_name: str = "TipSplit",
        themename: str = "flatly",
        accent: str = "primary",
        variant: str = "light",
        default_email: str = "",
        remember_default: bool = False,
    ) -> None:
        super().__init__(themename=themename)
        self.title(f"{app_name} Login")
        self._sign_in_callback = sign_in_callback
        self._accent = accent
        self._variant = variant
        self.result: Optional[dict] = None

        self.email_var = tk.StringVar(value=default_email)
        self.password_var = tk.StringVar()
        self.remember_var = tk.BooleanVar(value=remember_default)
        self.status_var = tk.StringVar(value="")

        self._build_ui(app_name)
        self._set_style()
        self._sign_in_thread: Optional[threading.Thread] = None

        self.bind("<Return>", lambda _: self._on_submit())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.resizable(False, False)
        self.place_window_center()
        self.after(0, lambda: self.email_entry.focus_set())

    # ------------------------------------------------------------------
    def _set_style(self) -> None:
        style = ttk.Style()
        style.configure("Login.TLabel", font=("Segoe UI", 10))
        style.configure("Login.Heading.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Login.TCheckbutton", font=("Segoe UI", 10))

    def _build_ui(self, app_name: str) -> None:
        padding = 20
        container = ttk.Frame(self, padding=padding, bootstyle=self._variant)
        container.pack(fill=tk.BOTH, expand=True)

        heading = ttk.Label(
            container,
            text=f"{app_name}",
            style="Login.Heading.TLabel",
            anchor="center",
        )
        heading.pack(pady=(0, 10))

        form = ttk.Frame(container)
        form.pack(fill=tk.BOTH, expand=True)

        email_label = ttk.Label(form, text="Email", style="Login.TLabel")
        email_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.email_entry = ttk.Entry(form, textvariable=self.email_var, width=35)
        self.email_entry.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))

        password_label = ttk.Label(form, text="Password", style="Login.TLabel")
        password_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))

        self.password_entry = ttk.Entry(
            form,
            textvariable=self.password_var,
            show="*",
            width=35,
        )
        self.password_entry.grid(row=3, column=0, sticky=tk.EW, pady=(0, 10))

        remember = ttk.Checkbutton(
            form,
            text="Remember me",
            variable=self.remember_var,
            style="Login.TCheckbutton",
        )
        remember.grid(row=4, column=0, sticky=tk.W)

        form.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(
            container,
            textvariable=self.status_var,
            style="Login.TLabel",
            anchor="center",
        )
        self.status_label.pack(pady=(10, 5))

        buttons = ttk.Frame(container)
        buttons.pack(fill=tk.X, pady=(5, 0))

        self.sign_in_button = ttk.Button(
            buttons,
            text="Sign In",
            bootstyle=f"{self._accent}-solid",
            command=self._on_submit,
        )
        self.sign_in_button.pack(side=tk.RIGHT, padx=(5, 0))

        cancel_button = ttk.Button(
            buttons,
            text="Cancel",
            bootstyle="secondary-outline",
            command=self._on_cancel,
        )
        cancel_button.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    def _on_submit(self) -> None:
        if self._sign_in_thread and self._sign_in_thread.is_alive():
            return
        email = self.email_var.get().strip()
        password = self.password_var.get()
        if not email or not password:
            messagebox.showerror("Missing information", "Please enter email and password.")
            return

        self._set_controls_state(tk.DISABLED)
        self.status_var.set("Signing in…")

        def worker():
            try:
                self._sign_in_callback(email, password)
            except Exception as exc:
                message = str(exc)
                # Use after's args to avoid referencing cleared exception objects
                self.after(0, self._on_failure, message)
            else:
                self.after(0, lambda: self._on_success(email))

        self._sign_in_thread = threading.Thread(target=worker, daemon=True)
        self._sign_in_thread.start()

    def _on_failure(self, message: str) -> None:
        self.status_var.set("")
        self._set_controls_state(tk.NORMAL)
        messagebox.showerror("Login failed", message)

    def _on_success(self, email: str) -> None:
        self.result = {
            "email": email,
            "remember": bool(self.remember_var.get()),
        }
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()

    def _set_controls_state(self, state: str) -> None:
        for widget in (self.email_entry, self.password_entry, self.sign_in_button):
            widget.configure(state=state)
