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
        self._password_visible = False
        self._progress_visible = False

        self._set_style()
        self._build_ui(app_name)
        self._sign_in_thread: Optional[threading.Thread] = None

        self.bind("<Return>", lambda _: self._on_submit())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.resizable(False, False)
        self.place_window_center()
        self.after(0, lambda: self.email_entry.focus_set())

    # ------------------------------------------------------------------
    def _set_style(self) -> None:
        style = ttk.Style()
        colors = style.colors

        style.configure("Login.Surface.TFrame", background=colors.bg)
        style.configure("Login.CardWrapper.TFrame", background=colors.bg)
        style.configure("Login.Hero.TFrame", background=colors.primary)
        style.configure("Login.Card.TFrame", background="#ffffff")

        style.configure("Login.TLabel", font=("Segoe UI", 10), background="#ffffff")
        style.configure("Login.Heading.TLabel", font=("Segoe UI", 18, "bold"), background="#ffffff")
        style.configure("Login.Subheading.TLabel", font=("Segoe UI", 10), foreground="#6c757d", background="#ffffff")
        style.configure("Login.Status.TLabel", font=("Segoe UI", 9), foreground="#6c757d", background="#ffffff")
        style.configure("Login.Badge.TLabel", font=("Segoe UI", 9, "bold"), foreground=colors.primary, background="#eaf2fb", padding=(10, 3))
        style.configure("Login.TCheckbutton", font=("Segoe UI", 10), background="#ffffff")

        style.configure("Login.Hero.Heading.TLabel", font=("Segoe UI", 18, "bold"), foreground="#ffffff", background=colors.primary)
        style.configure("Login.Hero.Sub.TLabel", font=("Segoe UI", 10), foreground="#dbe7ff", background=colors.primary)
        style.configure("Login.Hero.Badge.TLabel", font=("Segoe UI", 9, "bold"), foreground=colors.primary, background="#ffffff", padding=(10, 3))

        style.configure("Login.TEntry", font=("Segoe UI", 10), padding=(12, 10))

    def _build_ui(self, app_name: str) -> None:
        container = ttk.Frame(self, padding=0, style="Login.Surface.TFrame")
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        hero = ttk.Frame(container, width=240, style="Login.Hero.TFrame")
        hero.grid(row=0, column=0, sticky="nsew")
        hero.grid_propagate(False)

        hero_inner = ttk.Frame(hero, padding=(30, 36), style="Login.Hero.TFrame")
        hero_inner.pack(fill=tk.BOTH, expand=True)

        hero_badge = ttk.Label(
            hero_inner,
            text="TipSplit Suite",
            style="Login.Hero.Badge.TLabel",
        )
        hero_badge.pack(anchor=tk.W, pady=(0, 18))

        hero_heading = ttk.Label(
            hero_inner,
            text=app_name,
            style="Login.Hero.Heading.TLabel",
            anchor="w",
        )
        hero_heading.pack(anchor=tk.W)

        hero_copy = ttk.Label(
            hero_inner,
            text="Track tips, staffing, and payroll securely with a unified workflow.",
            style="Login.Hero.Sub.TLabel",
            anchor="w",
            justify=tk.LEFT,
            wraplength=200,
        )
        hero_copy.pack(anchor=tk.W, pady=(14, 12))

        hero_highlight = ttk.Label(
            hero_inner,
            text="Role-based access • Audit-ready exports\nResponsive support team",
            style="Login.Hero.Sub.TLabel",
            anchor="w",
            justify=tk.LEFT,
            wraplength=200,
        )
        hero_highlight.pack(anchor=tk.W)

        card_wrapper = ttk.Frame(container, padding=(48, 40, 48, 40), style="Login.CardWrapper.TFrame")
        card_wrapper.grid(row=0, column=1, sticky="nsew")
        card_wrapper.columnconfigure(0, weight=1)
        card_wrapper.rowconfigure(0, weight=1)

        card = ttk.Frame(card_wrapper, padding=(34, 36), style="Login.Card.TFrame")
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        badge = ttk.Label(card, text="Welcome back", style="Login.Badge.TLabel", anchor="w")
        badge.pack(anchor=tk.W)

        heading = ttk.Label(
            card,
            text="Sign in to continue",
            style="Login.Heading.TLabel",
            anchor="w",
        )
        heading.pack(anchor=tk.W, pady=(16, 6))

        subheading = ttk.Label(
            card,
            text="Use your TipSplit credentials to access analytics, payroll, and more.",
            style="Login.Subheading.TLabel",
            anchor="w",
            justify=tk.LEFT,
            wraplength=380,
        )
        subheading.pack(anchor=tk.W, pady=(0, 22))

        form = ttk.Frame(card, style="Login.Card.TFrame")
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(0, weight=1)

        email_label = ttk.Label(form, text="Email address", style="Login.TLabel")
        email_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 6))

        self.email_entry = ttk.Entry(form, textvariable=self.email_var, width=42, style="Login.TEntry")
        self.email_entry.grid(row=1, column=0, sticky=tk.EW, pady=(0, 18))

        password_row = ttk.Frame(form, style="Login.Card.TFrame")
        password_row.grid(row=2, column=0, sticky=tk.EW)

        password_label = ttk.Label(password_row, text="Password", style="Login.TLabel")
        password_label.pack(side=tk.LEFT)

        self.password_toggle = ttk.Button(
            password_row,
            text="Show",
            bootstyle="link",
            command=self._toggle_password,
        )
        self.password_toggle.pack(side=tk.RIGHT)

        self.password_entry = ttk.Entry(
            form,
            textvariable=self.password_var,
            show="*",
            width=42,
            style="Login.TEntry",
        )
        self.password_entry.grid(row=3, column=0, sticky=tk.EW, pady=(0, 18))

        remember = ttk.Checkbutton(
            form,
            text="Remember me on this device",
            variable=self.remember_var,
            style="Login.TCheckbutton",
            bootstyle="round-toggle",
        )
        remember.grid(row=4, column=0, sticky=tk.W)

        self.status_label = ttk.Label(
            card,
            textvariable=self.status_var,
            style="Login.Status.TLabel",
            anchor="w",
        )
        self.status_label.pack(fill=tk.X, pady=(22, 6))

        self.progress = ttk.Progressbar(card, mode="indeterminate", bootstyle=self._accent)

        buttons = ttk.Frame(card, style="Login.Card.TFrame")
        buttons.pack(fill=tk.X, pady=(14, 0))

        self.sign_in_button = ttk.Button(
            buttons,
            text="Sign In",
            bootstyle=f"{self._accent}-solid",
            command=self._on_submit,
            width=14,
        )
        self.sign_in_button.pack(side=tk.RIGHT, padx=(6, 0))

        cancel_button = ttk.Button(
            buttons,
            text="Cancel",
            bootstyle="secondary-outline",
            command=self._on_cancel,
            width=12,
        )
        cancel_button.pack(side=tk.RIGHT)

        support = ttk.Label(
            card,
            text="Having trouble? Contact your administrator.",
            style="Login.Subheading.TLabel",
            anchor="center",
            justify=tk.CENTER,
        )
        support.pack(fill=tk.X, pady=(20, 0))

        self._toggle_progress(False)

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
        self.status_var.set("Authenticating…")
        self._toggle_progress(True)

        def worker():
            try:
                self._sign_in_callback(email, password)
            except Exception as exc:
                message = str(exc)
                self.after(0, self._on_failure, message)
            else:
                self.after(0, lambda: self._on_success(email))

        self._sign_in_thread = threading.Thread(target=worker, daemon=True)
        self._sign_in_thread.start()

    def _on_failure(self, message: str) -> None:
        self.status_var.set("")
        self._set_controls_state(tk.NORMAL)
        self._toggle_progress(False)
        messagebox.showerror("Login failed", message)

    def _on_success(self, email: str) -> None:
        self.result = {
            "email": email,
            "remember": bool(self.remember_var.get()),
        }
        self._toggle_progress(False)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self._toggle_progress(False)
        self.destroy()

    def _set_controls_state(self, state: str) -> None:
        for widget in (
            self.email_entry,
            self.password_entry,
            self.password_toggle,
            self.sign_in_button,
        ):
            widget.configure(state=state)

    def _toggle_password(self) -> None:
        self._password_visible = not self._password_visible
        self.password_entry.configure(show="" if self._password_visible else "*")
        self.password_toggle.configure(text="Hide" if self._password_visible else "Show")

    def _toggle_progress(self, show: bool) -> None:
        if show:
            if not self._progress_visible:
                self.progress.pack(fill=tk.X, pady=(0, 10))
                self.progress.start(10)
                self._progress_visible = True
        else:
            if self._progress_visible:
                self.progress.stop()
                self.progress.pack_forget()
                self._progress_visible = False
