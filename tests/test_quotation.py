from __future__ import annotations

import unittest

from core.quotation import to_quotation_evidence


class QuotationEvidenceTests(unittest.TestCase):
    def test_calculates_total_from_extracted_base_gst_and_freight(self) -> None:
        result = to_quotation_evidence(
            {
                "vendor_name": "Acme",
                "item_name": "Pump",
                "quantity": 2,
                "unit_price": 100,
                "total_price": 200,
                "base_cost": 200,
                "gst_percent": 18,
                "freight_cost": 10,
                "other_taxes": 0,
                "additional_charges": 0,
                "currency_original": "INR",
                "delivery_days": 5,
                "payment_terms_days": 30,
                "missing_fields": [],
            },
            "vendor-1",
        )
        self.assertEqual(result["gst_amount"], 36)
        self.assertEqual(result["total_cost"], 246)

    def test_missing_values_stay_unknown_and_no_total_is_invented(self) -> None:
        result = to_quotation_evidence(
            {
                "vendor_name": "Acme",
                "base_cost": 0,
                "gst_percent": 18,
                "freight_cost": 0,
                "other_taxes": 0,
                "additional_charges": 0,
                "currency_original": "INR",
                "delivery_days": 30,
                "payment_terms_days": 30,
                "missing_fields": [
                    "total_price",
                    "freight_cost",
                    "delivery_days",
                    "payment_terms_days",
                ],
            },
            "vendor-1",
        )
        self.assertIsNone(result["base_amount"])
        self.assertIsNone(result["freight"])
        self.assertIsNone(result["delivery_days"])
        self.assertIsNone(result["payment_days"])
        self.assertIsNone(result["total_cost"])

    def test_explicit_quoted_total_is_preserved_without_recalculating_it(self) -> None:
        result = to_quotation_evidence(
            {
                "quoted_total": 623770,
                "currency_original": "INR",
                "missing_fields": ["quantity", "unit_price", "freight_cost"],
            },
            "vendor-1",
        )
        self.assertEqual(result["quoted_total"], 623770)
        self.assertEqual(result["total_cost"], 623770)
        self.assertIsNone(result["calculated_total"])

    def test_conflicting_quoted_total_is_not_used_as_verified_total(self) -> None:
        result = to_quotation_evidence(
            {
                "total_price": 100,
                "base_cost": 100,
                "gst_percent": 0,
                "gst_amount": 0,
                "freight_cost": 0,
                "other_taxes": 0,
                "additional_charges": 0,
                "quoted_total": 200,
                "currency_original": "INR",
                "missing_fields": [],
            },
            "vendor-1",
        )
        self.assertIsNone(result["total_cost"])
        self.assertFalse(result["total_consistent"])
        self.assertTrue(any("does not equal" in warning for warning in result["data_warnings"]))

    def test_tax_inclusive_total_does_not_add_gst_twice(self) -> None:
        result = to_quotation_evidence(
            {
                "total_price": 118,
                "base_cost": 118,
                "gst_percent": 18,
                "freight_cost": 0,
                "other_taxes": 0,
                "additional_charges": 0,
                "currency_original": "INR",
                "tax_inclusive": True,
                "missing_fields": [],
            },
            "vendor-1",
        )
        self.assertEqual(result["gst_amount"], 18)
        self.assertEqual(result["calculated_total"], 118)
        self.assertEqual(result["total_cost"], 118)

    def test_contradictory_totals_are_flagged(self) -> None:
        result = to_quotation_evidence(
            {
                "vendor_name": "Acme",
                "quantity": 2,
                "unit_price": 100,
                "total_price": 250,
                "base_cost": 250,
                "gst_percent": 18,
                "freight_cost": 0,
                "missing_fields": [],
            },
            "vendor-1",
        )
        self.assertTrue(result["data_warnings"])
        self.assertIn("does not equal", result["data_warnings"][0])

    def test_unknown_currency_invalidates_monetary_comparison(self) -> None:
        result = to_quotation_evidence(
            {
                "vendor_name": "Acme",
                "total_price": 100,
                "base_cost": 100,
                "gst_percent": 18,
                "freight_cost": 0,
                "missing_fields": ["currency"],
            },
            "vendor-1",
        )
        self.assertIsNone(result["base_amount"])
        self.assertIsNone(result["total_cost"])
        self.assertIsNone(result["currency"])
        self.assertTrue(result["data_warnings"])

    def test_unconfigured_currency_is_not_assumed_to_be_inr(self) -> None:
        result = to_quotation_evidence(
            {
                "vendor_name": "Acme",
                "currency": "EUR",
                "currency_original": "EUR",
                "total_price": 100,
                "base_cost": 100,
                "gst_percent": 18,
                "freight_cost": 0,
                "missing_fields": [],
            },
            "vendor-1",
        )
        self.assertIsNone(result["base_amount"])
        self.assertIsNone(result["total_cost"])
        self.assertEqual(result["source_currency"], "EUR")

    def test_missing_vendor_name_is_not_replaced_with_filename(self) -> None:
        result = to_quotation_evidence(
            {
                "vendor_name": "supplier-file-name",
                "source_file": "supplier-file-name.pdf",
                "missing_fields": ["vendor_name"],
            },
            "vendor-1",
        )
        self.assertIsNone(result["vendor_name"])


if __name__ == "__main__":
    unittest.main()
