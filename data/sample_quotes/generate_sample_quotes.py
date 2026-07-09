"""
generate_sample_quotes.py
-------------------------
Generates 5 realistic vendor quotation documents:
    - PDF (PyMuPDF)
    - PNG image (OpenCV) for OCR testing
    - CSV (structured) for spreadsheet ingestion

All content is rule-based and intentionally varied to exercise extraction.

Run:
    python data/sample_quotes/generate_sample_quotes.py
"""

from __future__ import annotations

import os


SAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))

SAMPLES = [
    {
        "slug": "alpha",
        "vendor_name": "Alpha Supplies Pvt Ltd",
        "lines": [
            "VENDOR QUOTATION",
            "Vendor: Alpha Supplies Pvt Ltd",
            "Item: Laptop Dell Latitude 5440",
            "Quantity: 50 units",
            "Unit Price: INR 52000",
            "Total Amount: INR 2600000",
            "GST: 18%",
            "Freight: INR 10000",
            "Delivery: 10 working days",
            "Payment Terms: Net 30 days",
            "Penalty: 0.5% per week delay, max 5%",
        ],
        "row": {
            "vendor_name": "Alpha Supplies Pvt Ltd",
            "item_name": "Laptop Dell Latitude 5440",
            "quantity": 50,
            "unit_price": 52000,
            "total_price": 2600000,
            "gst_percent": 18,
            "delivery_days": 12,
            "payment_terms_days": 30,
            "freight_cost": 10000,
            "currency": "INR",
        },
    },
    {
        "slug": "beta",
        "vendor_name": "TechWorld Suppliers",
        "lines": [
            "Quotation From: TechWorld Suppliers",
            "Product Description: Laptop Dell Latitude 5440",
            "Qty = 50",
            "Rate (Per Unit): Rs. 50000",
            "Subtotal: Rs. 2500000",
            "GST @18% applicable",
            "Shipping Charge: Rs. 15000",
            "Lead time: 20 days",
            "Payment: Net 15",
            "Late payment interest: 2% per month",
        ],
        "row": {
            "vendor_name": "TechWorld Suppliers",
            "item_name": "Laptop Dell Latitude 5440",
            "quantity": 50,
            "unit_price": 50000,
            "total_price": 2500000,
            "gst_percent": 18,
            "delivery_days": 20,
            "payment_terms_days": 15,
            "freight_cost": 15000,
            "currency": "INR",
        },
    },
    {
        "slug": "gamma",
        "vendor_name": "SSN Office Solutions",
        "lines": [
            "SSN Office Solutions",
            "Quotation",
            "Item: Laptop Dell Latitude 5440",
            "Quantity: 50",
            "Unit Cost: INR 51000",
            "Total: INR 2550000",
            "GST: 18%",
            "Freight: INR 0",
            "Delivery: 15 days",
            "Payment Terms: Net 45",
        ],
        "row": {
            "vendor_name": "SSN Office Solutions",
            "item_name": "Laptop Dell Latitude 5440",
            "quantity": 50,
            "unit_price": 51000,
            "total_price": 2550000,
            "gst_percent": 18,
            "delivery_days": 15,
            "payment_terms_days": 45,
            "freight_cost": 0,
            "currency": "INR",
        },
    },
    {
        "slug": "delta",
        "vendor_name": "RK Enterprises",
        "lines": [
            "Company: RK Enterprises",
            "Item: Laptop Dell Latitude 5440",
            "Qty: 50",
            "Unit Price: INR 49500",
            "Total Amount: INR 2475000",
            "GST: 18%",
            "Freight: INR 20000",
            "Dispatch in 25 days",
            "Payment Terms: Net 60",
        ],
        "row": {
            "vendor_name": "RK Enterprises",
            "item_name": "Laptop Dell Latitude 5440",
            "quantity": 50,
            "unit_price": 49500,
            "total_price": 2475000,
            "gst_percent": 18,
            "delivery_days": 25,
            "payment_terms_days": 60,
            "freight_cost": 20000,
            "currency": "INR",
        },
    },
    {
        "slug": "epsilon",
        "vendor_name": "Ganesh Tech Services",
        "lines": [
            "Ganesh Tech Services - Quotation",
            "Product: Laptop Dell Latitude 5440",
            "Quantity: 50 pcs",
            "Unit Price: INR 53000",
            "Total Amount: INR 2650000",
            "GST: 18%",
            "Freight: INR 5000",
            "Delivery: 7 days",
            "Payment Terms: Immediate",
            "Warranty: 3 years",
        ],
        "row": {
            "vendor_name": "Ganesh Tech Services",
            "item_name": "Laptop Dell Latitude 5440",
            "quantity": 50,
            "unit_price": 53000,
            "total_price": 2650000,
            "gst_percent": 18,
            "delivery_days": 7,
            "payment_terms_days": 1,
            "freight_cost": 5000,
            "currency": "INR",
        },
    },
]


def _write_csv(path: str, row: dict) -> None:
    headers = list(row.keys())
    values = [str(row[h]) for h in headers]
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        f.write(",".join(values) + "\n")

def _write_pdf(path: str, lines: list[str]) -> None:
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()

    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16

    doc.save(path)
    doc.close()


def _write_png(path: str, lines: list[str]) -> None:
    import cv2
    import numpy as np

    img = np.full((1600, 1200, 3), 255, dtype=np.uint8)
    y = 60
    for line in lines:
        cv2.putText(img, line[:80], (40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
        y += 45

    cv2.imwrite(path, img)


if __name__ == "__main__":
    print("Generating sample vendor quotation CSV files...")
    for s in SAMPLES:
        slug = s["slug"]

        csv_path = os.path.join(SAMPLE_DIR, f"sample_{slug}.csv")
        pdf_path = os.path.join(SAMPLE_DIR, f"sample_{slug}.pdf")
        png_path = os.path.join(SAMPLE_DIR, f"sample_{slug}.png")

        _write_csv(csv_path, s["row"])
        _write_pdf(pdf_path, s["lines"])
        _write_png(png_path, s["lines"])

        print(f"  Created: {csv_path}")
        print(f"  Created: {pdf_path}")
        print(f"  Created: {png_path}")
    print("Done.")
