"""
cost_engine.py
--------------
Computes production-style "total landed cost" with a transparent breakdown.

Total Landed Cost =
    base_cost
  + gst_amount
  + freight_cost
  + credit_cost               (penalizes shorter-than-baseline terms)
  + delay_penalty_cost        (risk cost for slow delivery)
  + missing_data_risk_cost    (small risk premium when key fields missing)

All money values are assumed to be INR by the time this runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class CostConfig:
    usd_to_inr: float = 83.0
    interest_rate: float = 0.12
    baseline_payment_days: int = 30
    sla_delivery_days: int = 14
    delay_penalty_rate_per_day: float = 0.001  # 0.1% of base_cost per day beyond SLA
    delay_penalty_cap_pct: float = 0.05        # cap at 5% of base_cost


def compute_total_landed_cost(vendor: Dict[str, Any], cfg: CostConfig | None = None) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """
    Returns:
        updated_vendor: vendor dict with `total_cost` populated
        breakdown: dict of cost components (INR)
    """
    cfg = cfg or CostConfig()

    base_cost = float(vendor.get("base_cost", vendor.get("total_price", 0.0)) or 0.0)
    gst_percent = float(vendor.get("gst_percent", 18.0) or 0.0)
    freight = float(vendor.get("freight_cost", 0.0) or 0.0)

    gst_amount = round(base_cost * max(0.0, min(100.0, gst_percent)) / 100.0, 2)
    subtotal = base_cost + gst_amount + freight

    payment_days = int(vendor.get("payment_days", vendor.get("payment_terms_days", 30)) or 0)
    credit_cost = _credit_cost(
        amount=subtotal,
        payment_days=payment_days,
        baseline_days=int(cfg.baseline_payment_days),
        interest_rate=float(cfg.interest_rate),
    )

    delivery_days = int(vendor.get("delivery_days", 30) or 30)
    delay_penalty_cost = _delay_penalty_cost(
        base_cost=base_cost,
        delivery_days=delivery_days,
        sla_days=int(cfg.sla_delivery_days),
        rate_per_day=float(cfg.delay_penalty_rate_per_day),
        cap_pct=float(cfg.delay_penalty_cap_pct),
        penalty_clause=str(vendor.get("penalty_clause") or ""),
    )

    missing_data_risk_cost = _missing_data_risk_cost(base_cost, vendor.get("missing_fields"))

    total_cost = round(subtotal + credit_cost + delay_penalty_cost + missing_data_risk_cost, 2)

    updated = dict(vendor)
    updated["total_cost"] = total_cost
    updated["gst_amount"] = gst_amount
    updated["credit_cost"] = credit_cost
    updated["delay_penalty_cost"] = delay_penalty_cost
    updated["missing_data_risk_cost"] = missing_data_risk_cost

    breakdown = {
        "base_cost": round(base_cost, 2),
        "gst_amount": round(gst_amount, 2),
        "freight_cost": round(freight, 2),
        "credit_cost": round(credit_cost, 2),
        "delay_penalty_cost": round(delay_penalty_cost, 2),
        "missing_data_risk_cost": round(missing_data_risk_cost, 2),
        "total_cost": round(total_cost, 2),
    }
    return updated, breakdown


def _credit_cost(amount: float, payment_days: int, baseline_days: int, interest_rate: float) -> float:
    """
    Hidden cost of *short* payment terms.

    If vendor gives fewer than `baseline_days` of credit, buyer effectively pays earlier
    and loses interest on working capital for the missing days.
    """
    missing_days = max(0, int(baseline_days) - int(payment_days))
    if amount <= 0 or missing_days <= 0:
        return 0.0
    return round((amount * missing_days * float(interest_rate)) / 365.0, 2)


def _delay_penalty_cost(
    base_cost: float,
    delivery_days: int,
    sla_days: int,
    rate_per_day: float,
    cap_pct: float,
    penalty_clause: str,
) -> float:
    """
    Risk cost for slow delivery (simple procurement heuristic).

    Uses defaults but tries to parse penalty clause patterns like:
        "Penalty: 0.5% per week, max 5%"
    """
    if base_cost <= 0:
        return 0.0

    parsed = _parse_penalty_clause(penalty_clause)
    if parsed is not None:
        rate_per_day, cap_pct = parsed

    late_days = max(0, int(delivery_days) - int(sla_days))
    if late_days <= 0:
        return 0.0

    raw = base_cost * late_days * float(rate_per_day)
    cap = base_cost * float(cap_pct)
    return round(min(raw, cap), 2)


def _parse_penalty_clause(text: str) -> tuple[float, float] | None:
    """
    Extract (rate_per_day, cap_pct) if clause contains a recognizable pattern.

    Supported examples:
        - "0.5% per week, max 5%"
        - "1% per day upto 10%"
    """
    import re

    if not text or "penalt" not in text.lower():
        return None

    # rate + unit
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*per\s*(day|week)", text, re.IGNORECASE)
    if not m:
        return None
    rate_pct = float(m.group(1)) / 100.0
    unit = m.group(2).lower()
    rate_per_day = rate_pct if unit == "day" else (rate_pct / 7.0)

    cap = None
    m2 = re.search(r"(?:max|cap(?:ped)?|upto|up to)\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
    if m2:
        cap = float(m2.group(1)) / 100.0

    return rate_per_day, (cap if cap is not None else 0.05)


def _missing_data_risk_cost(base_cost: float, missing_fields: Any) -> float:
    """
    Small risk premium when key commercial fields are missing.
    """
    if base_cost <= 0:
        return 0.0

    missing = set(missing_fields or []) if isinstance(missing_fields, list) else set()
    critical = {
        "total_price",
        "unit_price",
        "quantity",
        "gst_percent",
        "freight_cost",
        "delivery_days",
        "payment_terms_days",
        "payment_days",
    }
    count = len(missing.intersection(critical))
    # 0.25% per missing critical field, capped at 2%
    pct = min(0.02, 0.0025 * count)
    return round(base_cost * pct, 2)
