import os
import platform
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from datetime import datetime

# Config helpers
from AppConfig import (
    get_pdf_dir, set_pdf_dir, ensure_pdf_dir_selected,
    get_backend_dir, set_backend_dir
)

def _open_path_cross_platform(path: str):
    """Open a folder/file with the OS default file manager."""
    if not path:
        messagebox.showwarning("Chemin manquant", "Aucun chemin spécifié.")
        return
    if not os.path.exists(path):
        messagebox.showwarning("Introuvable", f"Le chemin n’existe pas :\n{path}")
        return
    try:
        sysname = platform.system().lower()
        if sysname == "windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sysname == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible d’ouvrir:\n{path}\n\n{e}")

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

def _choose_backend_dir(parent):
    """Let the user pick a new backend folder for JSON (internal) and persist it."""
    current = get_backend_dir()
    initialdir = current if (current and os.path.isdir(current)) else os.path.expanduser("~")
    new_dir = filedialog.askdirectory(parent=parent, initialdir=initialdir, title="Choisir le dossier backend (JSON)")
    if new_dir:
        try:
            os.makedirs(new_dir, exist_ok=True)
            set_backend_dir(new_dir)
            messagebox.showinfo("Dossier backend mis à jour", f"Nouveau dossier backend:\n{new_dir}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d’enregistrer le dossier backend:\n{e}")

def create_menu_bar(root, app):
    # Create themed top-level menu bar (same row as clock)
    menu_bar = ttk.Frame(root, padding=(10, 5))
    try:
        menu_bar.pack(fill=X, side=TOP, before=root.winfo_children()[0])
    except Exception:
        menu_bar.pack(fill=X, side=TOP)

    # ----- Ouvrir -----
    open_button = ttk.Menubutton(menu_bar, text="Ouvrir")
    open_menu = ttk.Menu(open_button, tearoff=0)
    open_menu.add_command(label="Feuille d'employés", command=app.authenticate_and_show_master)
    open_menu.add_command(label="Modification de distribution", command=app.show_json_viewer_tab)
    open_button["menu"] = open_menu
    open_button.pack(side=LEFT, padx=5)

    # ----- Réglages -----
    settings_button = ttk.Menubutton(menu_bar, text="Réglages")
    settings_menu = ttk.Menu(settings_button, tearoff=0)

    # PDF export root
    settings_menu.add_command(
        label="Dossier d’exportation PDF…",
        command=lambda: _choose_pdf_export_dir(root)
    )
    settings_menu.add_command(
        label="Ouvrir le dossier d’exportation PDF",
        command=lambda: (
            _open_path_cross_platform(get_pdf_dir())
            if get_pdf_dir() else messagebox.showwarning(
                "Dossier manquant",
                "Aucun dossier PDF défini. Configurez-le via Réglages → Dossier d’exportation PDF…"
            )
        )
    )

    settings_menu.add_separator()

    # Backend (JSON) root
    settings_menu.add_command(
        label="Dossier backend (JSON)…",
        command=lambda: _choose_backend_dir(root)
    )
    settings_menu.add_command(
        label="Ouvrir le dossier backend",
        command=lambda: _open_path_cross_platform(get_backend_dir())
    )

    # Optional helper to force-prompt for PDF root on demand
    settings_menu.add_separator()
    settings_menu.add_command(
        label="Vérifier/Configurer le dossier PDF maintenant",
        command=lambda: ensure_pdf_dir_selected(root)
    )

    settings_button["menu"] = settings_menu
    settings_button.pack(side=LEFT, padx=5)

    # ----- Summary (placeholder) -----
    summary_button = ttk.Menubutton(menu_bar, text="Summary")
    summary_menu = ttk.Menu(summary_button, tearoff=0)
    summary_menu.add_command(label="View Summary", command=lambda: None)
    summary_button["menu"] = summary_menu
    summary_button.pack(side=LEFT, padx=5)

    # Spacer
    ttk.Label(menu_bar).pack(side=LEFT, expand=True)

    # Clock (right-aligned)
    clock_label = ttk.Label(menu_bar, font=("Helvetica", 10))
    clock_label.pack(side=RIGHT, padx=10)

    def update_clock():
        now = datetime.now()
        formatted_time = now.strftime("%A %d %B %Y - %H:%M:%S")
        clock_label.config(text=formatted_time.capitalize())
        clock_label.after(1000, update_clock)

    update_clock()
    return clock_label
