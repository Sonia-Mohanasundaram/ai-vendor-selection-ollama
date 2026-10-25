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
    - other_taxes
    - additional_charges

Notes:
    - This is intentionally lightweight and CPU-friendly (no LLMs).
    - Missing values remain `None` and are recorded in `missing_fields`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


DEFAULTS: Dict[str, Any] = {
    "vendor_name": None,
    "item_name": None,
    "quantity": None,
    "unit_price": None,
    "total_price": None,
    "taxable_amount": None,
    "gst_percent": None,
    "gst_amount": None,
    "quoted_total": None,
    "discount_amount": None,
    "delivery_days": None,
    "payment_terms_days": None,
    "delivery_text": "",
    "payment_terms_text": "",
    "penalty_clause": "",
    "freight_cost": None,
    "other_taxes": None,
    "additional_charges": None,
    "validity_text": "",
    "currency": None,
    "tax_inclusive": None,
}


def extract_fields(text: str, filename: str = "") -> Dict[str, Any]:
    """
    Parse raw text and keep absent quotation fields unknown.
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
        if "delivery_text" not in structured and structured.get("delivery_days") is not None:
            structured["delivery_text"] = f"{structured.get('delivery_days')} days"
        if "payment_terms_text" not in structured and structured.get("payment_terms_days") is not None:
            structured["payment_terms_text"] = f"Net {structured.get('payment_terms_days')}"
        return _with_defaults(structured)

    cleaned = _cleanup_text(text or "")
    data: Dict[str, Any] = dict(DEFAULTS)
    missing_fields: list[str] = []
    evidence: Dict[str, str] = {}

    vendor_name, found_vendor = _extract_vendor_name(cleaned)
    data["vendor_name"] = vendor_name
    if vendor_name is None:
        missing_fields.append("vendor_name")
    elif not found_vendor:
        source = _find_source_line(cleaned, [vendor_name]) or vendor_name
        evidence["vendor_name"] = source
        data.setdefault("data_warnings", []).append(
            "Vendor name was inferred from an unlabeled document heading; verify it against the quotation."
        )

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

    # A line subtotal can be derived only when both source values are present.
    if found_qty and quantity is not None and quantity > 0:
        if not found_total and found_unit and unit_price is not None:
            inferred_total = float(unit_price) * int(quantity)
            data["total_price"] = inferred_total
            found_total = True
            if "total_price" in missing_fields:
                missing_fields.remove("total_price")
            evidence["total_price"] = "Calculated from extracted quantity and unit price"

        if not found_unit and found_total and data["total_price"] is not None:
            inferred_unit = float(data["total_price"]) / int(quantity)
            data["unit_price"] = inferred_unit
            found_unit = True
            if "unit_price" in missing_fields:
                missing_fields.remove("unit_price")
            evidence["unit_price"] = "Calculated from extracted subtotal and quantity"

    gst_percent, found_gst = _extract_gst_percent(cleaned)
    data["gst_percent"] = gst_percent
    if not found_gst:
        missing_fields.append("gst_percent")

    gst_amount, found_gst_amount = _extract_labeled_amount(
        cleaned, ["gst amount", "tax amount", "gst value"]
    )
    data["gst_amount"] = gst_amount
    if not found_gst_amount:
        missing_fields.append("gst_amount")

    quoted_total, found_quoted_total = _extract_quoted_total(cleaned)
    data["quoted_total"] = quoted_total
    if not found_quoted_total:
        missing_fields.append("quoted_total")

    discount_amount, found_discount = _extract_labeled_amount(cleaned, ["discount", "rebate"])
    data["discount_amount"] = discount_amount
    if not found_discount:
        missing_fields.append("discount_amount")

    taxable_amount, found_taxable = _extract_labeled_amount(
        cleaned, ["taxable amount", "taxable value"]
    )
    data["taxable_amount"] = taxable_amount
    if not found_taxable:
        missing_fields.append("taxable_amount")

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

    validity_text, found_validity = _extract_line_value(
        cleaned, ["validity", "valid until", "valid through"]
    )
    data["validity_text"] = validity_text
    if found_validity:
        evidence["validity_text"] = validity_text

    penalty_clause, found_penalty = _extract_penalty_clause(cleaned)
    data["penalty_clause"] = penalty_clause
    if found_penalty:
        evidence["penalty_clause"] = penalty_clause

    freight, found_freight = _extract_freight_cost(cleaned)
    data["freight_cost"] = freight
    if not found_freight:
        missing_fields.append("freight_cost")

    other_taxes, found_other_taxes = _extract_labeled_amount(
        cleaned, ["other tax", "additional tax", "cess", "levy"]
    )
    data["other_taxes"] = other_taxes
    if not found_other_taxes:
        missing_fields.append("other_taxes")

    additional_charges, found_additional_charges = _extract_labeled_amount(
        cleaned, ["other charge", "additional charge", "surcharge", "handling charge", "miscellaneous charge"]
    )
    data["additional_charges"] = additional_charges
    if not found_additional_charges:
        missing_fields.append("additional_charges")

    currency, found_currency = _extract_currency(cleaned)
    data["currency"] = currency
    if not found_currency:
        missing_fields.append("currency")

    tax_inclusive = _extract_tax_inclusive(cleaned)
    data["tax_inclusive"] = tax_inclusive

    data["missing_fields"] = sorted(set(missing_fields))
    source_labels = {
        "vendor_name": ["vendor", "supplier", "company", "from"],
        "item_name": ["item", "product", "description"],
        "quantity": ["quantity", "qty", "nos", "units", "pcs", "pieces"],
        "unit_price": ["unit price", "unit cost", "rate", "per unit"],
        "total_price": ["subtotal", "total amount", "total price", "total cost", "total"],
        "gst_percent": ["gst", "tax", "vat", "igst", "cgst", "sgst"],
        "gst_amount": ["gst amount", "tax amount", "gst value"],
        "quoted_total": ["grand total", "total payable", "amount due", "final total", "total"],
        "discount_amount": ["discount", "rebate"],
        "taxable_amount": ["taxable amount", "taxable value"],
        "delivery_days": ["delivery", "lead time", "dispatch"],
        "payment_terms_days": ["payment", "terms", "net"],
        "freight_cost": ["freight", "shipping", "logistics", "transport", "delivery charge", "handling"],
        "other_taxes": ["other tax", "additional tax", "cess", "levy"],
        "additional_charges": ["other charge", "additional charge", "surcharge", "handling charge"],
        "currency": ["inr", "usd", "₹", "$", "rupee", "dollar"],
    }
    for field, labels in source_labels.items():
        if field not in missing_fields and field not in evidence:
            source = _find_source_line(cleaned, labels)
            if source:
                evidence[field] = source
    data["extraction_evidence"] = evidence
    data["extraction_confidence"] = {
        field: "source-backed" if field in evidence else "unavailable"
        for field in (
            "vendor_name",
            "item_name",
            "quantity",
            "unit_price",
            "total_price",
            "gst_percent",
            "gst_amount",
            "quoted_total",
            "discount_amount",
            "taxable_amount",
            "validity_text",
            "delivery_days",
            "payment_terms_days",
            "freight_cost",
            "other_taxes",
            "additional_charges",
            "currency",
        )
    }
    data["field_status"] = {}
    for field, labels in source_labels.items():
        source = _find_source_line(cleaned, labels)
        if field in missing_fields:
            data["field_status"][field] = "unknown" if source else "not_provided"
        elif source and re.search(
            r"\b(?:not applicable|n/?a|none|nil|no\s+(?:other\s+)?(?:tax|charge|freight)|free)\b",
            source,
            re.IGNORECASE,
        ):
            data["field_status"][field] = "not_applicable"
        elif evidence.get(field, "").startswith("Calculated"):
            data["field_status"][field] = "calculated"
        else:
            data["field_status"][field] = "source_backed"
    if vendor_name is not None and not found_vendor:
        data["extraction_confidence"]["vendor_name"] = "heuristic"
        data["field_status"]["vendor_name"] = "unknown"
    return data


def _with_defaults(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(DEFAULTS)
    out.update(row)
    missing = row.get("missing_fields") or []
    out["missing_fields"] = sorted(set(missing)) if isinstance(missing, list) else []
    out["extraction_evidence"] = row.get("extraction_evidence") or {}
    out["extraction_confidence"] = row.get("extraction_confidence") or {}
    out["field_status"] = row.get("field_status") or {
        field: "not_provided" if field in out["missing_fields"] else "source_backed"
        for field in (
            "vendor_name",
            "item_name",
            "quantity",
            "unit_price",
            "total_price",
            "gst_percent",
            "gst_amount",
            "quoted_total",
            "discount_amount",
            "delivery_days",
            "payment_terms_days",
            "freight_cost",
            "other_taxes",
            "additional_charges",
            "currency",
        )
    }
    return out


def _find_source_line(text: str, labels: list[str]) -> str | None:
    for line in text.splitlines():
        if any(label.lower() in line.lower() for label in labels):
            return line.strip()[:250]
    return None


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

    import io
    import pandas as pd
    try:
        df = pd.read_csv(io.StringIO(text))
    except pd.errors.ParserError as exc:
        raise ValueError("Could not parse the structured quotation table.") from exc
    if df.empty:
        raise ValueError("The structured quotation table has no data rows.")
    r = df.iloc[0].to_dict()

    out: Dict[str, Any] = {}
    missing: list[str] = []

    # Map imperfect/short/truncated headers (common in real vendor sheets)
    header_map = {
        "vendor_name": ("vendor_name", "vendor name", "vendor", "supplier", "company"),
        "item_name": ("item_name", "item name", "item", "product", "description"),
        "quantity": ("quantity", "qty", "qnty", "nos", "units", "pcs", "pieces"),
        "unit_price": (
            "unit_price", "unit price", "unit_cost", "unit cost",
            "unit_rate", "unit rate", "price_per_unit", "price per unit", "rate",
        ),
        "total_price": (
            "total_price", "total price", "line_total", "line total",
            "line_amount", "line amount", "subtotal", "sub_total", "sub total",
            "total_amount", "total amount",
        ),
        "gst_amount": ("gst_amount", "tax_amount", "gst_value", "tax_value"),
        "taxable_amount": ("taxable_amount", "taxable_value"),
        "quoted_total": (
            "quoted_total", "grand_total", "amount_due", "total_payable",
            "final_total", "total",
        ),
        "discount_amount": ("discount_amount", "discount", "rebate"),
        "gst_percent": ("gst_percent", "gst_rate", "gst", "tax_percent", "tax_rate", "gst_per"),
        "freight_cost": (
            "freight_cost", "freight", "shipping_cost", "shipping_charge", "transport_cost"
        ),
        "other_taxes": ("other_taxes", "other_tax", "additional_tax", "cess", "levy"),
        "additional_charges": (
            "additional_charges", "other_charges", "surcharge", "handling_charge", "misc_charges"
        ),
        "delivery_days": ("delivery_days", "lead_time_days", "dispatch_days", "delivery"),
        "payment_terms_days": ("payment_terms_days", "payment_days", "net_days"),
        "currency": ("currency", "curr", "ccy"),
    }

    def normalize_header(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")

    def matches_header(actual: Any, alias: str) -> bool:
        normalized_actual = normalize_header(actual)
        normalized_alias = normalize_header(alias)
        return normalized_actual == normalized_alias or (
            "_" in normalized_alias and normalized_actual.startswith(f"{normalized_alias}_")
        )

    def get_fuzzy(target: str):
        for key in header_map.get(target, (target,)):
            for k in r.keys():
                if matches_header(k, key):
                    return r[k]
        return None

    for k in DEFAULTS.keys():
        if k in ("delivery_text", "payment_terms_text", "penalty_clause", "tax_inclusive", "validity_text"):
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
    out["extraction_evidence"] = {}
    for target, aliases in header_map.items():
        for source_key, value in r.items():
            if (
                value is not None
                and not (isinstance(value, float) and value != value)
                and any(matches_header(source_key, alias) for alias in aliases)
            ):
                out["extraction_evidence"][target] = f"{source_key}: {value}"
                break
    out["extraction_confidence"] = {
        target: "source-backed" if target in out["extraction_evidence"] else "unavailable"
        for target in header_map
    }
    return out


def _extract_delivery_text(text: str) -> Tuple[str, bool]:
    return _extract_line_value(text, ["delivery", "lead time", "dispatch", "shipping time"])


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


def _extract_vendor_name(text: str) -> Tuple[str | None, bool]:
    patterns = [
        # Require a clear separator to avoid matching headers like "VENDOR QUOTATION"
        r"(?:vendor|company|supplier|from)\s*[:\-]\s*([^\r\n]{3,80})",
        r"(?:quotation from|quote by)\s*[:\-]\s*([^\r\n]{3,80})",
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

    return DEFAULTS["vendor_name"], False


def _extract_item_name(text: str) -> Tuple[str | None, bool]:
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


def _extract_quantity(text: str) -> Tuple[int | None, bool]:
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
    return None, False


def _extract_unit_price(text: str) -> Tuple[float | None, bool]:
    patterns = [
        r"(?:unit\s*price|price\s*per\s*unit|rate|per\s*unit)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
        r"(?:unit\s*cost|cost\s*per\s*unit)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if val >= 0:
                return val, True
    # Fallback: find a relevant line and take last number
    val = _extract_number_from_line(text, ["unit price", "unit cost", "rate", "per unit"])
    if val is not None and val >= 0:
        return float(val), True
    return None, False


def _extract_total_price(text: str) -> Tuple[float | None, bool]:
    patterns = [
        r"(?:sub\s*total|subtotal|total\s*(?:amount|price|value))[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
        r"(?:sub\s*total|subtotal)[:\s=₹$A-Za-z.]*([0-9,]+(?:\.[0-9]{1,4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if val >= 0:
                return val, True
    val = _extract_number_from_line(text, ["subtotal", "sub total", "total amount", "total price"])
    if val is not None and val >= 0:
        return float(val), True
    return None, False


def _extract_quoted_total(text: str) -> Tuple[float | None, bool]:
    patterns = (
        r"(?:grand\s*total|total\s*payable|final\s*total|amount\s*due|total\s*including\s*(?:all\s*)?tax(?:es)?)"
        r"[:\s=₹$A-Za-z.]*([0-9][\d,]*(?:\.\d{1,4})?)",
        r"(?:^|\n)\s*total\s*[:=₹$A-Za-z.]*([0-9][\d,]*(?:\.\d{1,4})?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_float(match.group(1)), True
    return None, False


def _extract_tax_inclusive(text: str) -> bool | None:
    if re.search(
        r"\b(?:gst|tax)\s*(?:is\s*)?(?:included|inclusive)\b"
        r"|\b(?:tax|gst)[- ]inclusive\b"
        r"|\binclusive of\s+(?:gst|tax)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b(?:gst|tax)\s*(?:is\s*)?(?:excluded|exclusive|extra|additional)\b"
        r"|\bexcluding\s+(?:gst|tax)\b"
        r"|\bexclusive of\s+(?:gst|tax)\b",
        text,
        re.IGNORECASE,
    ):
        return False
    return None


def _extract_gst_percent(text: str) -> Tuple[float | None, bool]:
    tax_components = {
        name.lower(): _parse_float(value)
        for name, value in re.findall(
            r"\b(cgst|sgst|igst)\s*(?:@|:)?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*%",
            text,
            re.IGNORECASE,
        )
    }
    if "igst" in tax_components:
        return tax_components["igst"], True
    if "cgst" in tax_components and "sgst" in tax_components:
        return tax_components["cgst"] + tax_components["sgst"], True

    patterns = [
        r"(?:gst|tax|vat|igst|cgst|sgst)[:\s@]*([0-9]+(?:\.[0-9]{1,2})?)\s*%",
        r"([0-9]+(?:\.[0-9]{1,2})?)\s*%\s*(?:gst|tax|vat)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_float(match.group(1))
            if 0 <= val <= 100:
                return val, True
    return None, False


def _extract_delivery_days(text: str) -> Tuple[int | None, bool]:
    delivery_labels = re.compile(r"\b(?:delivery|lead\s*time|dispatch|shipping\s*time)\b", re.IGNORECASE)
    for line in text.splitlines():
        if not delivery_labels.search(line):
            continue
        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(working\s*days?|business\s*days?|days?|weeks?|months?)\b",
            line,
            re.IGNORECASE,
        )
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            multiplier = 7 if unit.startswith("week") else 30 if unit.startswith("month") else 1
            return int(value * multiplier), True
    return None, False


def _extract_payment_terms_days(text: str) -> Tuple[int | None, bool]:
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

    return None, False


def _extract_freight_cost(text: str) -> Tuple[float | None, bool]:
    for line in text.splitlines():
        if re.search(r"\b(?:freight|shipping|logistics|transport|delivery charge)\b", line, re.IGNORECASE):
            if re.search(r"\b(?:not applicable|n/?a|none|nil|no freight|free shipping)\b", line, re.IGNORECASE):
                return 0.0, True
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
    return None, False


def _extract_labeled_amount(
    text: str, labels: list[str]
) -> Tuple[float | None, bool]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    for line in text.splitlines():
        if not re.search(rf"\b(?:{label_pattern})s?\b", line, re.IGNORECASE):
            continue
        if re.search(r"\bno\s+(?:other\s+)?(?:tax|charge|cess|levy)", line, re.IGNORECASE):
            return 0.0, True
        if re.search(r"\bno\s+(?:discount|rebate)\b", line, re.IGNORECASE):
            return 0.0, True
        if re.search(r"\b(?:not applicable|n/?a|none|nil|no charge|free)\b", line, re.IGNORECASE):
            return 0.0, True
        match = re.search(r"(?:₹|INR|USD|\$)\s*([0-9][\d,]*(?:\.\d{1,4})?)", line, re.IGNORECASE)
        if match is None and "%" not in line:
            amounts = re.findall(r"([0-9][\d,]*(?:\.\d{1,4})?)", line)
            if amounts:
                return _parse_float(amounts[-1]), True
        if match:
            return _parse_float(match.group(1)), True
    return None, False


def _extract_currency(text: str) -> Tuple[str | None, bool]:
    if re.search(r"\bUSD\b|\$|dollar", text, re.IGNORECASE):
        return "USD", True
    if re.search(r"\bINR\b|₹|\brs\.?(?:\s|$)|\brupees?\b", text, re.IGNORECASE):
        return "INR", True
    return None, False


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
