import os
import json
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
from tkinter import StringVar, END, Listbox, Text
from ttkbootstrap.constants import *

class JsonViewerTab:
    def __init__(self, master):
        self.master = master
        self.frame = ttk.Frame(master)

        self.pay_period_var = StringVar()
        self.json_file_var = StringVar()
        self.current_file_path = None

        self.view_mode = StringVar(value="distribution")

        self._build_ui()
        self.refresh_pay_periods()
        self.frame.pack(fill="both", expand=True)

    def _build_ui(self):
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=X, pady=5, padx=10)

        ttk.Label(header_frame, text="Période de paye:").pack(side=LEFT)
        self.period_menu = ttk.Combobox(header_frame, textvariable=self.pay_period_var, state="readonly", width=28)
        self.period_menu.pack(side=LEFT, padx=5)
        self.period_menu.bind("<<ComboboxSelected>>", self.on_period_select)

        ttk.Button(header_frame, text="Rafraîchir", command=self.refresh_pay_periods).pack(side=LEFT, padx=5)

        # View toggle (right side)
        view_frame = ttk.Frame(header_frame)
        view_frame.pack(side=RIGHT)
        self.view_dist_btn = ttk.Button(view_frame, text="Vue Distribution", bootstyle="primary",
                                        command=lambda: self.set_view_mode("distribution"))
        self.view_decl_btn = ttk.Button(view_frame, text="Vue Déclaration", bootstyle="outline-primary",
                                        command=lambda: self.set_view_mode("declaration"))
        self.view_dist_btn.pack(side=LEFT)
        self.view_decl_btn.pack(side=LEFT, padx=6)

        # JSON file list
        list_frame = ttk.Frame(self.frame)
        list_frame.pack(fill=X, padx=10, pady=(2, 0))
        ttk.Label(list_frame, text="Fichiers JSON:").pack(anchor=W)

        self.file_listbox = Listbox(list_frame, height=6)
        self.file_listbox.pack(fill=X, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        # Inputs (Distribution)
        input_frame = ttk.LabelFrame(self.frame, text="Valeurs entrées (Distribution)")
        input_frame.pack(fill=X, expand=False, padx=10, pady=(10, 5))
        self.inputs_text = Text(input_frame, height=6, wrap="none")
        self.inputs_text.pack(fill=X, expand=True)

        # Declaration inputs
        decl_input_frame = ttk.LabelFrame(self.frame, text="Paramètres de déclaration")
        decl_input_frame.pack(fill=X, expand=False, padx=10, pady=(5, 5))
        self.decl_inputs_text = Text(decl_input_frame, height=5, wrap="none")
        self.decl_inputs_text.pack(fill=X, expand=True)

        # Employees Treeview
        emp_frame = ttk.LabelFrame(self.frame, text="Données des employés")
        emp_frame.pack(fill=BOTH, expand=True, padx=10, pady=(5, 10))

        columns = ("id", "name", "hours",
                   "cash", "sur_paye", "frais_admin",
                   "A", "B", "D", "E", "F",
                   "section")
        self.tree = ttk.Treeview(emp_frame, columns=columns, show="headings")
        headings = {
            "id": "#",
            "name": "Nom",
            "hours": "Heures",
            "cash": "Cash",
            "sur_paye": "Sur Paye",
            "frais_admin": "Frais Admin",
            "A": "A",
            "B": "B",
            "D": "D",
            "E": "E",
            "F": "F",
            "section": "Section",
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "w" if col in ("name", "section") else "center"
            width = 180 if col == "name" else (90 if col not in ("section",) else 110)
            self.tree.column(col, anchor=anchor, width=width, stretch=True)

        self.tree.pack(fill=BOTH, expand=True)

        # Default to Distribution view
        self.show_distribution_view()

        # Action buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Supprimer cette distribution", bootstyle=DANGER,
                   command=self.delete_selected_file).pack(side=LEFT, padx=5)

    def show_distribution_view(self):
        self.tree["displaycolumns"] = ("id", "name", "hours", "cash", "sur_paye", "frais_admin", "section")
        self.view_mode.set("distribution")
        self.view_dist_btn.config(bootstyle="primary")
        self.view_decl_btn.config(bootstyle="outline-primary")

    def show_declaration_view(self):
        self.tree["displaycolumns"] = ("id", "name", "hours", "A", "B", "D", "E", "F", "section")
        self.view_mode.set("declaration")
        self.view_dist_btn.config(bootstyle="outline-primary")
        self.view_decl_btn.config(bootstyle="primary")

    def set_view_mode(self, mode):
        if mode == "declaration":
            self.show_declaration_view()
        else:
            self.show_distribution_view()

    def refresh_pay_periods(self):
        base_dir = os.path.join("exports", "json")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        periods = sorted([name for name in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, name))])
        self.period_menu["values"] = periods

        if periods:
            self.pay_period_var.set(periods[0])
            self.on_period_select()
        else:
            self.pay_period_var.set("")
            self.file_listbox.delete(0, END)
            self.clear_treeviews()

    def on_period_select(self, event=None):
        self.file_listbox.delete(0, END)
        self.clear_treeviews()

        selected_period = self.pay_period_var.get()
        if not selected_period:
            return

        folder_path = os.path.join("exports", "json", selected_period)
        json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
        for f in sorted(json_files):
            self.file_listbox.insert(END, f)

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if not selection:
            return

        selected_file = self.file_listbox.get(selection[0])
        self.current_file_path = os.path.join("exports", "json", self.pay_period_var.get(), selected_file)

        try:
            with open(self.current_file_path, "r", encoding="utf-8") as f:
                content = json.load(f)

            self.clear_treeviews()

            # Distribution inputs
            inputs = content.get("inputs", {})
            self.inputs_text.delete("1.0", END)
            for key, val in inputs.items():
                self.inputs_text.insert(END, f"{key}: {val}\n")

            # Declaration inputs
            decl_inputs = content.get("declaration_inputs", {})
            self.decl_inputs_text.delete("1.0", END)
            if decl_inputs:
                for key, val in decl_inputs.items():
                    self.decl_inputs_text.insert(END, f"{key}: {val}\n")
            else:
                self.decl_inputs_text.insert(END, "(Aucune donnée de déclaration)")

            # Employees rows (supports both views)
            for emp in content.get("employees", []):
                # Skip if it's a malformed object
                if not isinstance(emp, dict):
                    continue

                # Numbers or blanks for declaration fields
                def _fmt(x):
                    return "" if x in ("", None) else x

                self.tree.insert("", END, values=(
                    emp.get("employee_id", ""),
                    emp.get("name", ""),
                    emp.get("hours", 0.0),
                    emp.get("cash", 0.0),
                    emp.get("sur_paye", 0.0),
                    emp.get("frais_admin", 0.0),
                    _fmt(emp.get("A", "")),
                    _fmt(emp.get("B", "")),
                    _fmt(emp.get("D", "")),
                    _fmt(emp.get("E", "")),
                    _fmt(emp.get("F", "")),
                    emp.get("section", ""),
                ))

            # Keep current view mode after loading
            if self.view_mode.get() == "declaration":
                self.show_declaration_view()
            else:
                self.show_distribution_view()

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier JSON:\n{str(e)}")

    def clear_treeviews(self):
        self.inputs_text.delete("1.0", END)
        self.decl_inputs_text.delete("1.0", END)
        for item in self.tree.get_children():
            self.tree.delete(item)

    def delete_selected_file(self):
        if not self.current_file_path:
            messagebox.showwarning("Aucun fichier sélectionné", "Veuillez d'abord sélectionner une distribution.")
            return

        file_name = os.path.basename(self.current_file_path)
        confirm = messagebox.askyesno("Confirmer la suppression",
                                      f"Êtes-vous sûr de vouloir supprimer '{file_name}' ?")
        if confirm:
            try:
                os.remove(self.current_file_path)
                messagebox.showinfo("Supprimé", "Fichier supprimé avec succès.")
                self.refresh_pay_periods()
                self.current_file_path = None
                self.clear_treeviews()
            except Exception as e:
                messagebox.showerror("Erreur", f"Échec de la suppression:\n{str(e)}")
