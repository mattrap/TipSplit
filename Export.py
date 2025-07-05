from datetime import datetime, timedelta

def get_pay_period(current_dt):
    known_start = datetime(2025, 6, 8, 6, 0)
    delta = current_dt - known_start
    total_seconds = delta.total_seconds()
    period_seconds = 14 * 24 * 3600  # 2 weeks

    period_index = int(total_seconds // period_seconds)
    period_start = known_start + timedelta(seconds=period_index * period_seconds)
    period_end = period_start + timedelta(days=13, hours=23, minutes=59)

    return period_start.strftime("%d/%m/%Y"), period_end.strftime("%d/%m/%Y")

def export_distribution_from_tab(distribution_tab):
    """
    Full export process based on the state of a DistributionTab instance.
    """
    from tkinter import messagebox
    import os

    date = distribution_tab.selected_date_str
    shift = distribution_tab.shift_var.get().upper()

    if not date or not shift:
        messagebox.showerror("Erreur", "Assurez-vous de sélectionner une date et un shift.")
        return

    try:
        ventes_net, depot_net, frais_admin, cash = distribution_tab.get_inputs()

        entries = []
        for item in distribution_tab.tree.get_children():
            values = distribution_tab.tree.item(item)["values"]
            if values[0] and values[1]:
                try:
                    entries.append({
                        "employee_id": int(values[0]),
                        "name": values[1],
                        "section": "Service" if "Service" in values[1] else "Bussboy",
                        "hours": float(values[3]),
                        "cash": float(values[4]),
                        "sur_paye": float(values[5]),
                        "frais_admin": float(values[6])
                    })
                except Exception:
                    continue

        export_distribution_summary(
            base_dir=os.getcwd(),
            date=date,
            shift=shift,
            fields={
                "Ventes Nettes": ventes_net,
                "Dépot Net": depot_net,
                "Frais Admin": frais_admin,
                "Cash": cash
            },
            entries=entries
        )

        messagebox.showinfo("Exporté", "Les données ont été exportées avec succès.")
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec de l'exportation:\n{e}")

