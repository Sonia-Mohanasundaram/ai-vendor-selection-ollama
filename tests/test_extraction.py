from __future__ import annotations

import unittest

from core.extraction import extract_fields
from core.normalization import normalize


class AdditionalChargeExtractionTests(unittest.TestCase):
    def test_missing_fields_are_not_filled_with_numeric_defaults(self) -> None:
        fields = extract_fields(
            "Vendor: Acme\nPayment Terms: Net 45 days",
            "quotation.pdf",
        )
        self.assertIsNone(fields["quantity"])
        self.assertIsNone(fields["unit_price"])
        self.assertIsNone(fields["gst_percent"])
        self.assertIsNone(fields["currency"])
        self.assertIsNone(fields["delivery_days"])
        self.assertIn("quantity", fields["missing_fields"])
        self.assertIn("unit_price", fields["missing_fields"])

    def test_payment_net_days_are_not_read_as_delivery_days(self) -> None:
        fields = extract_fields(
            "Vendor: Acme\nPayment Terms: Net 45 days",
            "quotation.pdf",
        )
        normalized = normalize(fields)
        self.assertEqual(normalized["payment_terms_days"], 45)
        self.assertIsNone(normalized["delivery_days"])

    def test_explicit_zero_is_preserved_as_a_real_value(self) -> None:
        fields = extract_fields(
            "Vendor: Acme\nQuantity: 2\nUnit Price: INR 0\nGST: 0%\nFreight: INR 0\nCurrency: INR",
            "quotation.pdf",
        )
        normalized = normalize(fields)
        self.assertEqual(normalized["unit_price"], 0)
        self.assertEqual(normalized["gst_percent"], 0)
        self.assertEqual(normalized["freight_cost"], 0)

    def test_not_applicable_charge_is_distinguished_from_unreported_charge(self) -> None:
        fields = extract_fields(
            "Vendor: Acme\nCurrency: INR\nFreight: Not applicable",
            "quotation.pdf",
        )
        normalized = normalize(fields)
        self.assertEqual(normalized["freight_cost"], 0)
        self.assertEqual(normalized["field_status"]["freight_cost"], "not_applicable")
        self.assertEqual(normalized["field_status"]["other_taxes"], "not_provided")

    def test_unparseable_source_value_is_marked_unknown(self) -> None:
        fields = extract_fields("Vendor: Acme\nQuantity: many", "quotation.pdf")
        self.assertIn("quantity", fields["missing_fields"])
        self.assertEqual(fields["field_status"]["quantity"], "unknown")

    def test_gst_at_rate_and_split_cgst_sgst_are_normalized_correctly(self) -> None:
        self.assertEqual(extract_fields("Vendor: Acme\nGST @18% applicable")["gst_percent"], 18)
        split = extract_fields("Vendor: Acme\nCGST: 9%\nSGST: 9%")
        self.assertEqual(split["gst_percent"], 18)

    def test_indian_currency_grouping_is_parsed(self) -> None:
        fields = extract_fields(
            "Vendor: Acme\nCurrency: INR\nQuantity: 2\nUnit Price: Rs. 1,23,456.75",
            "quotation.pdf",
        )
        normalized = normalize(fields)
        self.assertEqual(normalized["unit_price"], 123456.75)

    def test_unlabeled_vendor_heading_is_shown_as_heuristic_not_missing(self) -> None:
        fields = extract_fields("SSN Office Solutions\nQuotation\nItem: Printer")
        self.assertEqual(fields["vendor_name"], "SSN Office Solutions")
        self.assertNotIn("vendor_name", fields["missing_fields"])
        self.assertEqual(fields["extraction_confidence"]["vendor_name"], "heuristic")
        normalized = normalize(fields)
        self.assertTrue(any("inferred from an unlabeled" in warning for warning in normalized["data_warnings"]))

    def test_extracts_explicit_other_tax_and_additional_charge_amounts(self) -> None:
        fields = extract_fields(
            "Acme quotation\nOther tax: ₹200\nAdditional charges: ₹500",
            "acme.pdf",
        )
        normalized = normalize(fields)
        self.assertEqual(normalized["other_taxes"], 200)
        self.assertEqual(normalized["additional_charges"], 500)
        self.assertNotIn("other_taxes", normalized["missing_fields"])
        self.assertNotIn("additional_charges", normalized["missing_fields"])

    def test_tax_rate_alone_is_not_misread_as_other_tax_amount(self) -> None:
        fields = extract_fields("Acme quotation\nAdditional tax: 5%", "acme.pdf")
        self.assertIn("other_taxes", fields["missing_fields"])

    def test_structured_quotation_extracts_extra_cost_columns(self) -> None:
        fields = extract_fields(
            "vendor_name,total_price,gst_percent,freight_cost,other_taxes,additional_charges,currency\n"
            "Acme,1000,18,20,10,5,INR",
            "acme.csv",
        )
        self.assertEqual(fields["other_taxes"], 10)
        self.assertEqual(fields["additional_charges"], 5)

    def test_ambiguous_unit_and_tax_amount_columns_are_not_misread_as_price(self) -> None:
        fields = extract_fields(
            "vendor_name,unit,quantity,gst_amount\nAcme,1.0,10,180",
            "acme.csv",
        )
        self.assertIsNone(fields["unit_price"])
        self.assertIsNone(fields["total_price"])
        self.assertEqual(fields["gst_amount"], 180)
        self.assertIn("unit_price", fields["missing_fields"])


if __name__ == "__main__":
    unittest.main()
