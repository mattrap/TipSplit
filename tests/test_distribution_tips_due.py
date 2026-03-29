import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import Distribution as distribution_module


class _FakeEntry:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class DistributionTipsDueTests(unittest.TestCase):
    def _make_tab(self, tips_due_value, depot_net="0", cash="200"):
        tab = distribution_module.DistributionTab.__new__(distribution_module.DistributionTab)
        tab.fields = {
            "Ventes Nettes": _FakeEntry("1000"),
            "Dépot Net": _FakeEntry(depot_net),
            "Frais Admin": _FakeEntry("10"),
            "Cash": _FakeEntry(cash),
        }
        tab.declaration_fields = {
            "Ventes Totales": _FakeEntry("1000"),
            "Clients": _FakeEntry("10"),
            "Tips due": _FakeEntry(tips_due_value),
            "Ventes Nourriture": _FakeEntry("300"),
        }
        tab.inputs_valid = lambda: True
        tab.get_active_pay_period = lambda: {"id": "period-1"}
        return tab

    def test_get_declaration_inputs_turns_negative_tips_due_positive_for_calculation(self):
        tab = self._make_tab("-150")

        _ventes_totales, _clients, tips_due, _ventes_nourriture = tab.get_declaration_inputs()

        self.assertEqual(tips_due, 150.0)

    def test_get_declaration_inputs_turns_positive_tips_due_negative_for_calculation(self):
        tab = self._make_tab("120")

        _ventes_totales, _clients, tips_due, _ventes_nourriture = tab.get_declaration_inputs()

        self.assertEqual(tips_due, -120.0)

    def test_get_declaration_inputs_supports_comma_decimal(self):
        tab = self._make_tab("-120,5")

        _ventes_totales, _clients, tips_due, _ventes_nourriture = tab.get_declaration_inputs()

        self.assertEqual(tips_due, 120.5)

    def test_confirm_export_prompts_for_positive_tips_due_before_final_confirmation(self):
        tab = self._make_tab("120")

        with patch.object(distribution_module.messagebox, "askyesno", side_effect=[False]) as askyesno, \
             patch.object(distribution_module, "export_distribution_from_tab") as export_mock:
            tab.confirm_export()

        self.assertEqual(askyesno.call_count, 1)
        self.assertEqual(
            askyesno.call_args_list[0].args,
            (
                "Confirmation",
                "Êtes vous sûrs que la valeur TIPS DUE à entrer est '120' et non '-120'",
            ),
        )
        export_mock.assert_not_called()

    def test_confirm_export_skips_warning_for_negative_tips_due_and_exports_after_final_confirmation(self):
        tab = self._make_tab("-150")

        with patch.object(distribution_module.messagebox, "askyesno", side_effect=[True]) as askyesno, \
             patch.object(distribution_module, "export_distribution_from_tab") as export_mock:
            tab.confirm_export()

        self.assertEqual(
            askyesno.call_args_list[0].args,
            ("Confirmation", "Êtes-vous sûr que la distribution est complète ?"),
        )
        export_mock.assert_called_once_with(tab)

    def test_confirm_export_prompts_when_cash_is_not_greater_than_positive_depot(self):
        tab = self._make_tab("-150", depot_net="100", cash="50")

        with patch.object(distribution_module.messagebox, "askyesno", side_effect=[False]) as askyesno, \
             patch.object(distribution_module, "export_distribution_from_tab") as export_mock:
            tab.confirm_export()

        self.assertEqual(askyesno.call_count, 1)
        self.assertEqual(
            askyesno.call_args_list[0].args,
            (
                "Confirmation",
                "Vous ne pouvez pas avoir seulement 50$ cash avec un dépot positif de 100$",
            ),
        )
        export_mock.assert_not_called()

    def test_confirm_export_can_continue_after_cash_and_positive_depot_warning(self):
        tab = self._make_tab("-150", depot_net="100", cash="50")

        with patch.object(distribution_module.messagebox, "askyesno", side_effect=[True, True]) as askyesno, \
             patch.object(distribution_module, "export_distribution_from_tab") as export_mock:
            tab.confirm_export()

        self.assertEqual(
            askyesno.call_args_list[0].args,
            (
                "Confirmation",
                "Vous ne pouvez pas avoir seulement 50$ cash avec un dépot positif de 100$",
            ),
        )
        self.assertEqual(
            askyesno.call_args_list[1].args,
            ("Confirmation", "Êtes-vous sûr que la distribution est complète ?"),
        )
        export_mock.assert_called_once_with(tab)


if __name__ == "__main__":
    unittest.main()
