import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry
from MenuBar import create_menu_bar
from PunchClock import PunchClockPopup
from datetime import datetime
import json
import os

SERVICE_FILE = "service_employees.json"
BUSSBOY_FILE = "bussboy_employees.json"

class TimeSheet:
    def __init__(self, root, shared_data=None, reload_distribution_data=None):
        self.shared_data = shared_data
        self.reload_distribution_data = reload_distribution_data
        self.root = root
        self.service_total_row = None
        self.bussboy_total_row = None
        self.punch_data = {}
        self.hovered_row = None
        self.sort_directions = {}

        content = ttk.Frame(self.root, padding=10)
        content.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(content)
        header_frame.pack(fill=X, pady=(0, 10))

        self.create_date_picker(header_frame)
        self.create_confirm_button(header_frame)

        self.status_label = ttk.Label(header_frame, text="", font=("Helvetica", 10))
        self.status_label.pack(side=LEFT, padx=10)

        # --- Taller rows style (added) ---
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            font=("Helvetica", 14),  # bigger text
            rowheight=35             # taller rows
        )
        style.configure(
            "Custom.Treeview.Heading",
            font=("Helvetica", 14, "bold")
        )
        # ---------------------------------

        # Treeview
        self.tree = ttk.Treeview(
            content,
            columns=("number", "name", "points", "punch", "in", "out", "total"),
            show="headings",
            bootstyle="primary",
            style="Custom.Treeview"  # applied taller row style
        )
        self.tree.configure(selectmode="none")

        self.base_labels = {
            "number": "Numéro",
            "name": "Nom",
            "points": "Points",
            "punch": "🕒",
            "in": "Entrée",
            "out": "Sortie",
            "total": "Total"
        }

        for col, label in self.base_labels.items():
            if col in ["number", "name", "points"]:
                self.tree.heading(col, text=label, command=lambda _col=col: self.sort_by_column(self.tree, _col))
            else:
                self.tree.heading(col, text=label)

        self.tree.column("number", width=100, anchor=CENTER)
        self.tree.column("name", width=200, anchor=W)
        self.tree.column("points", width=100, anchor=CENTER)
        self.tree.column("punch", width=50, anchor=CENTER)
        self.tree.column("in", width=80, anchor=CENTER)
        self.tree.column("out", width=80, anchor=CENTER)
        self.tree.column("total", width=80, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)

        self.tree.tag_configure("section", font=("Helvetica", 16, "bold"), background="#b4c7af") #dark green
        self.tree.tag_configure("hover", background="#e0f7fa")
        self.tree.tag_configure("total", font=("Helvetica", 14, "bold"), background="#e8f5e9") # light green
        self.tree.tag_configure("filled", background="#d8eff0")  # after data entered

        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Motion>", self.on_hover)

        self.reload()

    def create_date_picker(self, parent):
        ttk.Label(parent, text="Remplir les heures du:", font=("Helvetica", 16, "bold")).pack(side=LEFT)

        self.date_picker = DateEntry(parent, bootstyle="primary", dateformat="%d-%m-%Y", width=20)
        self.date_picker.entry.bind("<Key>", lambda e: "break")  # block manual typing
        self.date_picker.pack(side=LEFT, padx=(10, 0))

        # Reset field to blank on startup
        self.date_picker.entry.delete(0, END)

    def create_confirm_button(self, parent):
        confirm_btn = ttk.Button(
            parent,
            text="Confirmer",
            bootstyle="success-outline",
            command=self.export_filled_rows
        )
        confirm_btn.pack(side=RIGHT)

    def load_data_file(self, filename):
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
        return []

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        self.service_total_row = None
        self.bussboy_total_row = None
        self.punch_data.clear()
        self.hovered_row = None

        service_data = self.load_data_file(SERVICE_FILE)
        if service_data:
            self.tree.insert("", "end", values=("", "--- Service ---", "", "", "", "", ""), tags=("section",))
            for row in service_data:
                row_id = self.tree.insert("", "end", values=(row[0], row[1], row[2], "🕒", "", "", ""), tags=("editable",))
                self.punch_data[row_id] = {"in": "", "out": "", "total": 0.0}
            self.service_total_row = self.tree.insert("", "end", values=("", "Total Service", "", "", "", "", "0.00"), tags=("total",))

        bussboy_data = self.load_data_file(BUSSBOY_FILE)
        if bussboy_data:
            self.tree.insert("", "end", values=("", "--- Bussboy ---", "", "", "", "", ""), tags=("section",))
            for row in bussboy_data:
                row_id = self.tree.insert("", "end", values=(row[0], row[1], row[2], "🕒", "", "", ""), tags=("editable",))
                self.punch_data[row_id] = {"in": "", "out": "", "total": 0.0}
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
            if "total" in tags:
                continue
            if "editable" not in tags:
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
        export_data = []
        current_section = None
        date_str = self.date_picker.entry.get().strip()

        if not date_str:
            self.flash_date_field()
            self.status_label.config(text="⛔ Veuillez choisir une date!", foreground="#B22222")
            self.fade_out_status_label()
            return

        try:
            datetime.strptime(date_str, self.date_picker.dateformat)
        except ValueError:
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
                continue

            if "editable" not in tags:
                continue

            punch = self.punch_data.get(item, {})
            try:
                total = float(punch.get("total", 0))
            except ValueError:
                total = 0

            if total > 0:
                export_data.append({
                    "section": current_section,
                    "number": values[0],
                    "name": values[1],
                    "points": values[2],
                    "in": punch.get("in", ""),
                    "out": punch.get("out", ""),
                    "hours": f"{total:.2f}"
                })

        self.shared_data.setdefault("transfer", {})
        self.shared_data["transfer"]["date"] = date_str
        self.shared_data["transfer"]["entries"] = export_data

        self.status_label.config(
            text="✅ Les Heures ont été enregistrées et transférées à l’onglet Distribution",
            foreground="#228B22")
        self.fade_out_status_label()

        if self.reload_distribution_data:
            self.reload_distribution_data()

        if "distribution_tab" in self.shared_data:
            dist_tab = self.shared_data["distribution_tab"]
            if hasattr(dist_tab, "update_pay_period_display"):
                dist_tab.update_pay_period_display()

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        col_index = int(col.replace("#", "")) - 1

        if not row_id or "editable" not in self.tree.item(row_id, "tags"):
            return

        if col_index == 3:  # 🕒 clicked
            PunchClockPopup(self.tree, row_id, self.on_clock_saved)

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

        # Add or remove "filled" tag
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
        direction = self.sort_directions.get(col, False)
        self.sort_directions[col] = not direction

        def get_val(item):
            val = tree.set(item, col)
            try:
                return float(val)
            except ValueError:
                return val.lower()

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
            if count % 2 == 0:
                entry.configure(style="danger.TEntry")
            else:
                entry.configure(style="TEntry")
            entry.after(150, lambda: flash(count + 1))

        flash()

    def fade_out_status_label(self, delay=1500, steps=7):
        def rgb_to_hex(r, g, b):
            return f"#{r:02x}{g:02x}{b:02x}"

        try:
            # Get the current foreground color of the label
            fg_color = self.status_label.cget("foreground")
            original_rgb = tuple(c // 256 for c in self.status_label.winfo_rgb(fg_color))
        except:
            original_rgb = (0, 0, 0)  # fallback to black

        try:
            # Get the label's background color to fade into
            bg_color = self.status_label.cget("background")
            target_rgb = tuple(c // 256 for c in self.status_label.winfo_rgb(bg_color))
        except:
            target_rgb = (255, 255, 255)  # fallback to white

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
