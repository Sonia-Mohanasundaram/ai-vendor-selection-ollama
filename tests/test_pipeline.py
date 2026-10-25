from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ai_evaluation import evaluate_vendors, vendor_evaluation_dict
from core.extraction import extract_fields
from core.ingestion import ingest_bytes
from core.normalization import normalize
from core.quotation import to_quotation_evidence


def model_response(vendor_ids: list[str]) -> str:
    return json.dumps(
        {
            "ranked_vendors": [
                {
                    "vendor_id": vendor_id,
                    "rank": index,
                    "recommendation_status": "recommended" if index == 1 else "alternative",
                    "advantages": ["Quotation data is available for comparison."],
                    "disadvantages": [],
                    "cost_comparison": "Cost is shown from the extracted quotation.",
                    "delivery_comparison": "Delivery is shown from the extracted quotation.",
                    "payment_terms_comparison": "Payment terms are shown from the extracted quotation.",
                    "risks": [],
                    "missing_information": [],
                    "explanation": "The ordering reflects the stated requirements.",
                    "confidence_explanation": "Confidence depends on extraction accuracy.",
                }
                for index, vendor_id in enumerate(vendor_ids, start=1)
            ],
            "best_recommendation_vendor_id": vendor_ids[0],
            "alternative_vendor_id": vendor_ids[1],
            "inconclusive": False,
            "overall_explanation": "The leading quotation best fits the requested priorities.",
        }
    )


class QuotationPipelineTests(unittest.TestCase):
    def test_two_csv_quotations_flow_through_extraction_to_ai_evaluation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        filenames = ["vendor_alpha_supplies.csv", "vendor_beta_traders.csv"]
        normalized = []
        for filename in filenames:
            contents = (root / "data" / "sample_quotes" / filename).read_bytes()
            fields = extract_fields(ingest_bytes(contents, filename), filename)
            quote = normalize(fields)
            quote["source_file"] = filename
            normalized.append(quote)
        evidence = [
            to_quotation_evidence(quote, f"vendor-{index}")
            for index, quote in enumerate(normalized, start=1)
        ]

        with patch(
            "core.ai_evaluation._ollama_chat",
            return_value=model_response(["vendor-1", "vendor-2"]),
        ):
            evaluation, warnings = evaluate_vendors(evidence, "Prioritize on-time delivery.")

        self.assertEqual(len(evaluation.ranked_vendors), 2)
        self.assertEqual(evaluation.ranked_vendors[0].vendor_id, "vendor-1")
        self.assertIsNone(evidence[0]["total_cost"])
        self.assertIsNone(evidence[1]["total_cost"])
        self.assertIsNone(evidence[0]["other_taxes"])
        self.assertIsNone(evidence[1]["additional_charges"])
        self.assertFalse(warnings)
        self.assertEqual(vendor_evaluation_dict(evaluation.ranked_vendors[0])["rank"], 1)

    def test_mixed_pdf_and_csv_uploads_preserve_extracted_commercial_fields(self) -> None:
        root = Path(__file__).resolve().parents[1]
        samples = [
            ("sample_alpha.pdf", "Alpha Supplies Pvt Ltd", 50, 52000.0, 10, 30, 10000.0),
            ("vendor_beta_traders.csv", "Beta Traders Co.", 500, 390.0, 20, 15, 6000.0),
        ]
        for filename, vendor_name, quantity, unit_price, delivery, payment, freight in samples:
            with self.subTest(filename=filename):
                contents = (root / "data" / "sample_quotes" / filename).read_bytes()
                fields = extract_fields(ingest_bytes(contents, filename), filename)
                quote = normalize(fields)
                self.assertEqual(quote["vendor_name"], vendor_name)
                self.assertEqual(quote["quantity"], quantity)
                self.assertEqual(quote["unit_price"], unit_price)
                self.assertEqual(quote["delivery_days"], delivery)
                self.assertEqual(quote["payment_terms_days"], payment)
                self.assertEqual(quote["freight_cost"], freight)
                self.assertTrue(quote["extraction_evidence"])

    def test_sample_budget_delivery_case_flows_from_text_to_verified_recommendation(self) -> None:
        documents = [
            (
                "Apex Office Supplies",
                526500,
                94770,
                2500,
                623770,
                5,
            ),
            (
                "BrightTech Distributors",
                512200,
                92196,
                0,
                604396,
                12,
            ),
            (
                "Nova Business Systems",
                536000,
                96480,
                1500,
                633980,
                4,
            ),
        ]
        evidence = []
        for index, (name, subtotal, gst, freight, total, delivery) in enumerate(documents, start=1):
            text = (
                f"Vendor: {name}\nItem: Office laptops and wireless mice\n"
                f"Quantity: 10\nUnit Price: INR {subtotal // 10}\n"
                f"Subtotal: INR {subtotal}\nGST: 18%\nGST Amount: INR {gst}\n"
                f"Freight: INR {freight}\nOther Taxes: INR 0\n"
                f"Additional Charges: INR 0\nDiscount: INR 0\n"
                f"Grand Total: INR {total}\nDelivery: {delivery} days\n"
                "Payment Terms: Net 30 days\nCurrency: INR"
            )
            fields = extract_fields(text, f"{name}.pdf")
            normalized = normalize(fields)
            evidence.append(to_quotation_evidence(normalized, f"vendor-{index}"))
            self.assertEqual(evidence[-1]["total_cost"], total)
            self.assertEqual(evidence[-1]["delivery_days"], delivery)
            self.assertFalse(evidence[-1]["data_warnings"])

        with patch(
            "core.ai_evaluation._ollama_chat",
            return_value=model_response(["vendor-2", "vendor-3", "vendor-1"]),
        ):
            evaluation, _ = evaluate_vendors(
                evidence,
                "10 office laptops and 10 wireless mice; maximum budget ₹630,000; "
                "delivery within 7 days; prefers Net 30 payment terms.",
            )

        self.assertEqual(evaluation.best_recommendation_vendor_id, "vendor-1")
        self.assertEqual(evaluation.ranked_vendors[0].vendor_id, "vendor-1")


if __name__ == "__main__":
    unittest.main()
