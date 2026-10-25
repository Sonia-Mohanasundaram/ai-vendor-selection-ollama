"""Normalize extracted quotation values without filling missing facts."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from utils.date_parser import parse_delivery_text_to_days, parse_payment_terms_to_days


DEFAULT_USD_TO_INR = 83.0
CENT = Decimal("0.01")
MONETARY_FIELDS = (
    "unit_price",
    "total_price",
    "taxable_amount",
    "gst_amount",
    "quoted_total",
    "discount_amount",
    "freight_cost",
    "other_taxes",
    "additional_charges",
)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(str(value).replace(",", "").replace("₹", "").strip())
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _days(value: Any) -> int | None:
    parsed = _number(value)
    if parsed is None or parsed < 0:
        return None
    return int(parsed)


def _money(value: float) -> float:
    try:
        return float(Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError("Monetary value cannot be represented safely.") from exc


def normalize(data: dict[str, Any], usd_to_inr: float = DEFAULT_USD_TO_INR) -> dict[str, Any]:
    if not math.isfinite(float(usd_to_inr)) or float(usd_to_inr) <= 0:
        raise ValueError("USD-to-INR conversion rate must be a finite positive number.")
    normalized = dict(data)
    missing = set(data.get("missing_fields") or [])
    warnings = list(data.get("data_warnings") or [])
    confidence = dict(data.get("extraction_confidence") or {})
    field_status = dict(data.get("field_status") or {})
    currency = str(data.get("currency_original") or data.get("currency") or "").strip().upper()
    currency_known = currency in {"INR", "USD"} and "currency" not in missing
    fx = float(usd_to_inr) if currency == "USD" else 1.0
    normalized["currency_original"] = currency or None
    normalized["fx_rate_to_inr"] = fx if currency_known else None
    normalized["currency_normalized"] = "INR" if currency_known else None

    for field in MONETARY_FIELDS:
        amount = None if field in missing or not currency_known else _number(data.get(field))
        if amount is not None and amount < 0:
            warnings.append(f"Extracted {field} is negative and needs verification.")
            amount = None
        normalized[field] = _money(amount * fx) if amount is not None else None
        if amount is None:
            missing.add(field)
            if data.get(field) not in (None, ""):
                field_status[field] = "unknown"

    quantity = None if "quantity" in missing else _days(data.get("quantity"))
    if quantity is None:
        missing.add("quantity")
    elif quantity <= 0:
        warnings.append("Extracted quantity must be greater than zero.")
        quantity = None
        missing.add("quantity")
    normalized["quantity"] = quantity

    base_cost = normalized["total_price"]
    if base_cost is None and quantity is not None and normalized["unit_price"] is not None:
        base_cost = _money(quantity * normalized["unit_price"])
        normalized["total_price"] = base_cost
        missing.discard("total_price")
        evidence = dict(normalized.get("extraction_evidence") or {})
        evidence["total_price"] = "Calculated from extracted quantity and unit price"
        normalized["extraction_evidence"] = evidence
        confidence["total_price"] = "calculated"
        field_status["total_price"] = "calculated"
    normalized["base_cost"] = base_cost

    discount_amount = normalized["discount_amount"]
    taxable_amount = normalized["taxable_amount"]
    if taxable_amount is None and base_cost is not None and discount_amount is not None:
        taxable_amount = _money(max(0.0, base_cost - discount_amount))
        normalized["taxable_amount"] = taxable_amount
        missing.discard("taxable_amount")
        confidence["taxable_amount"] = "calculated"
        field_status["taxable_amount"] = "calculated"
        evidence = dict(normalized.get("extraction_evidence") or {})
        evidence["taxable_amount"] = "Calculated from extracted base amount and discount"
        normalized["extraction_evidence"] = evidence

    gst_percent = None if "gst_percent" in missing else _number(
        data.get("gst_percent", data.get("gst"))
    )
    if gst_percent is not None and not 0 <= gst_percent <= 100:
        warnings.append("Extracted GST percentage is outside the valid range.")
        gst_percent = None
    normalized["gst_percent"] = gst_percent
    if gst_percent is None:
        missing.add("gst_percent")

    gst_amount = normalized["gst_amount"]
    gst_basis = taxable_amount if taxable_amount is not None else base_cost
    if gst_amount is None and gst_basis is not None and gst_percent is not None:
        if data.get("tax_inclusive") is True:
            gst_amount = _money(gst_basis * gst_percent / (100 + gst_percent))
        else:
            gst_amount = _money(gst_basis * gst_percent / 100)
        normalized["gst_amount"] = gst_amount
        missing.discard("gst_amount")
        evidence = dict(normalized.get("extraction_evidence") or {})
        evidence["gst_amount"] = "Calculated from extracted base amount and GST percentage"
        normalized["extraction_evidence"] = evidence
        confidence["gst_amount"] = "calculated"
        field_status["gst_amount"] = "calculated"

    delivery_days = None if "delivery_days" in missing else _days(data.get("delivery_days"))
    if delivery_days is None:
        delivery_days = parse_delivery_text_to_days(
            str(data.get("delivery_text") or data.get("delivery_days") or "")
        )
    normalized["delivery_days"] = delivery_days
    if delivery_days is None:
        missing.add("delivery_days")
    else:
        missing.discard("delivery_days")
        if field_status.get("delivery_days") in {None, "unknown", "not_provided"}:
            field_status["delivery_days"] = "source_backed"

    payment_days = None if "payment_terms_days" in missing else _days(data.get("payment_terms_days"))
    if payment_days is None:
        payment_days = parse_payment_terms_to_days(
            str(data.get("payment_terms_text") or data.get("payment_terms_days") or "")
        )
    normalized["payment_terms_days"] = payment_days
    normalized["payment_days"] = payment_days
    if payment_days is None:
        missing.add("payment_terms_days")
    else:
        missing.discard("payment_terms_days")
        if field_status.get("payment_terms_days") in {None, "unknown", "not_provided"}:
            field_status["payment_terms_days"] = "source_backed"

    normalized["currency"] = "INR" if currency_known else None
    normalized["tax_inclusive"] = data.get("tax_inclusive")
    if not currency_known:
        missing.add("currency")
        field_status["currency"] = (
            "unknown" if currency else "not_provided"
        )
        warnings.append(
            f"Source currency ({currency or 'unknown'}) cannot be normalized safely."
        )

    normalized["missing_fields"] = sorted(missing)
    normalized["data_warnings"] = list(dict.fromkeys(warnings))
    normalized["extraction_confidence"] = confidence
    normalized["field_status"] = field_status
    return normalized
