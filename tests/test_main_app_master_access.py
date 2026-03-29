import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *_args, **_kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

supabase_stub = types.ModuleType("supabase")
supabase_stub.Client = object
supabase_stub.create_client = lambda *_args, **_kwargs: object()
sys.modules.setdefault("supabase", supabase_stub)

import MainApp


class _FakeFrame:
    _counter = 0

    def __init__(self, _parent=None, **_kwargs):
        type(self)._counter += 1
        self._name = f"frame-{type(self)._counter}"

    def __str__(self):
        return self._name


class _FakeNotebook:
    def __init__(self, _root):
        self._tabs = []
        self.selected = None
        self.states = {}

    def pack(self, **_kwargs):
        return None

    def add(self, frame, text=""):
        frame_name = str(frame)
        if frame_name not in self._tabs:
            self._tabs.append(frame_name)
        self.states.setdefault(frame_name, {"text": text, "state": "normal"})
        self.states[frame_name]["text"] = text

    def tabs(self):
        return list(self._tabs)

    def select(self, frame):
        self.selected = str(frame)

    def tab(self, frame, state=None):
        if state is not None:
            self.states.setdefault(str(frame), {})["state"] = state


class _FakeLabel:
    def __init__(self, *_args, **_kwargs):
        pass

    def pack(self, **_kwargs):
        return None


class _FakeStringVar:
    def __init__(self, value=""):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


class _FakeRoot:
    def __init__(self):
        self.title_text = None
        self.geometry_value = None
        self.after_calls = []

    def title(self, value):
        self.title_text = value

    def update_idletasks(self):
        return None

    def winfo_screenwidth(self):
        return 1440

    def winfo_screenheight(self):
        return 900

    def geometry(self, value):
        self.geometry_value = value

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))


class _FakeController:
    email = "manager@example.com"


class _FakePayrollContext:
    def __init__(self, _service):
        pass

    def refresh_schedule(self):
        return {"id": "schedule-1"}

    def ensure_window(self):
        return None


class MainAppMasterAccessTests(unittest.TestCase):
    def test_startup_does_not_create_master_tab(self):
        root = _FakeRoot()
        controller = _FakeController()

        def fake_create_timesheet_tab(app_self):
            app_self.timesheet_frame = _FakeFrame(app_self.notebook)
            app_self.timesheet_tab = object()
            app_self.notebook.add(app_self.timesheet_frame, text="Time Sheet")

        def fake_create_distribution_tab(app_self):
            app_self.distribution_frame = _FakeFrame(app_self.notebook)
            app_self.distribution_tab = object()
            app_self.shared_data["distribution_tab"] = app_self.distribution_tab
            app_self.notebook.add(app_self.distribution_frame, text="Distribution")

        with patch.object(MainApp, "init_scaling"), \
             patch.object(MainApp, "fit_to_screen"), \
             patch.object(MainApp, "set_app_icon"), \
             patch.object(MainApp, "ensure_pdf_dir_selected"), \
             patch.object(MainApp, "create_menu_bar"), \
             patch.object(MainApp, "maybe_auto_check"), \
             patch.object(MainApp, "get_payroll_setup_pending", return_value=False), \
             patch.object(MainApp, "PayCalendarService", return_value=object()), \
             patch.object(MainApp, "PayrollContext", _FakePayrollContext), \
             patch.object(MainApp.ttk, "Notebook", _FakeNotebook), \
             patch.object(MainApp.ttk, "Label", _FakeLabel), \
             patch.object(MainApp.tk, "StringVar", _FakeStringVar), \
             patch.object(MainApp.TipSplitApp, "create_timesheet_tab", fake_create_timesheet_tab), \
             patch.object(MainApp.TipSplitApp, "create_distribution_tab", fake_create_distribution_tab):
            app = MainApp.TipSplitApp(root, controller)

        self.assertIsNone(app.master_frame)
        self.assertIsNone(app.master_tab)
        self.assertEqual(len(app.notebook.tabs()), 2)
        self.assertEqual(app.notebook.tabs(), [str(app.timesheet_frame), str(app.distribution_frame)])
        self.assertIn("distribution_tab", app.shared_data)

    def test_authenticate_and_show_master_stops_on_failed_password(self):
        app = MainApp.TipSplitApp.__new__(MainApp.TipSplitApp)
        app.ensure_payroll_setup_done = Mock(return_value=True)
        app.require_manager_password = Mock(return_value=False)
        app.show_master_tab = Mock()

        app.authenticate_and_show_master()

        app.require_manager_password.assert_called_once_with("accéder à la feuille maître")
        app.show_master_tab.assert_not_called()

    def test_show_master_tab_lazy_creates_and_does_not_duplicate(self):
        app = MainApp.TipSplitApp.__new__(MainApp.TipSplitApp)
        app.notebook = _FakeNotebook(None)
        app.ensure_payroll_setup_done = Mock(return_value=True)
        app.shared_data = {}
        app.master_frame = None
        app.master_tab = None
        app.reload_timesheet_data = Mock()

        master_ctor = Mock(side_effect=lambda *args, **kwargs: object())
        with patch.object(MainApp.ttk, "Frame", _FakeFrame), \
             patch.object(MainApp, "MasterSheet", master_ctor):
            app.show_master_tab()
            first_master_tab = app.master_tab
            first_tabs = list(app.notebook.tabs())
            app.show_master_tab()

        self.assertIsNotNone(first_master_tab)
        self.assertEqual(master_ctor.call_count, 1)
        self.assertEqual(len(first_tabs), 1)
        self.assertEqual(app.notebook.tabs(), first_tabs)
        self.assertEqual(app.notebook.selected, str(app.master_frame))

    def test_apply_payroll_setup_gate_handles_missing_master_tab(self):
        app = MainApp.TipSplitApp.__new__(MainApp.TipSplitApp)
        app.notebook = _FakeNotebook(None)
        app.timesheet_frame = _FakeFrame()
        app.distribution_frame = _FakeFrame()
        app.master_frame = None
        app.pay_frame = None
        app.analyse_frame = None
        app.json_viewer_frame = None
        app.show_pay_calendar_tab = Mock()
        app.notebook.add(app.timesheet_frame, text="Time Sheet")
        app.notebook.add(app.distribution_frame, text="Distribution")

        with patch.object(MainApp, "get_payroll_setup_pending", return_value=False):
            app._apply_payroll_setup_gate()

        self.assertEqual(app.notebook.states[str(app.timesheet_frame)]["state"], "normal")
        self.assertEqual(app.notebook.states[str(app.distribution_frame)]["state"], "normal")
        app.show_pay_calendar_tab.assert_not_called()


if __name__ == "__main__":
    unittest.main()
