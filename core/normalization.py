"""
normalization.py
----------------
Normalizes extracted values into comparable units.

Rules:
    - Convert all currency to INR (assume 1 USD = 83 INR)
    - Convert delivery/payment text -> numeric days
    - Derive a normalized `base_cost` used by the cost engine
"""

from __future__ import annotations

from typing import Any, Dict


DEFAULT_USD_TO_INR = 83.0


def normalize(data: Dict[str, Any], usd_to_inr: float = DEFAULT_USD_TO_INR) -> Dict[str, Any]:
    normalized = dict(data)

    currency = str(normalized.get("currency", "INR")).upper()
    fx = float(usd_to_inr) if currency == "USD" else 1.0
    normalized["fx_rate_to_inr"] = fx
    normalized["currency_original"] = currency

    # Monetary values -> INR
    for k in ("unit_price", "total_price", "freight_cost"):
        normalized[k] = round(float(normalized.get(k, 0.0)) * fx, 2)

    # Derive total_price if missing but unit_price + quantity exist
    qty = int(normalized.get("quantity", 1) or 1)
    if normalized.get("total_price", 0.0) == 0.0 and float(normalized.get("unit_price", 0.0)) > 0:
        normalized["total_price"] = round(float(normalized["unit_price"]) * qty, 2)

    gst_pct = float(normalized.get("gst_percent", normalized.get("gst", 18.0)))
    gst_pct = max(0.0, min(100.0, gst_pct))
    normalized["gst_percent"] = gst_pct

    # Parse delivery/payment text (if present)
    delivery_text = str(normalized.get("delivery_text") or "")
    payment_text = str(normalized.get("payment_terms_text") or "")

    try:
        from utils.date_parser import parse_delivery_text_to_days, parse_payment_terms_to_days
    except Exception:
        parse_delivery_text_to_days = lambda _t: None
        parse_payment_terms_to_days = lambda _t: None

    delivery_days_from_text = parse_delivery_text_to_days(delivery_text)
    payment_days_from_text = parse_payment_terms_to_days(payment_text)

    # Ensure day values are sane
    delivery_days = int(normalized.get("delivery_days", 30) or 30)
    payment_terms_days = int(normalized.get("payment_terms_days", 30) or 30)

    if delivery_days_from_text is not None:
        delivery_days = int(delivery_days_from_text)
    if payment_days_from_text is not None:
        payment_terms_days = int(payment_days_from_text)

    normalized["delivery_days"] = max(1, delivery_days)
    normalized["payment_terms_days"] = max(0, payment_terms_days)
    normalized["payment_days"] = normalized["payment_terms_days"]

    # Base cost used by cost engine (pre-GST, pre-hidden costs)
    normalized["base_cost"] = float(normalized.get("total_price", 0.0) or 0.0)

    # Display currency (after normalization everything is INR)
    normalized["currency_normalized"] = "INR"
    return normalized
