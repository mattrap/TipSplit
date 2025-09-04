"""Utility functions for DPI-aware UI scaling.

Call :func:`init_scaling` once after creating the ``Tk`` root to
configure Tk's internal scaling based on the system's DPI. Afterwards,
use :func:`scale` to multiply pixel values so that widgets have a
consistent physical size across displays.
"""

_ui_scale = 1.0


def init_scaling(root):
    """Initialize global scaling based on the display's DPI.

    Tk's default assumes a 96-DPI display.  Modern high-density
    displays often report much higher values, so we derive a scale
    factor relative to that baseline and clamp to at least ``1.0`` to
    avoid tiny UIs on low-density screens.
    """

    global _ui_scale
    try:
        # Query the number of pixels per inch and derive a scale factor
        # relative to the standard 72 DPI baseline used by most desktop
        # environments.
        dpi = root.winfo_fpixels("1i")
        _ui_scale = max(1.0, dpi / 72.0) if dpi > 0 else 1.0
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
