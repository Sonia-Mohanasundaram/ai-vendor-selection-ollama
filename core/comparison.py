"""
comparison.py
-------------
Builds the comparison DataFrame and determines the best vendor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd


def build_comparison(scored_vendors: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, str]:
    """
    Create a comparison DataFrame with procurement-friendly fields and return the best vendor.

    Output columns:
        vendor_name, total_cost, delivery_days, payment_days,
        cost_score, delivery_score, terms_score, final_score
    """
    if not scored_vendors:
        return pd.DataFrame(), "N/A"

    df = pd.DataFrame(scored_vendors).copy()
    df["payment_days"] = df.get("payment_days", df.get("payment_terms_days", 0))

    cols = [
        "vendor_name",
        "total_cost",
        "delivery_days",
        "payment_days",
        "cost_score",
        "delivery_score",
        "terms_score",
        "final_score",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = 0
    df = df[cols]

    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0.0)
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce").fillna(0).astype(int)
    df["payment_days"] = pd.to_numeric(df["payment_days"], errors="coerce").fillna(0).astype(int)
    df["final_score"] = pd.to_numeric(df["final_score"], errors="coerce").fillna(0.0)

    df.sort_values("final_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    best_vendor = str(df.iloc[0]["vendor_name"])
    return df, best_vendor

