"""
scoring.py
----------
Weighted scoring engine (0-100) for vendor quotations.

Final Score =
    (0.60 * Cost Score) +
    (0.25 * Delivery Score) +
    (0.15 * Terms Score)

Rules:
    - Lower total_cost -> higher Cost Score
    - Lower delivery_days -> higher Delivery Score
    - Higher payment_terms_days -> higher Terms Score
    - Missing values are penalized using `missing_fields`
"""

from __future__ import annotations

from typing import Any, Dict, List


WEIGHT_COST = 0.60
WEIGHT_DELIVERY = 0.25
WEIGHT_TERMS = 0.15


def compute_scores(vendors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not vendors:
        return []

    costs = [float(v.get("total_cost", 0.0)) for v in vendors]
    deliveries = [int(v.get("delivery_days", 0) or 0) for v in vendors]
    terms = [int(v.get("payment_days", v.get("payment_terms_days", 0)) or 0) for v in vendors]

    scored: list[dict[str, Any]] = []
    for v in vendors:
        row = dict(v)

        cost_score = _invert_minmax(float(row.get("total_cost", 0.0)), costs)
        delivery_score = _invert_minmax(int(row.get("delivery_days", 0) or 0), deliveries)
        terms_score = _normal_minmax(int(row.get("payment_days", row.get("payment_terms_days", 0)) or 0), terms)

        cost_score *= _cost_penalty(row)
        delivery_score *= _delivery_penalty(row)
        terms_score *= _terms_penalty(row)

        final_score = (
            WEIGHT_COST * cost_score
            + WEIGHT_DELIVERY * delivery_score
            + WEIGHT_TERMS * terms_score
        )

        row["cost_score"] = round(cost_score, 2)
        row["delivery_score"] = round(delivery_score, 2)
        row["terms_score"] = round(terms_score, 2)
        row["final_score"] = round(final_score, 2)
        scored.append(row)

    return scored


def _invert_minmax(value: float, all_values: List[float]) -> float:
    """Lower is better -> 0..100."""
    valid = [v for v in all_values if v is not None]
    if not valid:
        return 0.0
    min_v, max_v = min(valid), max(valid)
    if max_v == min_v:
        return 100.0 if max_v > 0 else 0.0
    return max(0.0, min(100.0, ((max_v - value) / (max_v - min_v)) * 100.0))


def _normal_minmax(value: float, all_values: List[float]) -> float:
    """Higher is better -> 0..100."""
    valid = [v for v in all_values if v is not None]
    if not valid:
        return 0.0
    min_v, max_v = min(valid), max(valid)
    if max_v == min_v:
        return 100.0 if max_v > 0 else 0.0
    return max(0.0, min(100.0, ((value - min_v) / (max_v - min_v)) * 100.0))


def _missing_set(vendor: Dict[str, Any]) -> set[str]:
    missing = vendor.get("missing_fields") or []
    return set(missing) if isinstance(missing, list) else set()


def _cost_penalty(vendor: Dict[str, Any]) -> float:
    missing = _missing_set(vendor)
    penalty = 1.0
    if float(vendor.get("total_cost", 0.0)) <= 0:
        return 0.0

    if "total_price" in missing and "unit_price" in missing:
        penalty *= 0.70
    elif "total_price" in missing or "unit_price" in missing:
        penalty *= 0.85

    if "gst_percent" in missing:
        penalty *= 0.90
    if "freight_cost" in missing:
        penalty *= 0.95

    return penalty


def _delivery_penalty(vendor: Dict[str, Any]) -> float:
    missing = _missing_set(vendor)
    if "delivery_days" in missing:
        return 0.70
    return 1.0


def _terms_penalty(vendor: Dict[str, Any]) -> float:
    missing = _missing_set(vendor)
    if "payment_terms_days" in missing:
        return 0.70
    return 1.0
