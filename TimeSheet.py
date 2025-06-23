import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry
from MenuBar import create_menu_bar
from PunchClock import PunchClockPopup
import json
import os

SERVICE_FILE = "service_employees.json"
BUSSBOY_FILE = "bussboy_employees.json"
EXPORT_FILE = "DaySheet.json"

class TimeSheet:
    def __init__(self, root, shared_data=None, day_sheet=None):
        self.shared_data = shared_data or {}
        self.day_sheet = day_sheet
        self.root = root
        self.service_total_row = None
        self.bussboy_total_row = None
        self.punch_data = {}
        self.hovered_row = None

        content = ttk.Frame(self.root, padding=10)
        content.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(content)
        header_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(header_frame, text="Remplir les heures du:", font=("Helvetica", 16, "bold")).pack(side=LEFT)
        self.date_picker = DateEntry(header_frame, bootstyle="primary", dateformat="%d-%B-%Y-%A", width=20)
        self.date_picker.pack(side=LEFT, padx=(10, 0))

        confirm_btn = ttk.Button(
            header_frame,
            text="Confirmer",
            bootstyle="success-outline",
            command=self.export_filled_rows
        )
        confirm_btn.pack(side=RIGHT)

        # Treeview
        self.tree = ttk.Treeview(
            content,
            columns=("number", "name", "points", "punch", "in", "out", "total"),
            show="headings",
            bootstyle="primary"
        )

        headings = {
            "number": "Numéro",
            "name": "Nom",
            "points": "Points",
            "punch": "🕒",
            "in": "Entrée",
            "out": "Sortie",
            "total": "Total"
        }

        for col, label in headings.items():
            self.tree.heading(col, text=label)

        self.tree.column("number", width=100, anchor=CENTER)
        self.tree.column("name", width=200, anchor=W)
        self.tree.column("points", width=100, anchor=CENTER)
        self.tree.column("punch", width=50, anchor=CENTER)
        self.tree.column("in", width=80, anchor=CENTER)
        self.tree.column("out", width=80, anchor=CENTER)
        self.tree.column("total", width=80, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=True)

        # Tag styling
        self.tree.tag_configure("section", font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("hover", background="#e0f7fa")
        self.tree.tag_configure("total", font=("Helvetica", 10, "bold"), background="#e8f5e9")

        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Motion>", self.on_hover)
        self.root.bind("<Visibility>", lambda e: self.reload())

        self.reload()

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
        self.hovered_row = None  # ✅ Reset hovered_row on reload

        service_data = self.load_data_file(SERVICE_FILE)
        if service_data:
            self.tree.insert("", "end", values=("", "--- Service ---", "", "", "", "", ""), tags=("section",))
            for row in service_data:
                row_id = self.tree.insert("", "end", values=(row[0], row[1], row[2], "🕒", "", "", ""), tags=("editable",))
                self.punch_data[row_id] = {"in": "", "out": "", "total": ""}
            self.service_total_row = self.tree.insert("", "end", values=("", "Total Service", "", "", "", "", "0.00"), tags=("total",))

        bussboy_data = self.load_data_file(BUSSBOY_FILE)
        if bussboy_data:
            self.tree.insert("", "end", values=("", "--- Bussboy ---", "", "", "", "", ""), tags=("section",))
            for row in bussboy_data:
                row_id = self.tree.insert("", "end", values=(row[0], row[1], row[2], "🕒", "", "", ""), tags=("editable",))
                self.punch_data[row_id] = {"in": "", "out": "", "total": ""}
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

            try:
                total = float(self.tree.item(item, "values")[6])
            except (ValueError, IndexError):
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
        for item in self.tree.get_children():
            tags = self.tree.item(item, "tags")
            if "section" in tags or "total" in tags:
                continue
            values = self.tree.item(item, "values")
            number, name, points, _, punch_in, punch_out, total = values
            if total.strip():
                export_data.append({
                    "number": number,
                    "name": name,
                    "points": points,
                    "hours": total
                })

        with open(EXPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        if self.day_sheet:
            selected_date = self.date_picker.entry.get()
            self.day_sheet.load_data(export_data, selected_date=selected_date)

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
        current[6] = f"{total:.2f}" if isinstance(total, (float, int)) else total
        self.tree.item(row_id, values=current)
        self.update_totals()

    def on_hover(self, event):
        row_id = self.tree.identify_row(event.y)

        # Skip if same as previous or not editable
        if row_id == self.hovered_row or not row_id:
            return
        if "editable" not in self.tree.item(row_id, "tags"):
            return

        # Remove hover from previous
        if self.hovered_row and self.tree.exists(self.hovered_row):
            prev_tags = [tag for tag in self.tree.item(self.hovered_row, "tags") if tag != "hover"]
            self.tree.item(self.hovered_row, tags=tuple(prev_tags))

        # Add hover to new row
        if self.tree.exists(row_id):
            tags = list(self.tree.item(row_id, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tree.item(row_id, tags=tuple(tags))

        self.hovered_row = row_id

# Optional standalone usage
if __name__ == "__main__":
    app_root = ttk.Window(themename="flatly", title="Time Sheet")
    create_menu_bar(app_root)
    TimeSheet(app_root)
    app_root.mainloop()
