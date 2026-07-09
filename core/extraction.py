"""
extraction.py
-------------
Rule-based field extraction using regex patterns and simple heuristics.

Extracted fields (single-line-item prototype):
    - vendor_name
    - item_name
    - quantity
    - unit_price
    - total_price
    - gst_percent
    - delivery_days
    - payment_terms_days
    - freight_cost

Notes:
    - This is intentionally lightweight and CPU-friendly (no LLMs).
    - When values are missing, sensible defaults are assigned and the field
      name is added to `missing_fields` (used for scoring penalties).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


DEFAULTS: Dict[str, Any] = {
    "vendor_name": "Unknown Vendor",
    "item_name": "Item",
    "quantity": 1,
    "unit_price": 0.0,
    "total_price": 0.0,
    "gst_percent": 18.0,
    "delivery_days": 30,
    "payment_terms_days": 30,
    "delivery_text": "",
    "payment_terms_text": "",
    "penalty_clause": "",
    "freight_cost": 0.0,
    "currency": "INR",
}


def extract_fields(text: str, filename: str = "") -> Dict[str, Any]:
    """
    Parse raw text and extract quotation fields. Missing fields are filled
    with defaults.
    """
    text_strip = (text or "").strip()
    if text_strip.startswith("[") and any(
        err in text_strip
        for err in (
            "OCR unavailable",
            "OCR error",
            "OCR fallback failed",
            "pytesseract not installed",
            "Could not decode image",
            "No text detected by OCR",
        )
    ):
        raise ValueError(f"File '{filename}': {text_strip}")

    # If the upload is a structured table (CSV/XLSX), try parsing it first.
    structured = _try_parse_structured_row(text or "")
    if structured is not None:
        structured.setdefault("missing_fields", [])
        # Also build delivery/payment text fields if only days are present.
        if "delivery_text" not in structured and "delivery_days" in structured:
            structured["delivery_text"] = f"{structured.get('delivery_days')} days"
        if "payment_terms_text" not in structured and "payment_terms_days" in structured:
            structured["payment_terms_text"] = f"Net {structured.get('payment_terms_days')}"
        return _with_defaults(structured)

    cleaned = _cleanup_text(text or "")
    data: Dict[str, Any] = dict(DEFAULTS)
    missing_fields: list[str] = []
    evidence: Dict[str, str] = {}

    vendor_name, found_vendor = _extract_vendor_name(cleaned, filename)
    data["vendor_name"] = vendor_name
    if not found_vendor and not filename:
        missing_fields.append("vendor_name")

    item_name, found_item = _extract_item_name(cleaned)
    data["item_name"] = item_name
    if not found_item:
        missing_fields.append("item_name")

    quantity, found_qty = _extract_quantity(cleaned)
    data["quantity"] = quantity
    if not found_qty:
        missing_fields.append("quantity")

    unit_price, found_unit = _extract_unit_price(cleaned)
    data["unit_price"] = unit_price
    if not found_unit:
        missing_fields.append("unit_price")

    total_price, found_total = _extract_total_price(cleaned)
    data["total_price"] = total_price
    if not found_total:
        missing_fields.append("total_price")

    # If one of unit/total is missing but quantity is known, infer it.
    # This prevents common OCR/formatting misses from turning into ₹0 totals.
    if found_qty and quantity > 0:
        if (not found_total or total_price <= 0) and found_unit and unit_price > 0:
            inferred_total = float(unit_price) * int(quantity)
            if inferred_total > 0:
                data["total_price"] = inferred_total
                found_total = True
                if "total_price" in missing_fields:
                    missing_fields.remove("total_price")
                evidence["total_price"] = "inferred from unit_price * quantity"

        if (not found_unit or unit_price <= 0) and found_total and data["total_price"] > 0:
            inferred_unit = float(data["total_price"]) / int(quantity)
            if inferred_unit > 0:
                data["unit_price"] = inferred_unit
                found_unit = True
                if "unit_price" in missing_fields:
                    missing_fields.remove("unit_price")
                evidence["unit_price"] = "inferred from total_price / quantity"

    gst_percent, found_gst = _extract_gst_percent(cleaned)
    data["gst_percent"] = gst_percent
    if not found_gst:
        missing_fields.append("gst_percent")

    delivery_days, found_delivery = _extract_delivery_days(cleaned)
    data["delivery_days"] = delivery_days
    if not found_delivery:
        missing_fields.append("delivery_days")

    payment_days, found_terms = _extract_payment_terms_days(cleaned)
    data["payment_terms_days"] = payment_days
    if not found_terms:
        missing_fields.append("payment_terms_days")

    delivery_text, found_delivery_text = _extract_delivery_text(cleaned)
    data["delivery_text"] = delivery_text
    if found_delivery_text:
        evidence["delivery_text"] = delivery_text

    payment_text, found_payment_text = _extract_payment_terms_text(cleaned)
    data["payment_terms_text"] = payment_text
    if found_payment_text:
        evidence["payment_terms_text"] = payment_text

    penalty_clause, found_penalty = _extract_penalty_clause(cleaned)
    data["penalty_clause"] = penalty_clause
    if found_penalty:
        evidence["penalty_clause"] = penalty_clause

    freight, found_freight = _extract_freight_cost(cleaned)
    data["freight_cost"] = freight
    if not found_freight:
        missing_fields.append("freight_cost")

    currency, found_currency = _extract_currency(cleaned)
    data["currency"] = currency
    if not found_currency:
        missing_fields.append("currency")

    data["missing_fields"] = sorted(set(missing_fields))
    data["extraction_evidence"] = evidence
    return data


def _with_defaults(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(DEFAULTS)
    out.update({k: v for k, v in row.items() if v is not None})
    missing = row.get("missing_fields") or []
    out["missing_fields"] = sorted(set(missing)) if isinstance(missing, list) else []
    return out


def _try_parse_structured_row(text: str) -> Dict[str, Any] | None:
    """
    Attempt to parse a single-row quotation from CSV-like text.
    """
    head = (text or "").lstrip()
    first_line = head.splitlines()[0] if head else ""
    # structured only if it looks like a delimited header row (CSV/XLSX->CSV)
    if "," not in first_line:
        return None
    if first_line.count(",") < 2:
        return None
    if not any(k in first_line.lower() for k in ("vendor", "supplier", "company", "item", "qty", "quantity", "unit", "total")):
        return None

    try:
        import io
        import pandas as pd

        df = pd.read_csv(io.StringIO(text))
        if df.empty:
            return None
        r = df.iloc[0].to_dict()
    except Exception:
        return None

    def get(key: str):
        for k in r.keys():
            if str(k).strip().lower() == key:
                return r[k]
        return None

    out: Dict[str, Any] = {}
    missing: list[str] = []

    # Map imperfect/short/truncated headers (common in real vendor sheets)
    header_map = {
        "vendor_name": ("vendor_name", "vendor", "supplier", "company", "vendor_na"),
        "item_name": ("item_name", "item", "product", "description", "item_na"),
        "quantity": ("quantity", "qty", "qnty", "nos", "units"),
        "unit_price": ("unit_price", "unit", "rate", "price", "unit_pr"),
        "total_price": ("total_price", "total", "amount", "value"),
        "gst_percent": ("gst_percent", "gst", "tax", "gst_per", "gst_percer"),
        "freight_cost": ("freight_cost", "freight", "shipping", "transport", "freight_cos"),
        "delivery_days": ("delivery_days", "delivery", "lead", "dispatch", "delivery_da"),
        "payment_terms_days": ("payment_terms_days", "payment", "terms", "payment_t"),
        "currency": ("currency", "curr", "ccy"),
    }

    def get_fuzzy(target: str):
        for key in header_map.get(target, (target,)):
            for k in r.keys():
                if key == str(k).strip().lower():
                    return r[k]
                if str(k).strip().lower().startswith(key):
                    return r[k]
        return None

    for k in DEFAULTS.keys():
        if k in ("delivery_text", "payment_terms_text", "penalty_clause"):
            continue
        v = get_fuzzy(k)
        if v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and not v.strip()):
            missing.append(k)
            continue
        out[k] = v

    # Normalize keys that often appear in files
    if "gst" in r and "gst_percent" not in out:
        out["gst_percent"] = r["gst"]
        if "gst_percent" in missing:
            missing.remove("gst_percent")

    out["missing_fields"] = missing
    return out


def _extract_delivery_text(text: str) -> Tuple[str, bool]:
    return _extract_line_value(text, ["delivery", "lead time", "dispatch", "shipping"])


def _extract_payment_terms_text(text: str) -> Tuple[str, bool]:
    return _extract_line_value(text, ["payment terms", "payment", "terms"])


def _extract_penalty_clause(text: str) -> Tuple[str, bool]:
    # Return the full line if it contains penalty/late fee/interest.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in ("penalt", "late fee", "late payment", "interest", "liquidated damages")):
            return ln[:250], True
    return "", False


def _extract_line_value(text: str, keywords: list[str]) -> Tuple[str, bool]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in keywords):
            # common "Key: Value" format
            parts = re.split(r"\s*[:\-]\s*", ln, maxsplit=1)
            if len(parts) == 2:
                val = parts[1].strip()
                return val[:200], True
            return ln[:200], True
    return "", False


def _cleanup_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _extract_vendor_name(text: str, filename: str) -> Tuple[str, bool]:
    patterns = [
        # Require a clear separator to avoid matching headers like "VENDOR QUOTATION"
        r"(?:vendor|company|supplier|from)\s*[:\-]\s*([A-Za-z0-9 &.,'()/-]{3,80})",
        r"(?:quotation from|quote by)\s*[:\-]\s*([A-Za-z0-9 &.,'()/-]{3,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().strip(",.:;")
            if name:
                return name, True

    # Heuristic: use the first meaningful line as vendor name
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:5]:
        low = ln.lower()
        if low in {"quotation", "vendor quotation", "vendor quote", "quote"}:
            continue
        if "vendor quotation" in low:
            continue
        # "Ganesh Tech Services - Quotation" -> "Ganesh Tech Services"
        if "-" in ln and "quotation" in low:
            candidate = ln.split("-", 1)[0].strip()
            if len(candidate) >= 3:
                return candidate, False
        # If line looks like a company name and is short enough, accept it
        if 3 <= len(ln) <= 80 and re.search(r"[A-Za-z]", ln):
            return ln.strip().strip(",.:;"), False

    if filename:
        stem = re.sub(r"[_\-]+", " ", filename.rsplit(".", 1)[0])
        return (stem.title() if stem else DEFAULTS["vendor_name"]), False

    return DEFAULTS["vendor_name"], False


def _extract_item_name(text: str) -> Tuple[str, bool]:
    patterns = [
        r"(?:item|product|description)[:\s]+([A-Za-z0-9 &.,'()/-]{3,120})",
        r"(?:for)[:\s]+([A-Za-z0-9 &.,'()/-]{3,120})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().strip(",.:;")
            if name:
                return name, True
    return DEFAULTS["item_name"], False


def _extract_quantity(text: str) -> Tuple[int, bool]:
    patterns = [
        r"(?:qty|quantity|nos|units?|pcs|pieces?)[:\s=]+(\d[\d,]*)",
        r"(\d[\d,]*)\s*(?:units?|nos|pcs|pieces?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_int(match.group(1))
            if val > 0:
                return val, True
    return int(DEFAULTS["quantity"]), False


def _extract_unit_price(text: str) -> Tuple[float, bool]:
    patterns = [
        r"(?:unit\s*price|price\s*per\s*unit|rate|per\s*unit)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
        r"(?:unit\s*cost|cost\s*per\s*unit)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if val > 0:
                return val, True
    # Fallback: find a relevant line and take last number
    val = _extract_number_from_line(text, ["unit price", "unit cost", "rate", "per unit"])
    if val is not None and val > 0:
        return float(val), True
    return float(DEFAULTS["unit_price"]), False


def _extract_total_price(text: str) -> Tuple[float, bool]:
    patterns = [
        r"(?:total\s*(?:amount|price|cost|value)|grand\s*total|amount\s*due)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
        r"(?:sub\s*total|subtotal)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if val > 0:
                return val, True
    val = _extract_number_from_line(text, ["total amount", "grand total", "subtotal", "sub total", "amount due", "total"])
    if val is not None and val > 0:
        return float(val), True
    return float(DEFAULTS["total_price"]), False


def _extract_gst_percent(text: str) -> Tuple[float, bool]:
    patterns = [
        r"(?:gst|tax|vat|igst|cgst|sgst)[:\s]*([0-9]+(?:\.[0-9]{1,2})?)\s*%",
        r"([0-9]+(?:\.[0-9]{1,2})?)\s*%\s*(?:gst|tax|vat)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if 0 < val <= 100:
                return val, True
    return float(DEFAULTS["gst_percent"]), False


def _extract_delivery_days(text: str) -> Tuple[int, bool]:
    patterns = [
        r"(?:delivery|lead\s*time|ship(?:ping)?|dispatch)[:\s]*(\d+)\s*(days?|working\s*days?|business\s*days?)",
        r"(?:delivery|lead\s*time|ship(?:ping)?|dispatch)[:\s]*(\d+)\s*(weeks?)",
        r"(\d+)\s*(days?|weeks?)\s*(?:delivery|lead\s*time|dispatch)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_int(match.group(1))
            unit = match.group(2).lower() if match.lastindex and match.lastindex >= 2 else ""
            if "week" in unit:
                val *= 7
            val = max(1, val)
            return val, True
    return int(DEFAULTS["delivery_days"]), False


def _extract_payment_terms_days(text: str) -> Tuple[int, bool]:
    patterns = [
        r"(?:payment\s*terms?|payment)[:\s]*net\s*(\d+)",
        r"\bnet\s*(\d+)\b",
        r"(?:payment\s*terms?|terms?)[:\s]*(\d+)\s*days?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_int(match.group(1))
            return max(0, val), True

    if re.search(r"(?:advance|upfront|immediate)", text, re.IGNORECASE):
        return 0, True

    return int(DEFAULTS["payment_terms_days"]), False


def _extract_freight_cost(text: str) -> Tuple[float, bool]:
    patterns = [
        r"(?:freight|shipping|logistics|transport(?:ation)?)[:\s]*(?:cost|charge|fee)?[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
        r"(?:delivery\s*charge|handling\s*charge)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if val >= 0:
                return val, True
    val = _extract_number_from_line(text, ["freight", "shipping", "logistics", "transport", "delivery charge", "handling"])
    if val is not None and val >= 0:
        return float(val), True
    return float(DEFAULTS["freight_cost"]), False


def _extract_currency(text: str) -> Tuple[str, bool]:
    if re.search(r"\bUSD\b|\$|dollar", text, re.IGNORECASE):
        return "USD", True
    if re.search(r"\bINR\b|₹|\brs\.?\b|\brupees?\b", text, re.IGNORECASE):
        return "INR", True
    return "INR", False


def _parse_float(value: str) -> float:
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _parse_int(value: str) -> int:
    try:
        return int(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _extract_number_from_line(text: str, keywords: list[str]) -> float | None:
    """
    Find the first line containing any keyword and return the last number on that line.
    Useful for unstructured quotes like: "Total Amount: INR 2600000".
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in keywords):
            nums = re.findall(r"([0-9][0-9,]*(?:\.[0-9]+)?)", ln)
            if nums:
                return _parse_float(nums[-1])
    return None
