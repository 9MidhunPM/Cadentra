"""Actual-calculator acceptance: PYTHONPATH=backend python3 -m unittest discover -s backend/tests/billing -p test_pricing.py -v."""
from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal, ROUND_DOWN, localcontext
from pathlib import Path

from app.modules.billing.pricing import PricingLine, SelectedDiscount, calculate_invoice


ROOT = Path(__file__).resolve().parents[3]
ZERO = Decimal("0.00")


def fixture_inputs(case: dict) -> tuple[tuple[PricingLine, ...], SelectedDiscount | None]:
    """Normalize source fixtures to the agreed, already-priced line boundary."""
    lines = [PricingLine(
        stable_line_key="BASE", quantity=1, unit_price=Decimal(case["base_fee"]),
        tax_rates=tuple(Decimal(rate) for rate in case["base_tax_rates"]),
    )]
    lines.extend(PricingLine(
        stable_line_key=line["key"], quantity=line["quantity"],
        unit_price=Decimal(line["price"]) + Decimal(line["variant_delta"]),
        tax_rates=tuple(Decimal(rate) for rate in line["tax_rates"]),
    ) for line in case["lines"])
    rule = case["discount"]
    discount = None if rule is None else SelectedDiscount(
        kind=rule["kind"], value=Decimal(rule["value"]),
        eligible_line_keys=frozenset(rule["eligible_keys"]),
    )
    return tuple(lines), discount


