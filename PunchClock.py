import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import Toplevel
from datetime import datetime, timedelta
from icon_helper import set_app_icon


class PunchClockPopup:
    def __init__(self, master, row_id, on_save):
        self.master = master
        self.row_id = row_id
        self.on_save = on_save

        self.start_time = None
        self.end_time = None
        self.is_selecting_start = True
        self.temp_hour = None
        self.temp_minute = None

        self.selected_hour_btn = None
        self.selected_minute_btn = None

        self.window = Toplevel(master)
        self._icon_refs = {}
        set_app_icon(self.window, self._icon_refs)
        employee_selected = master.item(row_id, "values")[1]  # column 1 is the name
        self.window.title(f"Sélectionner les heures pour     {employee_selected}")
        self.window.grab_set()
        self.window.resizable(False, False)
        self.window.geometry("600x400")

        self.main_frame = ttk.Frame(self.window, padding=10)
        self.main_frame.pack(fill=BOTH, expand=True)

        self.label_start = ttk.Label(self.main_frame, text="Heure d'entrée: ",
                                     font=("Helvetica", 16, "bold"), bootstyle="primary")
        self.label_start.pack(pady=(5, 2))

        self.label_end = ttk.Label(self.main_frame, text="Heure de sortie: ",
                                   font=("Helvetica", 16, "bold"), bootstyle="primary")
        self.label_end.pack(pady=(0, 10))

        self.hour_frame = ttk.Frame(self.main_frame)
        self.hour_frame.pack(pady=(0, 10))
        self.hour_buttons = []
        self.quarter_buttons = []

        for hour in range(24):
            btn = ttk.Button(
                self.hour_frame,
                text=f"{hour:02d}",
                width=5,
                bootstyle="outline-primary",
                command=lambda h=hour: self.expand_hour_button(h)
            )
            row, col = divmod(hour, 6)
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.hour_buttons.append(btn)

        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(pady=(10, 0))

        self.reset_btn = ttk.Button(
            self.control_frame,
            text="Réinitialiser",
            bootstyle="danger-outline",
            command=self.reset
        )
        self.reset_btn.pack(side=LEFT, padx=10)

        self.save_btn = ttk.Button(
            self.control_frame,
            text="Enregistrer",
            bootstyle="success",
            command=self.save_and_close
        )
        self.save_btn.pack(side=LEFT, padx=10)
        self.save_btn.config(state=DISABLED)

    def expand_hour_button(self, hour):
        self.temp_hour = hour

        for btn in self.hour_buttons:
            btn.config(bootstyle="light", width=5, state=DISABLED)

        for qb in self.quarter_buttons:
            qb.destroy()
        self.quarter_buttons.clear()

        target_x = 300
        target_y = 160

        hour_btn = ttk.Button(
            self.main_frame,
            text=f"{hour:02d}",
            width=7,
            bootstyle="primary"
        )
        hour_btn.place(x=target_x, y=target_y, anchor="center")
        self.quarter_buttons.append(hour_btn)

        quarter_offsets = {
            ":00": (-50, 0),
            ":15": (0, 100),
            ":30": (50, 0),
            ":45": (0, -100),
        }

        for label, (dy, dx) in quarter_offsets.items():
            qbtn = ttk.Button(
                self.main_frame,
                text=label,
                width=5,
                bootstyle="outline-primary",
                command=lambda m=label: self.select_minute(m)
            )
            qbtn.place(x=target_x + dx, y=target_y + dy, anchor="center")
            qbtn.tkraise()
            self.quarter_buttons.append(qbtn)

        if self.is_selecting_start:
            self.label_start.config(text=f"Heure d'entrée : {hour:02d}:00", bootstyle="primary")
        else:
            self.label_end.config(text=f"Heure de sortie : {hour:02d}:00", bootstyle="primary")

    def select_minute(self, minute_str):
        minute = int(minute_str[1:])
        if self.temp_hour is None:
            return

        self.temp_minute = minute
        full_time = f"{self.temp_hour:02d}:{minute:02d}"

        for btn in self.quarter_buttons:
            if btn.cget("text") == minute_str:
                btn.config(bootstyle="primary")
                self.selected_minute_btn = btn
            elif btn.cget("text").startswith(":"):
                btn.config(bootstyle="outline-primary")

        if self.is_selecting_start:
            self.start_time = (self.temp_hour, minute)
            self.label_start.config(text=f"Heure d'entrée : {full_time}", bootstyle="success")  # Turn green
            self.is_selecting_start = False
            self.reset_hour_buttons()
        else:
            self.end_time = (self.temp_hour, minute)
            self.label_end.config(text=f"Heure de sortie : {full_time}", bootstyle="success")  # Turn green
            self.save_btn.config(state=NORMAL)
            self.reset_hour_buttons()
            self.highlight_range()

        self.temp_hour = None
        self.temp_minute = None

    def highlight_range(self):
        for btn in self.hour_buttons:
            btn.config(bootstyle="light")

        if not self.start_time or not self.end_time:
            return

        start_dt = datetime(2000, 1, 1, *self.start_time)
        end_dt = datetime(2000, 1, 1, *self.end_time)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        current = start_dt
        while current <= end_dt:
            idx = current.hour % 24
            self.hour_buttons[idx].config(bootstyle="primary")
            current += timedelta(hours=1)

    def reset_hour_buttons(self, *_):
        for btn in self.hour_buttons:
            btn.config(bootstyle="outline-primary", width=5, state=NORMAL)

        for btn in self.quarter_buttons:
            btn.destroy()
        self.quarter_buttons.clear()

        self.selected_hour_btn = None
        self.selected_minute_btn = None

    def get_start_time_str(self):
        return f"{self.start_time[0]:02d}:{self.start_time[1]:02d}" if self.start_time else "??:??"

    def save_and_close(self):
        if self.start_time and self.end_time:
            start_dt = datetime(2000, 1, 1, *self.start_time)
            end_dt = datetime(2000, 1, 1, *self.end_time)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            duration = round((end_dt - start_dt).total_seconds() / 3600 * 4) / 4
            start_str = self.get_start_time_str()
            end_str = f"{self.end_time[0]:02d}:{self.end_time[1]:02d}"

            self.on_save(self.row_id, start_str, end_str, duration)
            self.window.destroy()

    def reset(self):
        self.start_time = None
        self.end_time = None
        self.is_selecting_start = True
        self.temp_hour = None
        self.temp_minute = None
        self.label_start.config(text="Heure d'entrée:", bootstyle="primary")
        self.label_end.config(text="Heure de sortie:", bootstyle="primary")
        self.save_btn.config(state=DISABLED)

        self.reset_hour_buttons()
        self.on_save(self.row_id, "", "", "")
