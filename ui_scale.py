"""Utility functions for DPI-aware UI scaling.

Call :func:`init_scaling` once after creating the ``Tk`` root to
configure Tk's internal scaling based on the system's DPI. Afterwards,
use :func:`scale` to multiply pixel values so that widgets have a
consistent physical size across displays.
"""

import sys

_ui_scale = 1.0


def enable_high_dpi_awareness():
    """Opt the process into DPI awareness on Windows."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def init_scaling(root):
    """Initialize global scaling based on the display's DPI.

    Tk's default assumes a 72-DPI display.  Modern high-density
    displays often report much higher values, so we derive separate
    scaling factors for Tk's internal units and for any explicit pixel
    values used by the program.  Pixel measurements are scaled relative
    to a 96-DPI baseline and clamped to at least ``1.0`` to avoid tiny
    UIs on low-density screens.

    Some packaged releases inadvertently inherit a non-default Tk
    scaling value from the build environment, resulting in an
    over-zoomed interface on normal displays.  To counter this we first
    read Tk's *current* scaling, compute the physical DPI, and only then
    apply our own scaling relative to the actual display DPI.
    """

    global _ui_scale
    try:
        # Obtain current Tk scaling (pixels per point).  Some frozen
        # builds may already have this set to a high value which would
        # otherwise compound our own scaling.
        current = float(root.tk.call("tk", "scaling"))

        # Determine the actual display DPI by removing Tk's existing
        # scaling factor.  ``winfo_fpixels('1i')`` returns the number of
        # pixels for one inch at the *current* scaling.
        dpi = root.winfo_fpixels("1i")
        if current > 0:
            dpi /= current

        # Tk's ``scaling`` is expressed in pixels per typographical
        # point (1/72\").  Use the physical DPI to derive the correct
        # value for fonts and other units, clamping to at least 1.0 so
        # we never shrink the UI below the 72-DPI baseline.
        tk_scale = max(1.0, dpi / 72.0) if dpi > 0 else current

        # Compute our own geometry scaling relative to the more common
        # 96-DPI desktop baseline.  This is used by :func:`scale` for any
        # explicit pixel measurements.
        _ui_scale = max(1.0, dpi / 96.0) if dpi > 0 else 1.0

        # Only apply the Tk scaling if it differs meaningfully from the
        # existing value to avoid compounding adjustments.
        if abs(current - tk_scale) > 0.01:
            root.tk.call("tk", "scaling", tk_scale)

        # Allow manual override from configuration (0 => auto)
        try:
            from AppConfig import get_ui_scale as _get_ui_scale
            override = float(_get_ui_scale())
        except Exception:
            override = 0.0
        if override and override > 0:
            _ui_scale = override
            root.tk.call("tk", "scaling", max(0.1, _ui_scale * (96.0 / 72.0)))
    except Exception:
        _ui_scale = 1.0
    return _ui_scale


def scale(value):
    """Scale the given pixel value using the configured DPI factor."""
    try:
        return int(value * _ui_scale)
    except Exception:
        return int(value)
