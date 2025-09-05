# JsonViewerTab.py — backend-only JSON browser/combiner
# Features added:
# 1) Sort pay periods and files newest-first
# 2) Defensive JSON loading (clean error handling)
# Also: keep *all* JSONs inside the app’s backend (no JSONs in user-visible folders)

import os
import json
import glob
import datetime as _dt
import ttkbootstrap as ttk
from tkinter import messagebox
from tkinter import StringVar, END, Listbox
from tkinter.scrolledtext import ScrolledText
from ttkbootstrap.constants import *

# JSONs (per-day and combined) live in the internal backend
from AppConfig import get_backend_dir
from ui_scale import scale
from tree_utils import fit_columns


class JsonViewerTab:
    def __init__(self, master):
        self.master = master
        self.frame = ttk.Frame(master)

        # UI state
        self.pay_period_var = StringVar()
        self.json_file_var = StringVar()
        self.current_file_path = None
        self.current_file_source = None  # 'unconfirmed' or 'confirmed'
        self.view_mode = StringVar(value="distribution")

        # --- Folders ---

        self.backend_json_root = get_backend_dir()

        # Per-day JSONs: {backend}/daily/{pay_period}/(unconfirmed|confirmed)/*.json
        self.base_dir = os.path.join(self.backend_json_root, "daily")

        # Combined pay summaries: {backend}/pay/{pay_period}/combined.Json
        self.pay_root = os.path.join(self.backend_json_root, "pay")
        os.makedirs(self.pay_root, exist_ok=True)

        # Map pay-period label -> absolute path
        self.period_paths = {}
        # The absolute path of the currently selected pay-period folder
        self.current_period_path = None
        self.unconfirmed_dir = None
        self.confirmed_dir = None

        self._build_ui()
        self.refresh_pay_periods()
        self.frame.pack(fill="both", expand=True)

    def _build_ui(self):
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=X, pady=5, padx=10)

        ttk.Label(header_frame, text="Période de paye (backend):").pack(side=LEFT)
        self.period_menu = ttk.Combobox(header_frame, textvariable=self.pay_period_var, state="readonly", width=28)
        self.period_menu.pack(side=LEFT, padx=5)
        self.period_menu.bind("<<ComboboxSelected>>", self.on_period_select)

        ttk.Button(
            header_frame,
            text="Rafraîchir",
            command=self.refresh_pay_periods,
            bootstyle=INFO,
        ).pack(side=LEFT, padx=5)

        # View toggle (right side)
        view_frame = ttk.Frame(header_frame)
        view_frame.pack(side=RIGHT)
        self.view_dist_btn = ttk.Button(
            view_frame, text="Vue Distribution", bootstyle="primary",
            command=lambda: self.set_view_mode("distribution")
        )
        self.view_decl_btn = ttk.Button(
            view_frame, text="Vue Déclaration", bootstyle="outline-primary",
            command=lambda: self.set_view_mode("declaration")
        )
        self.view_dist_btn.pack(side=LEFT)
        self.view_decl_btn.pack(side=LEFT, padx=6)

        # JSON file lists (unconfirmed vs confirmed)
        list_frame = ttk.Frame(self.frame)
        list_frame.pack(fill=X, padx=10, pady=(2, 0))

        # Unconfirmed files
        unconf_frame = ttk.Frame(list_frame)
        unconf_frame.pack(side=LEFT, fill=BOTH, expand=True)
        ttk.Label(unconf_frame, text="Nouveaux fichiers NON-vérifiés").pack(anchor=W)
        unconf_lb_frame = ttk.Frame(unconf_frame)
        unconf_lb_frame.pack(fill=X, pady=5)
        self.unconfirmed_listbox = Listbox(unconf_lb_frame, height=6)
        self.unconfirmed_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        unconf_scroll = ttk.Scrollbar(unconf_lb_frame, orient=VERTICAL, command=self.unconfirmed_listbox.yview)
        unconf_scroll.pack(side=RIGHT, fill=Y)
        self.unconfirmed_listbox.config(yscrollcommand=unconf_scroll.set)
        self.unconfirmed_listbox.bind(
            "<<ListboxSelect>>", lambda e: self.on_file_select(e, source="unconfirmed")
        )

        self.delete_btn = ttk.Button(
            unconf_frame,
            text="Supprimer cette distribution",
            bootstyle=DANGER,
            command=self.delete_selected_file,
            state=DISABLED,
        )
        self.delete_btn.pack(fill=X, pady=(0, 5))

        # Transfer button between lists
        transfer_frame = ttk.Frame(list_frame)
        transfer_frame.pack(side=LEFT, fill=Y, padx=5)
        self.transfer_btn = ttk.Button(
            transfer_frame,
            text="-->",
            command=self.confirm_selected_file,
            state=DISABLED,
            width=3,
            bootstyle=SUCCESS,
        )
        self.transfer_btn.pack(pady=(20, 5))
        self.transfer_back_btn = ttk.Button(
            transfer_frame,
            text="<--",
            command=self.unconfirm_selected_file,
            state=DISABLED,
            width=3,
            bootstyle=WARNING,
        )
        self.transfer_back_btn.pack()

        # Confirmed files
        conf_frame = ttk.Frame(list_frame)
        conf_frame.pack(side=LEFT, fill=BOTH, expand=True)
        ttk.Label(conf_frame, text="Distributions confirmées").pack(anchor=W)
        conf_lb_frame = ttk.Frame(conf_frame)
        conf_lb_frame.pack(fill=X, pady=5)
        self.confirmed_listbox = Listbox(conf_lb_frame, height=6)
        self.confirmed_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        conf_scroll = ttk.Scrollbar(conf_lb_frame, orient=VERTICAL, command=self.confirmed_listbox.yview)
        conf_scroll.pack(side=RIGHT, fill=Y)
        self.confirmed_listbox.config(yscrollcommand=conf_scroll.set)
        self.confirmed_listbox.bind(
            "<<ListboxSelect>>", lambda e: self.on_file_select(e, source="confirmed")
        )

        ttk.Button(
            conf_frame,
            text="Créer fichier combiné",
            command=self.on_create_combined_file,
        ).pack(fill=X)

        self.file_info_var = StringVar(value="Aucun fichier sélectionné")

        ttk.Label(
            self.frame, textvariable=self.file_info_var, bootstyle="info"
        ).pack(anchor=W, padx=10, pady=(5, 5))

        # Input summaries shown side by side
        inputs_wrapper = ttk.Frame(self.frame)
        inputs_wrapper.pack(fill=X, expand=False, padx=10, pady=(0, 5))

        input_frame = ttk.LabelFrame(inputs_wrapper, text="Valeurs entrées (Distribution)")
        input_frame.pack(side=LEFT, fill=BOTH, expand=True)
        self.inputs_text = ScrolledText(input_frame, height=6, wrap="none")
        self.inputs_text.pack(fill=BOTH, expand=True)

        decl_input_frame = ttk.LabelFrame(inputs_wrapper, text="Paramètres de déclaration")
        decl_input_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0))
        self.decl_inputs_text = ScrolledText(decl_input_frame, height=6, wrap="none")
        self.decl_inputs_text.pack(fill=BOTH, expand=True)

        # Employees Treeview
        emp_frame = ttk.LabelFrame(self.frame, text="Données des employés")
        emp_frame.pack(fill=BOTH, expand=True, padx=10, pady=(5, 10))

        columns = (
            "id",
            "name",
            "hours",
            "cash",
            "sur_paye",
            "frais_admin",
            "A",
            "B",
            "D",
            "E",
            "F",
            "section",
        )

        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=scale(25))
        tree_container = ttk.Frame(emp_frame)
        tree_container.pack(fill=BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_container, columns=columns, show="headings", style="Custom.Treeview"
        )
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
        self._width_map = {}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "w" if col in ("name", "section") else "center"
            width = 180 if col == "name" else (90 if col not in ("section",) else 110)
            scaled_width = scale(width)
            self._width_map[col] = scaled_width
            self.tree.column(col, anchor=anchor, width=scaled_width, minwidth=scale(20), stretch=True)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_scroll_y = ttk.Scrollbar(tree_container, orient=VERTICAL, command=self.tree.yview)
        tree_scroll_y.pack(side=RIGHT, fill=Y)
        tree_scroll_x = ttk.Scrollbar(emp_frame, orient=HORIZONTAL, command=self.tree.xview)
        tree_scroll_x.pack(fill=X)
        self.tree.config(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        fit_columns(self.tree, self._width_map)

        # Default to Distribution view
        self.show_distribution_view()

    # -----------------------
    # View switching
    # -----------------------
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

    # -----------------------
    # Pay period loading
    # -----------------------
    def refresh_pay_periods(self):
        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)

        # Discover pay-period folders and build label->path map
        self.period_paths = {}
        periods = []
        try:
            for name in os.listdir(self.base_dir):
                full_path = os.path.join(self.base_dir, name)
                if os.path.isdir(full_path):
                    periods.append(name)
                    self.period_paths[name] = full_path
        except FileNotFoundError:
            pass

        # Feature 1: newest-first sort (string sort works for ISO-like labels)
        periods = sorted(periods, reverse=True)
        self.period_menu["values"] = periods

        # Preserve selection if possible, otherwise select first available
        current = (self.pay_period_var.get() or "").strip()
        if current in periods:
            self.pay_period_var.set(current)
        elif periods:
            self.pay_period_var.set(periods[0])
        else:
            self.pay_period_var.set("")

        # Trigger list refresh
        self.on_period_select()

    def on_period_select(self, event=None):
        # Reset lists and current selection
        self.unconfirmed_listbox.delete(0, END)
        self.confirmed_listbox.delete(0, END)
        self.clear_treeviews()
        self.file_info_var.set("Aucun fichier sélectionné!")
        self.current_file_path = None
        self.current_file_source = None
        self.delete_btn.config(state=DISABLED)
        self.transfer_btn.config(state=DISABLED)
        self.transfer_back_btn.config(state=DISABLED)

        label = (self.pay_period_var.get() or "").strip()
        if not label:
            self.current_period_path = None
            self.unconfirmed_dir = None
            self.confirmed_dir = None
            return

        folder_path = self.period_paths.get(label) or os.path.join(self.base_dir, label)
        self.current_period_path = folder_path  # cache for later actions
        self.unconfirmed_dir = os.path.join(folder_path, "unconfirmed")
        self.confirmed_dir = os.path.join(folder_path, "confirmed")
        os.makedirs(self.unconfirmed_dir, exist_ok=True)
        os.makedirs(self.confirmed_dir, exist_ok=True)

        # Feature 1: newest-first file list for each folder
        unconfirmed_files = sorted(
            (f for f in os.listdir(self.unconfirmed_dir) if f.endswith(".json")), reverse=True
        )
        for f in unconfirmed_files:
            self.unconfirmed_listbox.insert(END, f)

        confirmed_files = sorted(
            (f for f in os.listdir(self.confirmed_dir) if f.endswith(".json")), reverse=True
        )
        for f in confirmed_files:
            self.confirmed_listbox.insert(END, f)

    # -----------------------
    # File selection & display
    # -----------------------
    def on_file_select(self, event, source):
        # Ensure only one listbox has a selection
        if source == "unconfirmed":
            selection = self.unconfirmed_listbox.curselection()
            self.confirmed_listbox.selection_clear(0, END)
            base_dir = self.unconfirmed_dir
        else:
            selection = self.confirmed_listbox.curselection()
            self.unconfirmed_listbox.selection_clear(0, END)
            base_dir = self.confirmed_dir

        if not selection or not base_dir:
            return

        selected_file = (
            self.unconfirmed_listbox.get(selection[0])
            if source == "unconfirmed"
            else self.confirmed_listbox.get(selection[0])
        )

        if not self.current_period_path:
            messagebox.showerror("Erreur", "Aucun dossier de période sélectionné.")
            return

        self.current_file_path = os.path.join(base_dir, selected_file)
        self.current_file_source = source
        try:
            mtime = os.path.getmtime(self.current_file_path)
            ts = _dt.datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
            self.file_info_var.set(f"Fichier sélectionné: {selected_file} // Créé le: {ts}")
        except OSError:
            self.file_info_var.set(f"Fichier sélectionné: {selected_file}")

        # Feature 2: defensive JSON load
        try:
            with open(self.current_file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier JSON:\n{type(e).__name__}: {e}")
            return

        try:
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
                if not isinstance(emp, dict):
                    continue

                def _fmt(x):
                    return "" if x in ("", None) else str(x)

                self.tree.insert(
                    "",
                    END,
                    values=(
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
                    ),
                )

            # Keep current view mode after loading
            if self.view_mode.get() == "declaration":
                self.show_declaration_view()
            else:
                self.show_distribution_view()

            if source == "unconfirmed":
                self.delete_btn.config(state=NORMAL)
                self.transfer_btn.config(state=NORMAL)
                self.transfer_back_btn.config(state=DISABLED)
            else:
                self.delete_btn.config(state=DISABLED)
                self.transfer_btn.config(state=DISABLED)
                self.transfer_back_btn.config(state=NORMAL)

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d’afficher le JSON chargé:\n{type(e).__name__}: {e}")

    def clear_treeviews(self):
        self.inputs_text.delete("1.0", END)
        self.decl_inputs_text.delete("1.0", END)
        for item in self.tree.get_children():
            self.tree.delete(item)

    # -----------------------
    # Delete action
    # -----------------------
    def delete_selected_file(self):
        if not self.current_file_path or self.current_file_source != "unconfirmed":
            messagebox.showwarning(
                "Sélection requise",
                "Veuillez sélectionner un fichier NON-vérifié à supprimer.",
            )
            return

        file_name = os.path.basename(self.current_file_path)
        confirm = messagebox.askyesno(
            "Confirmer la suppression",
            f"Êtes-vous sûr de vouloir supprimer '{file_name}' ?"
        )
        if confirm:
            try:
                os.remove(self.current_file_path)
                messagebox.showinfo("Supprimé", "Fichier supprimé avec succès.")
                self.on_period_select(None)
                self.current_file_path = None
                self.current_file_source = None
                self.file_info_var.set("Aucun fichier sélectionné")
                self.clear_treeviews()
                self.transfer_btn.config(state=DISABLED)
                self.transfer_back_btn.config(state=DISABLED)
                self.delete_btn.config(state=DISABLED)
            except Exception as e:
                messagebox.showerror("Erreur", f"Échec de la suppression:\n{str(e)}")

    # -----------------------
    # Transfer action
    # -----------------------
    def confirm_selected_file(self):
        """Move the selected unconfirmed file into the confirmed folder."""
        if not self.current_file_path or self.current_file_source != "unconfirmed":
            messagebox.showwarning(
                "Sélection requise",
                "Veuillez sélectionner un fichier non-vérifié à confirmer.",
            )
            return

        dest = os.path.join(self.confirmed_dir, os.path.basename(self.current_file_path))
        try:
            os.makedirs(self.confirmed_dir, exist_ok=True)
            os.replace(self.current_file_path, dest)
            messagebox.showinfo("Confirmé", "Confirmer cette distribution?")
            self.on_period_select(None)
            self.current_file_path = None
            self.current_file_source = None
            self.file_info_var.set("Aucun fichier sélectionné")
            self.clear_treeviews()
            self.transfer_btn.config(state=DISABLED)
            self.transfer_back_btn.config(state=DISABLED)
            self.delete_btn.config(state=DISABLED)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec du transfert:\n{e}")

    def unconfirm_selected_file(self):
        """Move the selected confirmed file back into the unconfirmed folder."""
        if not self.current_file_path or self.current_file_source != "confirmed":
            messagebox.showwarning(
                "Sélection requise",
                "Veuillez sélectionner un fichier confirmé à retourner.",
            )
            return

        dest = os.path.join(self.unconfirmed_dir, os.path.basename(self.current_file_path))
        try:
            os.makedirs(self.unconfirmed_dir, exist_ok=True)
            os.replace(self.current_file_path, dest)
            messagebox.showinfo("Retourné", "Fichier déplacé vers NON-vérifiés.")
            self.on_period_select(None)
            self.current_file_path = None
            self.current_file_source = None
            self.file_info_var.set("Aucun fichier sélectionné")
            self.clear_treeviews()
            self.transfer_btn.config(state=DISABLED)
            self.transfer_back_btn.config(state=DISABLED)
            self.delete_btn.config(state=DISABLED)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec du transfert:\n{e}")

    # -----------------------
    # Helpers for period info
    # -----------------------
    def _resolve_selected_pay_period_label(self) -> str:
        """Return the currently selected pay period label from the combobox."""
        return (self.pay_period_var.get() or "").strip()

    def _resolve_selected_pay_period_path(self) -> str:
        """
        Resolve the selected pay period folder using the label->path map.
        """
        label = self._resolve_selected_pay_period_label()
        if not label:
            raise RuntimeError("Aucune période sélectionnée.")

        # Prefer the cached path set by on_period_select
        if self.current_period_path:
            return self.current_period_path

        # Fall back to the map or base_dir + label
        path = self.period_paths.get(label) or os.path.join(self.base_dir, label)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Dossier introuvable: {path}")
        return path

    # -----------------------
    # Combine action
    # -----------------------
    def on_create_combined_file(self):
        """
        Handler for the 'Créer fichier combiné' button.

        It combines all *.json distributions from the selected backend period folder and writes:
         {backend}/pay/{pay_period}/combined.Json


        (No JSONs are written outside the app folder.)
        """
        period_label = self._resolve_selected_pay_period_label()
        if not period_label:
            messagebox.showerror("Erreur", "Veuillez sélectionner une période de paye.")
            return

        try:
            pay_period_path = self._resolve_selected_pay_period_path()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de localiser le dossier de la période:\n{e}")
            return

        try:
            out_path = self._combine_all_jsons_in_period(pay_period_path, period_label)
            messagebox.showinfo("Succès", f"Fichier combiné créé:\n{out_path}")
            # Refresh the list (we're browsing per-day JSONs; combined lives elsewhere)
            self.on_period_select(None)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de la création du fichier combiné:\n{e}")

    def _combine_all_jsons_in_period(self, pay_period_path: str, pay_period_label: str) -> str:
        """
        Combine every *.json file in the selected backend pay-period folder into:
            {backend}/pay/{pay_period_label}/combined.Json

        The result contains:
            {
              "pay_period": "...",
              "created_at": "...",
              "num_files": N,
              "distributions": [
                {"filename": "...", "content": {...}} or {"filename": "...", "error": "..."}
              ]
            }

        Returns the absolute output file path.
        """
        if not os.path.isdir(pay_period_path):
            raise FileNotFoundError(f"Dossier introuvable: {pay_period_path}")

        confirmed_dir = os.path.join(pay_period_path, "confirmed")
        if not os.path.isdir(confirmed_dir):
            raise FileNotFoundError(f"Dossier introuvable: {confirmed_dir}")

        out_dir = os.path.join(self.pay_root, pay_period_label)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "combined.Json")

        # Gather candidates from the confirmed folder
        all_jsons = sorted(
            p for p in glob.glob(os.path.join(confirmed_dir, "*.json"))
            if os.path.isfile(p)
        )

        # Exclude any known aggregate/final files if they exist inside the folder
        excluded_names = {"combined.Json", f"{pay_period_label}_pay_data.json"}
        jsons_to_merge = [p for p in all_jsons if os.path.basename(p) not in excluded_names]

        combined = {
            "pay_period": pay_period_label,
            "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "num_files": len(jsons_to_merge),
            "distributions": []
        }

        for p in jsons_to_merge:
            entry = {"filename": os.path.basename(p)}
            try:
                with open(p, "r", encoding="utf-8") as f:
                    entry["content"] = json.load(f)
            except Exception as e:
                entry["error"] = f"{type(e).__name__}: {e}"
            combined["distributions"].append(entry)

        # Atomic write
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)

        return out_path
