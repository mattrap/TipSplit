import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from MenuBar import create_menu_bar
import json
import os

DATA_FILE_SERVICE = "service_employees.json"
DATA_FILE_BUSSBOY = "bussboy_employees.json"

class MasterSheet:
    def __init__(self, frame, on_save_callback=None, shared_data=None):
        self.sort_directions = {}
        self.root = frame
        self.unsaved_changes = False
        self.save_button = None
        self.back_button = None
        self.hovered_rows = {}
        self.edit_box = None
        self.on_save_callback = on_save_callback
        self.shared_data = shared_data or {}

        # Header Frame
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=X, pady=(10, 0), padx=10)

        ttk.Label(header_frame, text="Feuille d'employé", font=("Helvetica", 16, "bold")).pack(side=LEFT)

        self.button_container = ttk.Frame(header_frame)
        self.button_container.pack(side=RIGHT)

        self.service_tree = self.create_table_section(self.root, "Service", self.add_service_row, self.delete_service_row)
        self.bussboy_tree = self.create_table_section(self.root, "Bussboy", self.add_bussboy_row, self.delete_bussboy_row)

        self.load_data(self.service_tree, DATA_FILE_SERVICE, key="service")
        self.load_data(self.bussboy_tree, DATA_FILE_BUSSBOY, key="bussboy")

    def create_table_section(self, root, title, add_callback, delete_callback):
        frame = ttk.Frame(root)
        frame.pack(pady=(10, 5), fill=X)

        ttk.Label(frame, text=title, font=("Helvetica", 14, "bold")).pack(side=LEFT, padx=(10, 5))
        ttk.Button(frame, text="➕", bootstyle=SUCCESS, width=3, command=add_callback).pack(side=LEFT, padx=2)
        ttk.Button(frame, text="➖", bootstyle=DANGER, width=3, command=delete_callback).pack(side=LEFT, padx=2)

        table_frame = ttk.Frame(root, padding=(10, 5))
        table_frame.pack(fill=BOTH, expand=True)

        tree = ttk.Treeview(table_frame, columns=("number", "name", "points"), show="headings", bootstyle="primary")
        for col in ("number", "name", "points"):
            tree.heading(col, text=col.capitalize(), command=lambda c=col, t=tree: self.sort_column(c, t))
        self._configure_columns(tree)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        ttk.Scrollbar(table_frame, orient=VERTICAL, command=tree.yview).pack(side=RIGHT, fill=Y)

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
        tree.column("number", width=100, anchor=CENTER)
        tree.column("name", width=200, anchor=W)
        tree.column("points", width=100, anchor=CENTER)

    def sort_column(self, col, tree):
        self.sort_directions.setdefault(tree, {})
        reverse = self.sort_directions[tree].get(col, False)
        self.sort_directions[tree][col] = not reverse

        data = [(tree.set(k, col), k) for k in tree.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            data.sort(key=lambda t: t[0].lower(), reverse=reverse)

        for index, (_, k) in enumerate(data):
            tree.move(k, '', index)

        arrow = " ↓" if reverse else " ↑"
        for col_name in tree['columns']:
            label = col_name.capitalize()
            if col_name == col:
                label += arrow
            tree.heading(col_name, text=label, command=lambda c=col_name, t=tree: self.sort_column(c, t))

        for i, item in enumerate(tree.get_children()):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.item(item, tags=(tag,))

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
        tree.insert("", "end", values=("", "", ""), tags=(tag,))
        self.set_unsaved_changes(True)

    def _delete_selected_row(self, tree):
        selected = tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Select One Row", "Please select exactly one row to delete.")
            return
        confirm = messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected row?")
        if not confirm:
            return
        tree.delete(selected[0])
        self.set_unsaved_changes(True)
        self.restripe_rows(tree)

    def restripe_rows(self, tree):
        for i, item in enumerate(tree.get_children()):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.item(item, tags=(tag,))

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
        x, y, width, height = tree.bbox(row_id, column)
        value = tree.item(row_id)["values"][column_index]
        self.edit_box = ttk.Entry(tree)
        self.edit_box.place(x=x, y=y, width=width, height=height)
        self.edit_box.insert(0, value)
        self.edit_box.focus()

        def save_edit(event=None):
            new_value = self.edit_box.get()
            values = list(tree.item(row_id, "values"))
            if column_index < len(values) and values[column_index] != new_value:
                values[column_index] = new_value
                tree.item(row_id, values=values)
                self.set_unsaved_changes(True)
            self.edit_box.destroy()
            self.edit_box = None

        self.edit_box.bind("<Return>", save_edit)
        self.edit_box.bind("<FocusOut>", save_edit)

    def show_context_menu(self, event, tree):
        selected = tree.identify_row(event.y)
        if selected:
            tree.selection_set(selected)
            menu = ttk.Menu(tree, tearoff=0)
            menu.add_command(label="Delete Row", command=lambda: self._delete_selected_row(tree))
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

    def save_data(self, tree, filename, key):
        data = [tree.item(item)["values"] for item in tree.get_children()]
        if self.shared_data is not None:
            self.shared_data[key] = data
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    def load_data(self, tree, filename, key=None):
        tree.delete(*tree.get_children())
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
                for i, row in enumerate(data):
                    tag = "evenrow" if i % 2 == 0 else "oddrow"
                    tree.insert("", "end", values=row, tags=(tag,))
            if key:
                self.shared_data[key] = data
        self.sort_directions.setdefault(tree, {})
        self.sort_directions[tree]["points"] = True
        self.sort_column("points", tree)

    def save_all_data(self):
        self.save_data(self.service_tree, DATA_FILE_SERVICE, key="service")
        self.save_data(self.bussboy_tree, DATA_FILE_BUSSBOY, key="bussboy")
        self.set_unsaved_changes(False)
        messagebox.showinfo("Saved", "All changes have been saved successfully.")
        if self.on_save_callback:
            self.on_save_callback()

    def discard_changes(self):
        self.load_data(self.service_tree, DATA_FILE_SERVICE, key="service")
        self.load_data(self.bussboy_tree, DATA_FILE_BUSSBOY, key="bussboy")
        self.set_unsaved_changes(False)

    def set_unsaved_changes(self, value: bool):
        self.unsaved_changes = value
        if value and not self.save_button:
            self.back_button = ttk.Button(self.button_container, text="↩️ Back", bootstyle=SECONDARY, command=self.discard_changes)
            self.back_button.pack(side=LEFT, padx=5)
            self.save_button = ttk.Button(self.button_container, text="📅 Save", bootstyle=INFO, command=self.save_all_data)
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
    clock_label = create_menu_bar(app_root)
    MasterSheet(app_root)
    app_root.mainloop()
