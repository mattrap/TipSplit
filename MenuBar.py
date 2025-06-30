import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from datetime import datetime

def create_menu_bar(root, app):
    # Create themed top-level menu bar
    menu_bar = ttk.Frame(root, padding=(10, 5))
    menu_bar.pack(fill=X, side=TOP, before=root.winfo_children()[0])

    # Open menu
    open_button = ttk.Menubutton(menu_bar, text="Open")
    open_menu = ttk.Menu(open_button)
    open_menu.add_command(label="Master Sheet", command=app.show_master_tab)
    open_button["menu"] = open_menu
    open_button.pack(side=LEFT, padx=5)

    # Settings menu
    settings_button = ttk.Menubutton(menu_bar, text="Settings")
    settings_menu = ttk.Menu(settings_button)
    settings_menu.add_command(label="Preferences", command=lambda: None)
    settings_button["menu"] = settings_menu
    settings_button.pack(side=LEFT, padx=5)

    # Summary menu
    summary_button = ttk.Menubutton(menu_bar, text="Summary")
    summary_menu = ttk.Menu(summary_button)
    summary_menu.add_command(label="View Summary", command=lambda: None)
    summary_button["menu"] = summary_menu
    summary_button.pack(side=LEFT, padx=5)

    # Spacer
    spacer = ttk.Label(menu_bar)
    spacer.pack(side=LEFT, expand=True)

    # Clock
    clock_label = ttk.Label(menu_bar, font=("Helvetica", 10))
    clock_label.pack(side=RIGHT, padx=10)

    def update_clock():
        now = datetime.now()
        formatted_time = now.strftime("%A %d %B %Y - %H:%M:%S")
        clock_label.config(text=formatted_time.capitalize())
        clock_label.after(1000, update_clock)

    update_clock()

    return clock_label
