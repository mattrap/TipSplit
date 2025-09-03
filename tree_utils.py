import ttkbootstrap as ttk

def fit_columns(tree: ttk.Treeview, width_map) -> None:
    """Make treeview columns resize to fit available width.

    Args:
        tree: Treeview widget to adjust.
        width_map: mapping of column name -> base width weight.
    """
    def _resize(event=None):
        columns = tree.cget("displaycolumns")
        # "displaycolumns" returns "#all" when all columns are shown; convert to actual names
        if columns in ("#all", ("#all",)):
            columns = tree.cget("columns")
        if isinstance(columns, str):
            columns = columns.split()
        else:
            columns = list(columns)
        total = sum(width_map.get(col, 1) for col in columns)
        if total <= 0:
            return
        available = tree.winfo_width()
        for col in columns:
            weight = width_map.get(col, 1)
            new_width = max(int(available * weight / total), 20)
            tree.column(col, width=new_width)
    tree.bind("<Configure>", _resize)
    _resize()