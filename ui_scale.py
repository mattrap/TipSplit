"""Utility functions for DPI-aware UI scaling.

Call init_scaling(root) once after creating the Tk root to configure
Tk's internal scaling based on the system's DPI.  Afterwards, use
scale(value) to multiply pixel values so that widgets have a consistent
physical size across displays.
"""

_ui_scale = 1.0


def init_scaling(root):
    """Initialize global scaling based on the display's DPI."""
    global _ui_scale
    try:
        # Tk uses pixels per point (1/72 inch) for its internal scaling.
        # Query the number of pixels per inch and derive a scale factor.
        dpi = root.winfo_fpixels("1i")
        _ui_scale = dpi / 72.0 if dpi > 0 else 1.0
        root.tk.call("tk", "scaling", _ui_scale)
    except Exception:
        _ui_scale = 1.0
    return _ui_scale


def scale(value):
    """Scale the given pixel value using the configured DPI factor."""
    try:
        return int(value * _ui_scale)
    except Exception:
        return int(value)
