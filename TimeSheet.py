# TimeSheet.py — uses AppConfig-backed, writable employee files

import json
import os
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry, Spinbox
from MenuBar import create_menu_bar
from PunchClock import PunchClockPopup
from tkinter import END

from debug_log import log_debug

# Use the centralized AppConfig helpers so paths work on all machines
from AppConfig import ensure_employee_data_ready
from ui_scale import scale


class TimeSheet:
    def __init__(self, root, shared_data=None, reload_distribution_data=None):
        # Ensure backend employee files exist and resolve their paths
        self.service_file, self.bussboy_file = ensure_employee_data_ready()

        self.shared_data = shared_data or {}
        self.reload_distribution_data = reload_distribution_data
        self.root = root
        self.service_total_row = None
        self.bussboy_total_row = None
        self.punch_data = {}
        self.hovered_row = None
        self.sort_directions = {}

        # Temporary points overrides + editor state
        self.temp_points_overrides = {}   # row_id -> int
        self.points_editor = None         # Spinbox widget
        self.points_editor_row = None     # row currently being edited
        self.original_points = {}         # row_id -> standard points

        content = ttk.Frame(self.root, padding=10)
        content.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(content)
        header_frame.pack(fill=X, pady=(0, 10))

        self.create_date_picker(header_frame)
        self.create_confirm_button(header_frame)

        self.status_label = ttk.Label(header_frame, text="", font=("Helvetica", 14))
        self.status_label.pack(side=LEFT, padx=10)

        # --- Taller rows style ---
        style = ttk.Style()
        style.configure("Custom.Treeview", font=("Helvetica", 14), rowheight=scale(35))
        style.configure("Custom.Treeview.Heading", font=("Helvetica", 14, "bold"))
        # -------------------------

        # Treeview + scrollbar
        tree_frame = ttk.Frame(content)
        tree_frame.pack(fill=BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("number", "name", "points", "punch", "in", "out", "total"),
            show="headings",
            bootstyle="primary",
            style="Custom.Treeview",
            selectmode="none",
        )

        scroll = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill=Y)

        self.base_labels = {
            "number": "Numéro",
            "name": "Nom",
            "points": "Points",
            "punch": "🕒",
            "in": "Entrée",
            "out": "Sortie",
            "total": "Total",
        }

        for col, label in self.base_labels.items():
            if col in ["number", "name", "points"]:
                self.tree.heading(col, text=label, command=lambda _col=col: self.sort_by_column(self.tree, _col))
            else:
                self.tree.heading(col, text=label)

        self.tree.column("number", width=scale(100), anchor=CENTER)
        self.tree.column("name", width=scale(200), anchor=W)
        self.tree.column("points", width=scale(100), anchor=CENTER)
        self.tree.column("punch", width=scale(50), anchor=CENTER)
        self.tree.column("in", width=scale(80), anchor=CENTER)
        self.tree.column("out", width=scale(80), anchor=CENTER)
        self.tree.column("total", width=scale(80), anchor=CENTER)

        self.tree.tag_configure("section", font=("Helvetica", 16, "bold"), background="#b4c7af")
        self.tree.tag_configure("hover", background="#e0f7fa")
        self.tree.tag_configure("total", font=("Helvetica", 14, "bold"), background="#e8f5e9")
        self.tree.tag_configure("filled", background="#d8eff0")
        self.tree.tag_configure("points_edited", background="#fff3cd")  # soft yellow for temp points edits

        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Motion>", self.on_hover)
        self.tree.bind("<Configure>", lambda e: self._end_points_edit(commit=True))
        self.tree.bind("<Button-4>", lambda e: self._end_points_edit(commit=True))  # some Linux
        self.tree.bind("<Button-5>", lambda e: self._end_points_edit(commit=True))

        # Footer with centered reset button
        footer_frame = ttk.Frame(content)
        footer_frame.pack(fill=X, pady=(10, 0))
        footer_frame.columnconfigure(0, weight=1)  # center the single column
        reset_btn = ttk.Button(
            footer_frame,
            text="Réinitialiser heures et points",
            bootstyle="danger-outline",
            command=self.reset_hours_and_points
        )
        reset_btn.grid(row=0, column=0, pady=6)  # centered by default (no sticky)

        self.reload()

    def create_date_picker(self, parent):
        ttk.Label(parent, text="Remplir les heures du:", font=("Helvetica", 16, "bold")).pack(side=LEFT)
        self.date_picker = DateEntry(parent, bootstyle="primary", dateformat="%d-%m-%Y", width=20)
        self.date_picker.entry.bind("<Key>", lambda e: "break")  # block manual typing
        self.date_picker.pack(side=LEFT, padx=(10, 0))
        self.date_picker.entry.delete(0, END)

    def create_confirm_button(self, parent):
        confirm_btn = ttk.Button(
            parent,
            text="Confirmer",
            bootstyle="success-outline",
            command=self.export_filled_rows
        )
        confirm_btn.pack(side=RIGHT)

    # ---------- Data loading ----------
    def _load_data_file(self, path):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            # Corrupt or unreadable; treat as empty so UI still loads
            pass
        return []

    def reload(self):
        self._end_points_edit(commit=False)
        self.tree.delete(*self.tree.get_children())
        self.service_total_row = None
        self.bussboy_total_row = None
        self.punch_data.clear()
        self.temp_points_overrides.clear()
        self.original_points.clear()
        self.hovered_row = None

        # Use backend-aware files
        service_data = self._load_data_file(self.service_file)
        if service_data:
            self.tree.insert("", "end", values=("", "--- Service ---", "", "", "", "", ""), tags=("section",))
            for row in service_data:
                number = row[0] if len(row) > 0 else ""
                name   = row[1] if len(row) > 1 else ""
                points = row[2] if len(row) > 2 else 0
                row_id = self.tree.insert("", "end", values=(number, name, points, "🕒", "", "", ""), tags=("editable",))
                self.punch_data[row_id] = {"in": "", "out": "", "total": 0.0}
                try:
                    self.original_points[row_id] = int(points)
                except Exception:
                    self.original_points[row_id] = 0
            self.service_total_row = self.tree.insert("", "end", values=("", "Total Service", "", "", "", "", "0.00"), tags=("total",))

        bussboy_data = self._load_data_file(self.bussboy_file)
        if bussboy_data:
            self.tree.insert("", "end", values=("", "--- Bussboy ---", "", "", "", "", ""), tags=("section",))
            for row in bussboy_data:
                number = row[0] if len(row) > 0 else ""
                name   = row[1] if len(row) > 1 else ""
                points = row[2] if len(row) > 2 else 0
                row_id = self.tree.insert("", "end", values=(number, name, points, "🕒", "", "", ""), tags=("editable",))
                self.punch_data[row_id] = {"in": "", "out": "", "total": 0.0}
                try:
                    self.original_points[row_id] = int(points)
                except Exception:
                    self.original_points[row_id] = 0
            self.bussboy_total_row = self.tree.insert("", "end", values=("", "Total Bussboy", "", "", "", "", "0.00"), tags=("total",))

        self.update_totals()

    def update_totals(self):
        service_total = 0.0
        bussboy_total = 0.0
        in_bussboy = False
        for item in self.tree.get_children():
            tags = self.tree.item(item, "tags")
            if "section" in tags:
                in_bussboy = "Bussboy" in self.tree.item(item, "values")[1]
                continue
            if "total" in tags or "editable" not in tags:
                continue
            total = self.punch_data.get(item, {}).get("total", 0)
            try:
                total = float(total)
            except ValueError:
                total = 0.0
            if in_bussboy:
                bussboy_total += total
            else:
                service_total += total
        if self.service_total_row:
            self.tree.item(self.service_total_row, values=("", "Total Service", "", "", "", "", f"{service_total:.2f}"))
        if self.bussboy_total_row:
            self.tree.item(self.bussboy_total_row, values=("", "Total Bussboy", "", "", "", "", f"{bussboy_total:.2f}"))

    def export_filled_rows(self):
        log_debug("TimeSheet: export_filled_rows invoked")
        try:
            self._end_points_edit(commit=True)

            export_data = []
            current_section = None
            date_str = self.date_picker.entry.get().strip()

            log_debug(f"TimeSheet: Starting export for date: {date_str}")

            if not date_str:
                log_debug("TimeSheet: No date selected; aborting export")
                self.flash_date_field()
                self.status_label.config(text="⛔ Veuillez choisir une date!", foreground="#B22222")
                self.fade_out_status_label()
                return

            try:
                datetime.strptime(date_str, self.date_picker.dateformat)
            except ValueError:
                log_debug("TimeSheet: Invalid date format; aborting export")
                self.flash_date_field()
                self.status_label.config(text="⛔ Format de date invalide!", foreground="#B22222")
                self.fade_out_status_label()
                return

            for item in self.tree.get_children():
                tags = self.tree.item(item, "tags")
                values = self.tree.item(item, "values")

                if "section" in tags:
                    section_label = values[1].strip("- ").strip()
                    current_section = section_label
                    log_debug(f"TimeSheet: Found section: {current_section}")
                    continue

                if "editable" not in tags:
                    continue

                punch = self.punch_data.get(item, {})
                try:
                    total = float(punch.get("total", 0))
                except ValueError:
                    total = 0

                if total > 0:
                    entry = {
                        "section": current_section,
                        "number": values[0],
                        "name": values[1],
                        "points": values[2],  # uses edited value if present
                        "in": punch.get("in", ""),
                        "out": punch.get("out", ""),
                        "hours": f"{total:.2f}"
                    }
                    export_data.append(entry)
                    log_debug(f"TimeSheet: Adding entry: {entry}")

            log_debug(f"TimeSheet: Total entries to export: {len(export_data)}")
            if not export_data:
                log_debug("TimeSheet: No rows with recorded hours found")

            self.shared_data.setdefault("transfer", {})
            self.shared_data["transfer"]["date"] = date_str
            self.shared_data["transfer"]["entries"] = export_data

            log_debug(f"TimeSheet: Data stored in shared_data: {self.shared_data['transfer']}")

            self.status_label.config(
                text="✅ Les Heures ont été enregistrées et transférées à l'onglet Distribution",
                foreground="#228B22")
            self.fade_out_status_label()

            if callable(self.reload_distribution_data):
                try:
                    log_debug("TimeSheet: Calling reload_distribution_data")
                    self.reload_distribution_data()
                except Exception as e:
                    log_debug(f"TimeSheet: reload_distribution_data failed: {e}")
            else:
                log_debug("TimeSheet: reload_distribution_data is None")

            if "distribution_tab" in self.shared_data:
                dist_tab = self.shared_data["distribution_tab"]
                if hasattr(dist_tab, "update_pay_period_display"):
                    log_debug("TimeSheet: Calling update_pay_period_display")
                    dist_tab.update_pay_period_display()
                else:
                    log_debug("TimeSheet: distribution_tab has no update_pay_period_display method")
            else:
                log_debug("TimeSheet: distribution_tab not found in shared_data")
        except Exception as e:
            log_debug(f"TimeSheet: Unexpected error during export_filled_rows: {e}")
            self.status_label.config(text="⛔ Erreur inattendue - voir TipSplit_debug.log", foreground="#B22222")
            self.fade_out_status_label()

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            self._end_points_edit(commit=True)
            return

        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        col_index = int(col.replace("#", "")) - 1

        if not row_id or "editable" not in self.tree.item(row_id, "tags"):
            self._end_points_edit(commit=True)
            return

        # Points column clicked -> begin inline edit
        if col_index == 2:  # "points"
            self._begin_points_edit(row_id)
            return

        # Clock column
        if col_index == 3:  # 🕒 clicked
            self._end_points_edit(commit=True)
            PunchClockPopup(self.tree, row_id, self.on_clock_saved)
            return

        self._end_points_edit(commit=True)

    def on_clock_saved(self, row_id, punch_in, punch_out, total):
        current = list(self.tree.item(row_id, "values"))
        current[4] = punch_in
        current[5] = punch_out

        try:
            total_float = float(total)
            current[6] = f"{total_float:.2f}"
        except (ValueError, TypeError):
            total_float = 0.0
            current[6] = ""

        self.tree.item(row_id, values=current)
        self.punch_data[row_id] = {
            "in": punch_in,
            "out": punch_out,
            "total": total_float
        }

        tags = list(self.tree.item(row_id, "tags"))
        if total_float > 0 and "filled" not in tags:
            tags.append("filled")
        elif total_float == 0 and "filled" in tags:
            tags.remove("filled")
        self.tree.item(row_id, tags=tuple(tags))

        self.update_totals()

    def on_hover(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id == self.hovered_row or not row_id:
            return
        if "editable" not in self.tree.item(row_id, "tags"):
            return

        if self.hovered_row and self.tree.exists(self.hovered_row):
            prev_tags = [tag for tag in self.tree.item(self.hovered_row, "tags") if tag != "hover"]
            self.tree.item(self.hovered_row, tags=tuple(prev_tags))

        if self.tree.exists(row_id):
            tags = list(self.tree.item(row_id, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tree.item(row_id, tags=tuple(tags))

        self.hovered_row = row_id

    def sort_by_column(self, tree, col):
        self._end_points_edit(commit=True)

        direction = self.sort_directions.get(col, False)
        self.sort_directions[col] = not direction

        def get_val(item):
            val = tree.set(item, col)
            try:
                return float(val)
            except ValueError:
                return str(val).lower()

        sections = []
        current_section = []

        for item in tree.get_children():
            tags = self.tree.item(item, "tags")
            if "section" in tags:
                if current_section:
                    sections.append(current_section)
                current_section = [item]
            elif "total" in tags:
                current_section.append(item)
                sections.append(current_section)
                current_section = []
            else:
                current_section.append(item)
        if current_section:
            sections.append(current_section)

        for section in sections:
            editable_rows = [i for i in section if "editable" in tree.item(i, "tags")]
            sorted_items = sorted(editable_rows, key=get_val, reverse=direction)
            insert_after = section[0]
            for item in sorted_items:
                tree.move(item, '', tree.index(insert_after) + 1)
                insert_after = item

        for c, base_label in self.base_labels.items():
            if c == col:
                arrow = "▲" if not direction else "▼"
                tree.heading(c, text=f"{base_label} {arrow}", command=lambda _col=c: self.sort_by_column(tree, _col))
            elif c in ["number", "name", "points"]:
                tree.heading(c, text=base_label, command=lambda _col=c: self.sort_by_column(tree, _col))
            else:
                tree.heading(c, text=base_label)

    def flash_date_field(self):
        entry = self.date_picker.entry
        original_style = entry.cget("style")

        def flash(count=0):
            if count >= 8:
                entry.configure(style=original_style)
                return
            entry.configure(style="danger.TEntry" if count % 2 == 0 else "TEntry")
            entry.after(150, lambda: flash(count + 1))

        flash()

    def fade_out_status_label(self, delay=1500, steps=7):
        def rgb_to_hex(r, g, b):
            return f"#{r:02x}{g:02x}{b:02x}"

        try:
            fg_color = self.status_label.cget("foreground")
            original_rgb = tuple(c // 256 for c in self.status_label.winfo_rgb(fg_color))
        except:
            original_rgb = (0, 0, 0)

        try:
            bg_color = self.status_label.cget("background")
            target_rgb = tuple(c // 256 for c in self.status_label.winfo_rgb(bg_color))
        except:
            target_rgb = (255, 255, 255)

        def step_fade(step=0):
            if step >= steps:
                self.status_label.config(text="")
                return

            ratio = 1 - (step / steps)
            r = int(original_rgb[0] * ratio + target_rgb[0] * (1 - ratio))
            g = int(original_rgb[1] * ratio + target_rgb[1] * (1 - ratio))
            b = int(original_rgb[2] * ratio + target_rgb[2] * (1 - ratio))
            self.status_label.config(foreground=rgb_to_hex(r, g, b))
            self.root.after(delay // steps, lambda: step_fade(step + 1))

        self.root.after(delay, step_fade)

    # =========================
    # Reset logic
    # =========================
    def reset_hours_and_points(self):
        """Reset all hours, clock fields, totals, and points back to standard values."""
        self._end_points_edit(commit=False)

        for item in self.tree.get_children():
            tags = set(self.tree.item(item, "tags"))
            if "editable" not in tags:
                continue

            vals = list(self.tree.item(item, "values"))
            number, name = vals[0], vals[1]

            # Restore original (standard) points
            std_points = self.original_points.get(item, vals[2])
            try:
                std_points = int(std_points)
            except (ValueError, TypeError):
                std_points = vals[2]

            # Reset punch/total visuals
            new_vals = (number, name, str(std_points), "🕒", "", "", "")
            self.tree.item(item, values=new_vals)

            # Clear punch data
            self.punch_data[item] = {"in": "", "out": "", "total": 0.0}

            # Remove highlight tags
            tags.discard("filled")
            tags.discard("points_edited")
            self.tree.item(item, tags=tuple(tags))

        # Clear temp overrides
        self.temp_points_overrides.clear()

        # Reset totals display rows
        if self.service_total_row:
            self.tree.item(self.service_total_row, values=("", "Total Service", "", "", "", "", "0.00"))
        if self.bussboy_total_row:
            self.tree.item(self.bussboy_total_row, values=("", "Total Bussboy", "", "", "", "", "0.00"))

        self.status_label.config(
            text="♻️ Heures et points réinitialisés aux valeurs standard.",
            foreground="#8B4513"
        )
        self.fade_out_status_label()

    # =========================
    # Points inline edit helpers
    # =========================
    def _begin_points_edit(self, row_id):
        # If already editing another row, commit it first
        if self.points_editor and self.points_editor_row != row_id:
            self._end_points_edit(commit=True)

        # Compute cell bbox to place the editor
        bbox = self.tree.bbox(row_id, column="#3")  # points is 3rd column
        if not bbox:
            return
        x, y, w, h = bbox

        # Current value
        current_vals = list(self.tree.item(row_id, "values"))
        try:
            current_points = int(current_vals[2])
        except (ValueError, TypeError):
            current_points = 0

        # Create spinbox editor
        self.points_editor_row = row_id
        self.points_editor = Spinbox(
            self.tree,
            from_=0,
            to=20,
            increment=1,
            width=5,
            justify="center",
            bootstyle="warning"
        )
        self.points_editor.delete(0, END)
        self.points_editor.insert(0, str(current_points))
        self.points_editor.place(x=x, y=y, width=w, height=h)

        # Bindings
        self.points_editor.focus_set()
        self.points_editor.bind("<Return>", lambda e: self._end_points_edit(commit=True))
        self.points_editor.bind("<KP_Enter>", lambda e: self._end_points_edit(commit=True))
        self.points_editor.bind("<Escape>", lambda e: self._end_points_edit(commit=False))
        self.points_editor.bind("<FocusOut>", lambda e: self._end_points_edit(commit=True))

    def _end_points_edit(self, commit=True):
        """Commit/cancel the current points edit if any."""
        if not self.points_editor:
            return

        row_id = self.points_editor_row
        val_str = self.points_editor.get()

        # destroy widget first (avoid re-entrancy)
        try:
            self.points_editor.destroy()
        finally:
            self.points_editor = None
            self.points_editor_row = None

        if not row_id or not self.tree.exists(row_id):
            return

        if commit:
            try:
                new_points = int(val_str)
                new_points = max(0, min(20, new_points))
            except (ValueError, TypeError):
                return  # ignore bad value, keep old

            vals = list(self.tree.item(row_id, "values"))
            old_points = vals[2]
            if str(new_points) != str(old_points):
                vals[2] = str(new_points)
                self.tree.item(row_id, values=vals)

                # mark as temporarily edited
                tags = set(self.tree.item(row_id, "tags"))
                tags.add("points_edited")
                self.tree.item(row_id, tags=tuple(tags))

                # track override for this session
                self.temp_points_overrides[row_id] = new_points
        else:
            # cancel: no changes
            pass