class PricingAcceptanceTests(unittest.TestCase):
    def assert_money(self, amount: Decimal) -> None:
        self.assertIsInstance(amount, Decimal)
        self.assertTrue(amount.is_finite())
        self.assertEqual(amount.as_tuple().exponent, -2)

    def test_all_canonical_and_prepared_vectors(self):
        paths = (
            ROOT / "contracts/billing-vectors.json",
            Path(__file__).with_name("pricing_cases.json"),
        )
        cases = [case for path in paths for case in json.loads(path.read_text())["cases"]]
        self.assertEqual(len(cases), 15)
        for case in cases:
            with self.subTest(case=case["id"]):
                lines, discount = fixture_inputs(case)
                result = calculate_invoice(lines, discount)
                expected = case["expected"]
                for attribute, fixture_key in (
                    ("subtotal", "subtotal"), ("discount_total", "discount"),
                    ("tax_total", "tax"), ("total", "total"),
                ):
                    actual = getattr(result, attribute)
                    self.assert_money(actual)
                    self.assertEqual(actual, Decimal(expected[fixture_key]))
                self.assertIsInstance(result.lines, tuple)
                self.assertEqual(tuple(item.line for item in result.lines), lines)
                expected_discounts = list(expected["line_discounts"])
                # Pack vectors omit the zero-valued base line; DTOs always include it.
                if Decimal(case["base_fee"]) == 0:
                    expected_discounts.insert(0, "0.00")
                self.assertEqual(
                    [item.discount for item in result.lines],
                    [Decimal(amount) for amount in expected_discounts],
                )
                for item in result.lines:
                    self.assertEqual(item.taxable_amount, item.gross - item.discount)
                    self.assertGreaterEqual(item.discount, ZERO)
                    self.assertLessEqual(item.discount, item.gross)
                    self.assertIsInstance(item.tax_amounts, tuple)
                    self.assertEqual(len(item.tax_amounts), len(item.line.tax_rates))
                    self.assertEqual(item.tax_total, sum(item.tax_amounts, ZERO))
                    self.assertEqual(item.total, item.taxable_amount + item.tax_total)
                    for amount in (
                        item.gross, item.discount, item.taxable_amount,
                        item.tax_total, item.total, *item.tax_amounts,
                    ):
                        self.assert_money(amount)
                for attribute in ("discount_total", "tax_total", "total"):
                    line_attribute = "discount" if attribute == "discount_total" else attribute
                    self.assertEqual(
                        getattr(result, attribute),
                        sum((getattr(item, line_attribute) for item in result.lines), ZERO),
                    )
                self.assertEqual(result.subtotal, sum((item.gross for item in result.lines), ZERO))

    def test_remainder_ties_follow_stable_keys_under_permutation(self):
        lines = tuple(PricingLine(key, 1, Decimal("0.05"), (Decimal("10"),))
                      for key in ("Z", "A", "M"))
        discount = SelectedDiscount("FIXED", Decimal("0.01"), frozenset({"Z", "A", "M"}))
        first = calculate_invoice(lines, discount)
        reversed_result = calculate_invoice(tuple(reversed(lines)), discount)
        def allocations(result):
            return {item.line.stable_line_key: item.discount for item in result.lines}

        self.assertEqual(allocations(first), {"Z": ZERO, "A": Decimal("0.01"), "M": ZERO})
        self.assertEqual(allocations(first), allocations(reversed_result))
        self.assertEqual(first.total, reversed_result.total)

    def test_round_half_up_does_not_inherit_ambient_rounding(self):
        with localcontext() as context:
            context.rounding = ROUND_DOWN
            result = calculate_invoice((PricingLine("L1", 1, Decimal("0.05"), (Decimal("10"),)),))
        self.assertEqual(result.lines[0].tax_amounts, (Decimal("0.01"),))
        self.assertEqual(result.total, Decimal("0.06"))

    def test_low_ambient_precision_does_not_change_amounts(self):
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_DOWN
            line = PricingLine("L1", 3, Decimal("1560.00"), (Decimal("18"),))
            rule = SelectedDiscount("PERCENT", Decimal("10"), frozenset({"L1"}))
            result = calculate_invoice((line,), rule)
            self.assertEqual(context.prec, 3)
            self.assertEqual(context.rounding, ROUND_DOWN)
        self.assertEqual(result.total, Decimal("4970.16"))

    def test_amounts_fit_database_money_and_preserve_cents(self):
        maximum = Decimal("9999999999999999.99")
        result = calculate_invoice((PricingLine("L1", 1, maximum),))
        self.assertEqual(result.total, maximum)
        with self.assertRaises(ValueError):
            calculate_invoice((PricingLine("L1", 2, maximum),))
        with self.assertRaises(ValueError):
            calculate_invoice((PricingLine("L1", 1, maximum), PricingLine("L2", 1, maximum)))
        with self.assertRaises(ValueError):
            PricingLine("L1", 1, Decimal("0.001"))

    def test_negative_zero_is_normalized(self):
        result = calculate_invoice((PricingLine("L1", 1, Decimal("-0.00")),))
        self.assertEqual(str(result.lines[0].gross), "0.00")
        self.assertEqual(str(result.total), "0.00")

    def test_percentages_respect_stored_rate_precision(self):
        # Unlimited precision can round onto a half-cent before quantization.
        beyond_storage = Decimal("9." + "9" * 60)
        with self.assertRaises(ValueError):
            PricingLine("L1", 1, Decimal("0.05"), (beyond_storage,))
        with self.assertRaises(ValueError):
            SelectedDiscount("PERCENT", beyond_storage, frozenset({"L1"}))
        line = PricingLine("L1", 1, Decimal("0.05"), (Decimal("9.9999"),))
        self.assertEqual(calculate_invoice((line,)).tax_total, ZERO)
        rule = SelectedDiscount("PERCENT", Decimal("9.9999"), frozenset({"L1"}))
        self.assertEqual(calculate_invoice((line,), rule).discount_total, ZERO)

    def test_multiple_tax_amounts_are_rounded_separately(self):
        result = calculate_invoice((PricingLine(
            "L1", 1, Decimal("0.05"), (Decimal("10"), Decimal("10")),
        ),))
        self.assertEqual(result.lines[0].tax_amounts, (Decimal("0.01"), Decimal("0.01")))
        self.assertEqual(result.tax_total, Decimal("0.02"))
        self.assertEqual(result.total, Decimal("0.07"))

    def test_zero_eligible_gross_never_divides_or_creates_discount(self):
        lines = (PricingLine("FREE", 1, ZERO, (Decimal("18"),)),)
        discount = SelectedDiscount("FIXED", Decimal("50"), frozenset({"FREE"}))
        result = calculate_invoice(lines, discount)
        self.assertEqual(result.discount_total, ZERO)
        self.assertEqual(result.total, ZERO)

    def test_inputs_and_results_are_immutable(self):
        line = PricingLine("L1", 2, Decimal("10.00"), (Decimal("18"),))
        discount = SelectedDiscount("PERCENT", Decimal("10"), frozenset({"L1"}))
        original = (line.quantity, line.unit_price, line.tax_rates, discount.value, discount.eligible_line_keys)
        result = calculate_invoice((line,), discount)
        self.assertEqual(
            (line.quantity, line.unit_price, line.tax_rates, discount.value, discount.eligible_line_keys), original,
        )
        for instance, attribute, replacement in (
            (line, "quantity", 99), (discount, "value", ZERO),
            (result, "total", ZERO), (result.lines[0], "discount", ZERO),
        ):
            with self.subTest(type=type(instance).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(instance, attribute, replacement)

    def test_invalid_line_values_are_rejected(self):
        invalid = (
            {"stable_line_key": ""}, {"quantity": 0}, {"quantity": -1},
            {"quantity": True}, {"quantity": Decimal("1")}, {"quantity": 1.5},
            {"unit_price": 0.1}, {"unit_price": Decimal("-0.01")},
            {"unit_price": Decimal("NaN")}, {"unit_price": Decimal("Infinity")},
            {"tax_rates": (0.1,)}, {"tax_rates": (Decimal("-0.01"),)},
            {"tax_rates": (Decimal("100.01"),)}, {"tax_rates": (Decimal("NaN"),)},
            {"tax_rates": (Decimal("Infinity"),)},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                values = dict(stable_line_key="L1", quantity=1, unit_price=Decimal("1.00"), tax_rates=())
                values.update(changes)
                with self.assertRaises(ValueError):
                    calculate_invoice((PricingLine(**values),))

    def test_duplicate_keys_are_rejected(self):
        line = PricingLine("L1", 1, Decimal("1.00"), ())
        with self.assertRaises(ValueError):
            calculate_invoice((line, line))

    def test_invalid_selected_discounts_are_rejected(self):
        line = PricingLine("L1", 1, Decimal("100.00"), ())
        invalid = (
            {"kind": "OTHER"}, {"value": 0.1}, {"value": Decimal("-0.01")},
            {"value": Decimal("NaN")}, {"value": Decimal("Infinity")},
            {"kind": "PERCENT", "value": Decimal("100.01")},
            {"eligible_line_keys": frozenset({"MISSING"})},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                values = dict(kind="FIXED", value=Decimal("1.00"), eligible_line_keys=frozenset({"L1"}))
                values.update(changes)
                with self.assertRaises(ValueError):
                    calculate_invoice((line,), SelectedDiscount(**values))


if __name__ == "__main__":
    unittest.main(verbosity=2)
