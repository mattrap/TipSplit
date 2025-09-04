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

    Some packaged releases inadvertently inherit a non-default Tk
    scaling value from the build environment, resulting in an
    over-zoomed interface on normal displays.  To counter this we first
    read Tk's *current* scaling, compute the physical DPI, and only then
    apply our own scaling relative to the 96-DPI baseline.
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

        # Derive our target scale relative to the standard 96‑DPI
        # baseline used by most desktop environments.
        _ui_scale = max(1.0, dpi / 96.0) if dpi > 0 else 1.0

        # Only apply the scaling if it differs meaningfully from the
        # existing value to avoid compounding adjustments.
        if abs(current - _ui_scale) > 0.01:
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
