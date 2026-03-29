import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

access_control_stub = types.ModuleType("access_control")


class _AccessController:
    email = ""


class _AccessError(Exception):
    pass


access_control_stub.AccessController = _AccessController
access_control_stub.AccessError = _AccessError
sys.modules.setdefault("access_control", access_control_stub)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from MainApp import TipSplitApp


class _FakeFrame:
    def __init__(self, tab_id):
        self.tab_id = tab_id
        self.state = {}

    def __str__(self):
        return self.tab_id


class _FakeNotebook:
    def __init__(self):
        self.visible_tabs = []
        self.hidden_tabs = set()
        self.tab_options = {}
        self.add_calls = []
        self.hide_calls = []
        self.selected = None

    def add(self, frame, **kwargs):
        key = str(frame)
        if key not in self.visible_tabs:
            self.visible_tabs.append(key)
        self.hidden_tabs.discard(key)
        self.tab_options.setdefault(key, {}).update(kwargs)
        self.add_calls.append(frame)
        if self.selected is None:
            self.selected = key

    def hide(self, frame):
        key = str(frame)
        if key in self.visible_tabs:
            self.visible_tabs.remove(key)
        self.hidden_tabs.add(key)
        self.hide_calls.append(frame)
        if self.selected == key:
            self.selected = self.visible_tabs[0] if self.visible_tabs else None

    def tabs(self):
        return list(self.visible_tabs)

    def tab(self, frame, option=None, **kwargs):
        key = str(frame)
        if option is not None:
            return self.tab_options.get(key, {}).get(option)
        if kwargs:
            self.tab_options.setdefault(key, {}).update(kwargs)
            return None
        return dict(self.tab_options.get(key, {}))

    def select(self, frame=None):
        if frame is None:
            return self.selected
        self.selected = str(frame)


class _FakeButton:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


class TipSplitAppTabTests(unittest.TestCase):
    def _make_app(self):
        app = TipSplitApp.__new__(TipSplitApp)
        app.notebook = _FakeNotebook()
        app._ensure_tab_management_state()
        return app

    def test_menu_opened_tabs_are_marked_closeable(self):
        app = self._make_app()
        frame = _FakeFrame(".pay")

        app._register_tab(frame, text="Pay", closeable=True, hidden=True)

        self.assertTrue(app.is_tab_closeable(frame))
        self.assertEqual(app._frame_from_tab_id(str(frame)), frame)

    def test_fixed_tabs_are_not_closeable(self):
        app = self._make_app()
        frame = _FakeFrame(".distribution")

        app._register_tab(frame, text="Distribution", closeable=False)

        self.assertFalse(app.is_tab_closeable(frame))

    def test_close_tab_hides_closeable_tab(self):
        app = self._make_app()
        frame = _FakeFrame(".analyse")
        app._register_tab(frame, text="Analyse", closeable=True)

        closed = app.close_tab(frame)

        self.assertTrue(closed)
        self.assertEqual(app.notebook.hide_calls, [frame])
        self.assertNotIn(str(frame), app.notebook.tabs())

    def test_show_registered_tab_reopens_same_frame_instance(self):
        app = self._make_app()
        frame = _FakeFrame(".json")
        frame.state["filter"] = "pending"
        app._register_tab(frame, text="Confirmer les distribution", closeable=True, hidden=True)

        app._show_registered_tab(frame)

        self.assertIn(str(frame), app.notebook.tabs())
        self.assertEqual(app.notebook.selected, str(frame))
        self.assertIs(app._frame_from_tab_id(str(frame)), frame)
        self.assertEqual(frame.state["filter"], "pending")

    def test_show_pay_calendar_tab_refreshes_existing_tab_when_reopened(self):
        app = self._make_app()
        app.ensure_payroll_setup_done = lambda: True
        app.pay_calendar_frame = _FakeFrame(".calendar")
        app.pay_calendar_tab = type("CalendarTab", (), {"refresh_periods": Mock()})()
        app._register_tab(
            app.pay_calendar_frame,
            text="Calendrier de paie",
            closeable=True,
            hidden=True,
        )

        app.show_pay_calendar_tab()

        self.assertIn(str(app.pay_calendar_frame), app.notebook.tabs())
        self.assertEqual(app.notebook.selected, str(app.pay_calendar_frame))
        app.pay_calendar_tab.refresh_periods.assert_called_once_with()

    def test_close_button_disables_for_fixed_tab(self):
        app = self._make_app()
        app.close_tab_button = _FakeButton()
        frame = _FakeFrame(".distribution")
        app._register_tab(frame, text="Distribution", closeable=False)

        app._update_close_tab_button()

        self.assertEqual(app.close_tab_button.state, "disabled")

    def test_close_button_enables_for_menu_tab(self):
        app = self._make_app()
        app.close_tab_button = _FakeButton()
        frame = _FakeFrame(".pay")
        app._register_tab(frame, text="Pay", closeable=True)
        app.notebook.select(frame)

        app._update_close_tab_button()

        self.assertEqual(app.close_tab_button.state, "normal")


if __name__ == "__main__":
    unittest.main()
