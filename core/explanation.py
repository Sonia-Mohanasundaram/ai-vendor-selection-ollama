"""
explanation.py
--------------
Rule-based explanation and audit trail generator (no LLM).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd


def build_why_table(df: pd.DataFrame, best_vendor: str) -> pd.DataFrame:
    df2 = df.copy()
    for col in ["total_cost", "delivery_days", "payment_days", "final_score"]:
        if col in df2.columns:
            df2[col] = pd.to_numeric(df2[col], errors="coerce")

    best = df2[df2["vendor_name"] == best_vendor].iloc[0]
    best_cost = float(best["total_cost"])
    best_del = int(best["delivery_days"])
    best_terms = int(best["payment_days"])
    best_score = float(best["final_score"])

    out = df2[
        ["vendor_name", "total_cost", "delivery_days", "payment_days", "final_score"]
    ].copy()
    out["cost_diff_vs_best"] = out["total_cost"] - best_cost
    out["delivery_diff_vs_best"] = out["delivery_days"] - best_del
    out["terms_diff_vs_best"] = out["payment_days"] - best_terms
    out["score_diff_vs_best"] = out["final_score"] - best_score

    out.sort_values("final_score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def generate_explanation(best_vendor: str, df: pd.DataFrame, best_vendor_details: Dict[str, Any] | None = None) -> str:
    """
    Produce a procurement-style explanation (markdown) for the recommended vendor.
    """
    if df.empty or "vendor_name" not in df.columns:
        return "No comparison data available."

    df2 = df.copy()
    for col in ["total_cost", "delivery_days", "payment_days", "final_score"]:
        if col in df2.columns:
            df2[col] = pd.to_numeric(df2[col], errors="coerce")

    best = df2[df2["vendor_name"] == best_vendor].iloc[0]
    n = len(df2)

    # Ranks
    cost_rank = int(df2["total_cost"].rank(method="min", ascending=True)[df2["vendor_name"] == best_vendor].iloc[0])
    del_rank = int(df2["delivery_days"].rank(method="min", ascending=True)[df2["vendor_name"] == best_vendor].iloc[0])
    terms_rank = int(df2["payment_days"].rank(method="min", ascending=False)[df2["vendor_name"] == best_vendor].iloc[0])
    score_rank = int(df2["final_score"].rank(method="min", ascending=False)[df2["vendor_name"] == best_vendor].iloc[0])

    # Winners
    lowest_cost_vendor = str(df2.loc[df2["total_cost"].idxmin(), "vendor_name"])
    fastest_vendor = str(df2.loc[df2["delivery_days"].idxmin(), "vendor_name"])
    best_terms_vendor = str(df2.loc[df2["payment_days"].idxmax(), "vendor_name"])

    reasons: list[str] = []
    if best_vendor == lowest_cost_vendor:
        reasons.append("lowest total landed cost")
    if best_vendor == fastest_vendor:
        reasons.append("fastest delivery")
    if best_vendor == best_terms_vendor:
        reasons.append("best payment terms")
    if not reasons:
        reasons.append("best overall trade-off across cost, delivery, and terms")

    # Gaps to #2
    df_sorted = df2.sort_values("final_score", ascending=False).reset_index(drop=True)
    lead = float(df_sorted.iloc[0]["final_score"]) - float(df_sorted.iloc[1]["final_score"]) if len(df_sorted) > 1 else 0.0

    cost = float(best["total_cost"])
    delivery = int(best["delivery_days"])
    terms = int(best["payment_days"])
    score = float(best["final_score"])

    bullets = "\n".join(
        f"- {r[0].upper() + r[1:]}" for r in reasons
    )

    hidden_bits: list[str] = []
    if isinstance(best_vendor_details, dict):
        cc = float(best_vendor_details.get("credit_cost", 0.0) or 0.0)
        dc = float(best_vendor_details.get("delay_penalty_cost", 0.0) or 0.0)
        mc = float(best_vendor_details.get("missing_data_risk_cost", 0.0) or 0.0)
        if cc > 0:
            hidden_bits.append(f"credit cost Rs.{cc:,.0f} (shorter payment terms vs baseline)")
        if dc > 0:
            hidden_bits.append(f"delay penalty risk Rs.{dc:,.0f} (delivery beyond SLA)")
        if mc > 0:
            hidden_bits.append(f"missing-data risk Rs.{mc:,.0f}")

    hidden_line = (
        "**Hidden costs:** " + "; ".join(hidden_bits) + ".\n\n"
        if hidden_bits
        else "**Hidden costs:** none detected (beyond GST and freight).\n\n"
    )

    return (
        f"**{best_vendor}** is recommended (**rank {score_rank}/{n}**, score **{score:.1f}/100**, "
        f"lead **{lead:.1f}** points).\n\n"
        f"**Reasons:**\n{bullets}\n\n"
        f"**Key values:** total cost Rs.{cost:,.0f}, delivery {delivery} days, payment terms Net {terms} days.\n\n"
        f"{hidden_line}"
        f"**Ranks:** Cost {cost_rank}/{n}, Delivery {del_rank}/{n}, Terms {terms_rank}/{n}."
    )
