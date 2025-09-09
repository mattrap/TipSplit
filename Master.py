# Master.py — uses AppConfig-backed, writable employee files (portable- & installer-safe)

import json
import os
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from MenuBar import create_menu_bar

from AppConfig import ensure_employee_data_ready, get_employee_files
from ui_scale import scale
from tree_utils import fit_columns


class MasterSheet:
    def __init__(self, frame, on_save_callback=None, shared_data=None):
        # Ensure backend files exist and are writable; returns (service_path, bussboy_path)
        ensure_employee_data_ready()
        self.service_path, self.bussboy_path = get_employee_files()

        self.sort_directions = {}
        self.root = frame

        # --------- Scrollable container ---------
        self.canvas = ttk.Canvas(self.root)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        vsb = ttk.Scrollbar(self.root, orient=VERTICAL, command=self.canvas.yview)
        vsb.pack(side=RIGHT, fill=Y)
        self.canvas.configure(yscrollcommand=vsb.set)

        self.container = ttk.Frame(self.canvas)
        window = self.canvas.create_window((0, 0), window=self.container, anchor="nw")

        # Update scrollregion and width when widgets resize
        self.container.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e, w=window: self.canvas.itemconfigure(w, width=e.width),
        )

        self.unsaved_changes = False
        self.save_button = None
        self.back_button = None
        self.hovered_rows = {}
        self.edit_box = None
        self.on_save_callback = on_save_callback
        self.shared_data = shared_data or {}

        # ---------- STYLE: Treeview row height ----------
        style = ttk.Style()
        style.configure("Treeview", rowheight=scale(25))         # base
        style.configure("primary.Treeview", rowheight=scale(34)) # bootstyle="primary"

        # Header Frame
        header_frame = ttk.Frame(self.container)
        header_frame.pack(fill=X, pady=(10, 0), padx=10)

        ttk.Label(header_frame, text="Feuille d'employé", font=("Helvetica", 16, "bold")).pack(side=LEFT)

        self.button_container = ttk.Frame(header_frame)
        self.button_container.pack(side=RIGHT)

        # Tables
        self.service_tree = self.create_table_section(
            self.container, "Service", self.add_service_row, self.delete_service_row
        )
        self.bussboy_tree = self.create_table_section(
            self.container, "Bussboy", self.add_bussboy_row, self.delete_bussboy_row
        )

        # Initial load
        self.load_data(self.service_tree, self.service_path, key="service")
        self.load_data(self.bussboy_tree, self.bussboy_path, key="bussboy")

    # ---------------------------
    # Column helpers & validation
    # ---------------------------
    @staticmethod
    def _is_int_column(index: int) -> bool:
        # columns: number(0), name(1), points(2), email(3)
        # keep int validation for number and points
        return index in (0, 2)

    @staticmethod
    def _is_int(value: str) -> bool:
        """
        Strict integer check after trimming spaces.
        Accepts optional leading '-' for negatives (remove to allow only positives).
        """
        if value is None:
            return False
        s = str(value).strip()
        if not s:
            return False
        if s.startswith("-"):
            return s[1:].isdigit()
        return s.isdigit()

    # ---------------------------
    # UI construction
    # ---------------------------
    def create_table_section(self, root, title, add_callback, delete_callback):
        frame = ttk.Frame(root)
        frame.pack(pady=(10, 5), fill=X)

        ttk.Label(frame, text=title, font=("Helvetica", 14, "bold")).pack(side=LEFT, padx=(10, 5))
        ttk.Button(frame, text="➕", bootstyle=SUCCESS, width=3, command=add_callback).pack(side=LEFT, padx=2)
        ttk.Button(frame, text="➖", bootstyle=DANGER, width=3, command=delete_callback).pack(side=LEFT, padx=2)

        table_frame = ttk.Frame(root, padding=(10, 5))
        table_frame.pack(fill=BOTH, expand=True)

        # Keep order aligned with stored data: number, name, points, email
        tree = ttk.Treeview(
            table_frame,
            columns=("number", "name", "points", "email"),
            show="headings",
            bootstyle="primary"
        )
        for col in ("number", "name", "points", "email"):
            tree.heading(col, text=col.capitalize(), command=lambda c=col, t=tree: self.sort_column(c, t))
        self._configure_columns(tree)
        tree.pack(side=LEFT, fill=BOTH, expand=True)

        scroll = ttk.Scrollbar(table_frame, orient=VERTICAL, command=tree.yview)
        scroll.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=scroll.set)

        tree.tag_configure("evenrow", background="#f2f2f2")
        tree.tag_configure("oddrow", background="#ffffff")
        tree.tag_configure("highlighted", background="#d0ebff")
        tree.tag_configure("hover", background="#e0f7fa")

        tree.bind("<Double-1>", self.on_double_click)
        tree.bind("<Button-3>", lambda e, t=tree: self.show_context_menu(e, t))
        tree.bind("<<TreeviewSelect>>", lambda e, t=tree: self.highlight_selected(t))
        tree.bind("<Motion>", lambda e, t=tree: self.on_hover(e, t))

        return tree

    def _configure_columns(self, tree):
        num_w = scale(120)
        name_w = scale(240)
        pts_w = scale(100)
        email_w = scale(240)
        width_map = {"number": num_w, "name": name_w, "points": pts_w, "email": email_w}
        tree.column("number", width=num_w, minwidth=scale(20), anchor=CENTER, stretch=True)
        tree.column("name", width=name_w, minwidth=scale(20), anchor=W, stretch=True)
        tree.column("points", width=pts_w, minwidth=scale(20), anchor=CENTER, stretch=True)
        tree.column("email", width=email_w, minwidth=scale(20), anchor=W, stretch=True)
        fit_columns(tree, width_map)

    # ---------------------------
    # Sorting
    # ---------------------------
    def sort_column(self, col, tree):
        self.sort_directions.setdefault(tree, {})
        reverse = self.sort_directions[tree].get(col, False)
        self.sort_directions[tree][col] = not reverse

        data = [(tree.set(k, col), k) for k in tree.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            data.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)

        for index, (_, k) in enumerate(data):
            tree.move(k, '', index)

        arrow = " ↓" if reverse else " ↑"
        for col_name in tree['columns']:
            label = col_name.capitalize()
            if col_name == col:
                label += arrow
            tree.heading(col_name, text=label, command=lambda c=col_name, t=tree: self.sort_column(c, t))

        self.restripe_rows(tree)

    # ---------------------------
    # Row add/delete
    # ---------------------------
    def add_service_row(self):
        self._add_row(self.service_tree)

    def delete_service_row(self):
        self._delete_selected_row(self.service_tree)

    def add_bussboy_row(self):
        self._add_row(self.bussboy_tree)

    def delete_bussboy_row(self):
        self._delete_selected_row(self.bussboy_tree)

    def _add_row(self, tree):
        index = len(tree.get_children())
        tag = "evenrow" if index % 2 == 0 else "oddrow"
        # default empty row matching current columns (number, name, points, email)
        tree.insert("", "end", values=("", "", "", ""), tags=(tag,))
        self.set_unsaved_changes(True)

    def _delete_selected_row(self, tree):
        selected = tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Erreur", "Sélectionnez qu'une seule rangée")
            return
        confirm = messagebox.askyesno("Confirmer la suppression", "Voulez-vous vraiment supprimer cette rangée?")
        if not confirm:
            return
        tree.delete(selected[0])
        self.set_unsaved_changes(True)
        self.restripe_rows(tree)

    def restripe_rows(self, tree):
        for i, item in enumerate(tree.get_children()):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.item(item, tags=(tag,))

    # ---------------------------
    # Inline editing
    # ---------------------------
    def on_double_click(self, event):
        tree = event.widget
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        column_index = int(column.replace("#", "")) - 1
        if not row_id:
            return

        # Cell geometry & current value
        bbox = tree.bbox(row_id, column)
        if not bbox:
            return
        x, y, width, height = bbox
        values = list(tree.item(row_id)["values"])
        # pad to number of columns for safe editing beyond current length (back-compat rows)
        total_cols = len(tree["columns"]) if isinstance(tree["columns"], (list, tuple)) else len(tuple(tree["columns"]))
        if len(values) < total_cols:
            values = values + [""] * (total_cols - len(values))
        original_value = values[column_index] if column_index < len(values) else ""

        # Create editor and keep a local handle + closed flag
        editor = ttk.Entry(tree)
        editor.place(x=x, y=y, width=width, height=height)
        editor.insert(0, str(original_value))
        editor.focus()
        self.edit_box = editor
        closed = False

        def finish_edit(save: bool, new_value=None):
            nonlocal values, closed
            if closed:
                return
            closed = True

            # Save new value if requested
            if save and (new_value is not None):
                # ensure list is long enough (back-compat)
                if column_index >= len(values):
                    values.extend([""] * (column_index + 1 - len(values)))
                if values[column_index] != new_value:
                    values[column_index] = new_value
                    tree.item(row_id, values=values)
                    self.set_unsaved_changes(True)

            try:
                editor.destroy()
            except Exception:
                pass
            if self.edit_box is editor:
                self.edit_box = None

        def cancel_edit(event=None):
            # ESC-like behavior: revert silently
            finish_edit(save=False)

        def save_edit(event=None):
            # Guard if already closed
            if not editor.winfo_exists() or self.edit_box is not editor:
                return

            new_text = editor.get().strip()

            # If this is an int column, invalid input -> behave exactly like ESC (revert silently)
            if self._is_int_column(column_index):
                if not self._is_int(new_text):
                    cancel_edit()
                    return
                new_value = int(new_text)
            else:
                new_value = new_text

            finish_edit(save=True, new_value=new_value)

        # Bindings
        editor.bind("<Return>", save_edit)    # commit
        editor.bind("<FocusOut>", save_edit)  # commit on blur
        editor.bind("<Escape>", cancel_edit)  # revert silently

    # ---------------------------
    # UX niceties
    # ---------------------------
    def show_context_menu(self, event, tree):
        selected = tree.identify_row(event.y)
        if selected:
            tree.selection_set(selected)
            menu = ttk.Menu(tree, tearoff=0)
            menu.add_command(label="Supprimer la rangée", command=lambda: self._delete_selected_row(tree))
            menu.tk_popup(event.x_root, event.y_root)

    def highlight_selected(self, tree):
        for item in tree.get_children():
            tags = list(tree.item(item, "tags"))
            if item in tree.selection():
                if "highlighted" not in tags:
                    tags.append("highlighted")
            else:
                tags = [t for t in tags if t != "highlighted"]
            tree.item(item, tags=tags)

    def on_hover(self, event, tree):
        row_id = tree.identify_row(event.y)
        if tree not in self.hovered_rows:
            self.hovered_rows[tree] = {"row": None, "base_tag": None}
        hovered = self.hovered_rows[tree]["row"]
        base_tag = self.hovered_rows[tree]["base_tag"]
        if hovered and not tree.exists(hovered):
            self.hovered_rows[tree] = {"row": None, "base_tag": None}
            return
        if row_id != hovered:
            if hovered and tree.exists(hovered):
                tree.item(hovered, tags=(base_tag,))
            if row_id and tree.exists(row_id):
                current_tags = tree.item(row_id, "tags")
                base = current_tags[0] if current_tags else "oddrow"
                tree.item(row_id, tags=("hover",))
                self.hovered_rows[tree] = {"row": row_id, "base_tag": base}

    # ---------------------------
    # Persistence (AppConfig paths)
    # ---------------------------
    def save_data(self, tree, filename, key):
        data = [tree.item(item)["values"] for item in tree.get_children()]
        if self.shared_data is not None:
            self.shared_data[key] = data
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder le fichier:\n{filename}\n\n{e}")

    def load_data(self, tree, filename, key=None):
        # Clear table
        tree.delete(*tree.get_children())

        data = []
        try:
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
        except Exception:
            # Treat as empty if corrupt; AppConfig seeding should have handled corruption too
            data = []

        for i, row in enumerate(data):
            # Insert exactly as in file (no coercion)
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.insert("", "end", values=row, tags=(tag,))

        if key is not None and self.shared_data is not None:
            self.shared_data[key] = data

        # Default: sort by points descending on load
        self.sort_directions.setdefault(tree, {})
        self.sort_directions[tree]["points"] = True
        self.sort_column("points", tree)

    def save_all_data(self):
        self.save_data(self.service_tree, self.service_path, key="service")
        self.save_data(self.bussboy_tree, self.bussboy_path, key="bussboy")
        self.set_unsaved_changes(False)
        messagebox.showinfo("Sauvegardé!", "Les changements ont été effectués avec succès")
        if self.on_save_callback:
            self.on_save_callback()

    def discard_changes(self):
        self.load_data(self.service_tree, self.service_path, key="service")
        self.load_data(self.bussboy_tree, self.bussboy_path, key="bussboy")
        self.set_unsaved_changes(False)

    def set_unsaved_changes(self, value: bool):
        self.unsaved_changes = value
        if value and not self.save_button:
            self.back_button = ttk.Button(self.button_container, text="↩️ ANNULER", bootstyle=SECONDARY, command=self.discard_changes)
            self.back_button.pack(side=LEFT, padx=5)
            self.save_button = ttk.Button(self.button_container, text="📅 SAUVEGARDER", bootstyle=INFO, command=self.save_all_data)
            self.save_button.pack(side=LEFT)
        elif not value:
            if self.save_button:
                self.save_button.destroy()
                self.save_button = None
            if self.back_button:
                self.back_button.destroy()
                self.back_button = None


# Run standalone
if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly")
    create_menu_bar(app_root)
    MasterSheet(app_root)
    app_root.mainloop()
