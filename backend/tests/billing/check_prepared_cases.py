#!/usr/bin/env python3
"""Check prepared fixture expectations with the planning oracle, not the app."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CASES_FILE = Path(__file__).with_name("pricing_cases.json")


def reject_float(value: str) -> None:
    raise ValueError(f"Fixture contains a JSON floating-point number: {value}")


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(), parse_float=reject_float)["cases"]


def load_reference():
    spec = importlib.util.spec_from_file_location(
        "cadentra_planning_reference", ROOT / "scripts/check_pack.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Planning reference calculator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.calculate


class PreparedPricingCases(unittest.TestCase):
    """Executable fixture checks; actual-service acceptance follows Gate A."""

    def test_expected_totals_match_planning_reference(self):
        calculate = load_reference()
        cases = load_cases(ROOT / "contracts/billing-vectors.json") + load_cases(CASES_FILE)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                before = deepcopy(case)
                self.assertEqual(calculate(case), case["expected"])
                self.assertEqual(case, before, "Reference check mutated a fixture")

    def test_line_order_does_not_change_discount_assignment(self):
        calculate = load_reference()
        case = next(
            case
            for case in load_cases(CASES_FILE)
            if case["id"] == "remainder_tie_uses_key_not_input_order"
        )
        original = calculate(case)
        reordered = deepcopy(case)
        reordered["lines"].reverse()
        actual = calculate(reordered)
        for key in ("subtotal", "discount", "tax", "total"):
            self.assertEqual(original[key], actual[key])
        original_allocations = dict(
            zip((line["key"] for line in case["lines"]), original["line_discounts"], strict=True)
        )
        reordered_allocations = dict(
            zip((line["key"] for line in reordered["lines"]), actual["line_discounts"], strict=True)
        )
        self.assertEqual(original_allocations, reordered_allocations)

    def test_fixture_money_is_finite_decimal_text(self):
        for case in load_cases(CASES_FILE):
            with self.subTest(case=case["id"]):
                amounts = [case["base_fee"], *case["base_tax_rates"]]
                for line in case["lines"]:
                    self.assertIs(type(line["quantity"]), int)
                    self.assertGreater(line["quantity"], 0)
                    amounts.extend([line["price"], line["variant_delta"], *line["tax_rates"]])
                if case["discount"]:
                    amounts.append(case["discount"]["value"])
                expected = case["expected"]
                amounts.extend(expected[key] for key in ("subtotal", "discount", "tax", "total"))
                amounts.extend(expected["line_discounts"])
                for value in amounts:
                    self.assertIsInstance(value, str)
                    self.assertTrue(Decimal(value).is_finite())


if __name__ == "__main__":
    print("Prepared-fixture/reference checks only; no application or database tests.", flush=True)
    unittest.main(verbosity=2)
