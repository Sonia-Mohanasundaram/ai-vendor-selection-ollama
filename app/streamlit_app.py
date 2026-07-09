"""
Streamlit UI: AI Vendor Comparison System (CPU-only, rule-based).

Run:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import os
import hashlib
import sys
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.ingestion import ingest_bytes, preview_file
from core.extraction import extract_fields
from core.normalization import normalize
from core.cost_engine import compute_total_landed_cost, CostConfig
from core.scoring import compute_scores
from core.comparison import build_comparison
from core.explanation import generate_explanation, build_why_table
from core.history import init_db, list_sessions, get_session, save_session, clear_history
from utils.xlsx_writer import df_to_xlsx_bytes


st.set_page_config(page_title="AI Vendor Comparison System", layout="wide")
st.title("AI Vendor Comparison System")

st.write(
    "Upload vendor quotations (PDF, images, CSV, XLSX). "
    "The system extracts key fields, normalizes values, compares vendors, scores them, "
    "and recommends the best option using rule-based logic (no LLMs)."
)

uploaded_files = st.file_uploader(
    "Upload quotation files",
    type=["pdf", "png", "jpg", "jpeg", "csv", "xlsx"],
    accept_multiple_files=True,
)

file_count = len(uploaded_files) if uploaded_files else 0
if uploaded_files and (file_count < 3 or file_count > 10):
    st.warning("Upload between 3 and 10 vendor files for a realistic comparison.")

analyze = st.button(
    "Analyze Quotations",
    type="primary",
    use_container_width=True,
    disabled=not uploaded_files or file_count > 10 or file_count < 3,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "outputs", "history.db")
init_db(DB_PATH)

st.sidebar.title("📜 History")
sessions = list_sessions(DB_PATH, limit=100)
session_labels = {
    s["id"]: f'Analysis {s["id"]} — {s["vendor_count"]} vendors — {s["best_vendor"]} ({s["final_score"]:.1f}) — {str(s["timestamp"])[:10]}'
    for s in sessions
}
selected = st.sidebar.radio(
    "Previous analyses",
    options=["New analysis"] + [s["id"] for s in sessions],
    format_func=lambda x: x if x == "New analysis" else session_labels.get(x, f"Analysis {x}"),
)

if st.sidebar.button("Clear History", use_container_width=True):
    clear_history(DB_PATH)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Assumptions")
usd_to_inr = st.sidebar.number_input("USD → INR rate", min_value=1.0, max_value=500.0, value=83.0, step=0.5)
interest_rate_pct = st.sidebar.slider("Interest rate (p.a.) %", 0.0, 30.0, 12.0, 0.5)
baseline_payment_days = st.sidebar.slider("Baseline payment days", 0, 120, 30, 1)
sla_delivery_days = st.sidebar.slider("SLA delivery days", 1, 120, 14, 1)
delay_penalty_rate_per_day_pct = st.sidebar.slider("Delay risk / day %", 0.0, 1.0, 0.10, 0.05)
delay_penalty_cap_pct = st.sidebar.slider("Delay risk cap %", 0.0, 20.0, 5.0, 0.5)
st.sidebar.caption(
    "Delay risk is a *cost* added when delivery exceeds SLA (capped). "
    "Credit cost is added when payment terms are shorter than baseline."
)

cost_cfg = CostConfig(
    usd_to_inr=float(usd_to_inr),
    interest_rate=float(interest_rate_pct) / 100.0,
    baseline_payment_days=int(baseline_payment_days),
    sla_delivery_days=int(sla_delivery_days),
    delay_penalty_rate_per_day=float(delay_penalty_rate_per_day_pct) / 100.0,
    delay_penalty_cap_pct=float(delay_penalty_cap_pct) / 100.0,
)

def _style_comparison(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    df2 = df.copy()
    for col in ["total_cost", "delivery_days", "payment_days", "final_score"]:
        df2[col] = pd.to_numeric(df2[col], errors="coerce")

    min_cost = df2["total_cost"].min()
    min_delivery = df2["delivery_days"].min()
    max_score = df2["final_score"].max()

    def highlight(row: pd.Series):
        styles = [""] * len(row)
        cols = list(row.index)

        def set_style(col_name: str, style: str):
            if col_name in cols:
                styles[cols.index(col_name)] = style

        if pd.notna(row.get("total_cost")) and row["total_cost"] == min_cost:
            set_style("total_cost", "background-color: #DCFCE7;")  # green
        if pd.notna(row.get("delivery_days")) and row["delivery_days"] == min_delivery:
            set_style("delivery_days", "background-color: #DBEAFE;")  # blue
        if pd.notna(row.get("final_score")) and row["final_score"] == max_score:
            set_style("final_score", "background-color: #FEF3C7;")  # gold

        return styles

    return (
        df2.style.apply(highlight, axis=1)
        .format(
            {
                "total_cost": "Rs.{:,.2f}",
                "delivery_days": "{:.0f}",
                "payment_days": "{:.0f}",
                "cost_score": "{:.2f}",
                "delivery_score": "{:.2f}",
                "terms_score": "{:.2f}",
                "final_score": "{:.2f}",
            }
        )
    )


def _cost_breakdown_df(breakdowns: List[Dict[str, float]]) -> pd.DataFrame:
    if not breakdowns:
        return pd.DataFrame()
    df = pd.DataFrame(breakdowns)
    cols = [
        "vendor_name",
        "base_cost",
        "gst_amount",
        "freight_cost",
        "credit_cost",
        "delay_penalty_cost",
        "missing_data_risk_cost",
        "total_cost",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def _render_file_previews(files: List[Any]) -> None:
    if not files:
        return
    st.subheader("File preview")
    st.caption("Preview is for verification; extraction uses the full document text/OCR.")
    for f in files:
        name = f.name
        b = f.getvalue()
        info = preview_file(b, name)
        with st.expander(name, expanded=False):
            if info["type"] == "pdf":
                import fitz

                try:
                    doc = fitz.open(stream=b, filetype="pdf")
                    page_count = min(2, doc.page_count)
                    for p in range(page_count):
                        page = doc[p]
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        st.image(pix.tobytes("png"), caption=f"Page {p+1}", use_container_width=True)
                    doc.close()
                except Exception as e:
                    st.write(f"PDF preview failed: {e}")
            elif info["type"] == "image":
                st.image(b, caption=name, use_container_width=True)
            elif info["type"] == "table":
                st.dataframe(info["df"], use_container_width=True)
            else:
                st.write("No preview available for this file type.")


def _render_results(results: Dict[str, Any]) -> None:
    comparison_df = pd.DataFrame(results.get("comparison", []))
    best_vendor = results.get("best_vendor", "N/A")
    explanation = results.get("explanation", "")
    why_df = pd.DataFrame(results.get("why_table", []))
    breakdown_df = pd.DataFrame(results.get("cost_breakdown", []))
    vendors = results.get("vendors") or []

    st.subheader("Comparison")
    st.caption("Highlights: lowest cost (green), fastest delivery (blue), best score (gold).")
    if not comparison_df.empty:
        st.dataframe(_style_comparison(comparison_df), use_container_width=True)

    st.subheader("Ranking per metric")
    ranks = comparison_df.copy()
    if not ranks.empty:
        ranks["cost_rank"] = ranks["total_cost"].rank(method="min", ascending=True).astype(int)
        ranks["delivery_rank"] = ranks["delivery_days"].rank(method="min", ascending=True).astype(int)
        ranks["terms_rank"] = ranks["payment_days"].rank(method="min", ascending=False).astype(int)
        ranks["overall_rank"] = ranks["final_score"].rank(method="min", ascending=False).astype(int)
        st.dataframe(
            ranks[["vendor_name", "cost_rank", "delivery_rank", "terms_rank", "overall_rank"]]
            .sort_values("overall_rank")
            .reset_index(drop=True),
            use_container_width=True,
        )

    st.subheader("Recommended Vendor")
    st.success(best_vendor)
    st.write(explanation)

    st.subheader("Why this vendor is best")
    if not why_df.empty:
        st.dataframe(
            why_df.style.format(
                {
                    "total_cost": "Rs.{:,.0f}",
                    "delivery_days": "{:.0f}",
                    "payment_days": "{:.0f}",
                    "final_score": "{:.2f}",
                    "cost_diff_vs_best": "Rs.{:+,.0f}",
                    "delivery_diff_vs_best": "{:+.0f} d",
                    "terms_diff_vs_best": "{:+.0f} d",
                    "score_diff_vs_best": "{:+.2f}",
                }
            ),
            use_container_width=True,
        )

    st.subheader("Hidden cost breakdown (landed cost)")
    if not breakdown_df.empty:
        st.dataframe(
            breakdown_df.style.format(
                {
                    "base_cost": "Rs.{:,.0f}",
                    "gst_amount": "Rs.{:,.0f}",
                    "freight_cost": "Rs.{:,.0f}",
                    "credit_cost": "Rs.{:,.0f}",
                    "delay_penalty_cost": "Rs.{:,.0f}",
                    "missing_data_risk_cost": "Rs.{:,.0f}",
                    "total_cost": "Rs.{:,.0f}",
                }
            ),
            use_container_width=True,
        )

    st.subheader("Export")
    if not comparison_df.empty:
        st.download_button(
            "Download CSV report",
            data=comparison_df.to_csv(index=False).encode("utf-8"),
            file_name="vendor_comparison_report.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "Download Excel report (.xlsx)",
            data=df_to_xlsx_bytes(comparison_df, sheet_name="Vendor Comparison"),
            file_name="vendor_comparison_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if vendors:
        with st.expander("Audit trail (saved)"):
            for v in vendors:
                st.markdown(f"**{v.get('vendor_name', 'Unknown Vendor')}**")
                st.json(v)


if analyze and uploaded_files:
    with st.spinner("Analyzing quotations..."):
        extracted: List[Dict[str, Any]] = []
        errors: list[str] = []
        cost_breakdowns: List[Dict[str, float]] = []
        file_names: List[str] = [f.name for f in uploaded_files]
        uploaded_files_meta: List[Dict[str, Any]] = []

        prog = st.progress(0, text="Processing files...")
        total = len(uploaded_files)

        for i, f in enumerate(uploaded_files, start=1):
            try:
                b = f.getvalue()
                uploaded_files_meta.append(
                    {
                        "name": f.name,
                        "size": len(b),
                        "type": getattr(f, "type", "") or "",
                        "sha256": hashlib.sha256(b).hexdigest(),
                    }
                )
                raw_text = ingest_bytes(b, f.name)
                fields = extract_fields(raw_text, filename=f.name)
                norm = normalize(fields, usd_to_inr=float(usd_to_inr))
                costed, breakdown = compute_total_landed_cost(norm, cfg=cost_cfg)
                extracted.append(costed)

                breakdown_row = dict(breakdown)
                breakdown_row["vendor_name"] = costed.get("vendor_name", f.name)
                cost_breakdowns.append(breakdown_row)
            except Exception as e:
                errors.append(f"{f.name}: {e}")

            prog.progress(int(i * 100 / max(1, total)), text=f"Processed {i}/{total}")

        if errors:
            st.warning("Some files could not be processed:")
            for msg in errors:
                st.write(f"- {msg}")

        if not extracted:
            st.error("No valid quotations were processed.")
        else:
            scored = compute_scores(extracted)
            comparison_df, best_vendor = build_comparison(scored)
            best_details = next((v for v in scored if v.get("vendor_name") == best_vendor), None)
            explanation = generate_explanation(best_vendor, comparison_df, best_vendor_details=best_details)

            st.subheader("Comparison")
            st.caption("Highlights: lowest cost (green), fastest delivery (blue), best score (gold).")
            st.dataframe(_style_comparison(comparison_df), use_container_width=True)

            st.subheader("Ranking per metric")
            ranks = comparison_df.copy()
            ranks["cost_rank"] = ranks["total_cost"].rank(method="min", ascending=True).astype(int)
            ranks["delivery_rank"] = ranks["delivery_days"].rank(method="min", ascending=True).astype(int)
            ranks["terms_rank"] = ranks["payment_days"].rank(method="min", ascending=False).astype(int)
            ranks["overall_rank"] = ranks["final_score"].rank(method="min", ascending=False).astype(int)
            st.dataframe(
                ranks[["vendor_name", "cost_rank", "delivery_rank", "terms_rank", "overall_rank"]]
                .sort_values("overall_rank")
                .reset_index(drop=True),
                use_container_width=True,
            )

            st.subheader("Recommended Vendor")
            st.success(best_vendor)
            st.write(explanation)

            st.subheader("Why this vendor is best")
            why_df = build_why_table(comparison_df, best_vendor)
            st.caption("Diff columns are relative to the recommended vendor (positive cost/delivery diffs are worse).")
            st.dataframe(
                why_df.style.format(
                    {
                        "total_cost": "Rs.{:,.0f}",
                        "delivery_days": "{:.0f}",
                        "payment_days": "{:.0f}",
                        "final_score": "{:.2f}",
                        "cost_diff_vs_best": "Rs.{:+,.0f}",
                        "delivery_diff_vs_best": "{:+.0f} d",
                        "terms_diff_vs_best": "{:+.0f} d",
                        "score_diff_vs_best": "{:+.2f}",
                    }
                ),
                use_container_width=True,
            )

            st.subheader("Hidden cost breakdown (landed cost)")
            cb = _cost_breakdown_df(cost_breakdowns)
            if not cb.empty:
                st.dataframe(
                    cb.style.format(
                        {
                            "base_cost": "Rs.{:,.0f}",
                            "gst_amount": "Rs.{:,.0f}",
                            "freight_cost": "Rs.{:,.0f}",
                            "credit_cost": "Rs.{:,.0f}",
                            "delay_penalty_cost": "Rs.{:,.0f}",
                            "missing_data_risk_cost": "Rs.{:,.0f}",
                            "total_cost": "Rs.{:,.0f}",
                        }
                    ),
                    use_container_width=True,
                )

            st.subheader("Export")
            csv_bytes = comparison_df.to_csv(index=False).encode("utf-8")
            xlsx_bytes = df_to_xlsx_bytes(comparison_df, sheet_name="Vendor Comparison")
            st.download_button(
                "Download CSV report",
                data=csv_bytes,
                file_name="vendor_comparison_report.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                "Download Excel report (.xlsx)",
                data=xlsx_bytes,
                file_name="vendor_comparison_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # Save session history
            output_files_meta = [
                {
                    "name": "vendor_comparison_report.csv",
                    "size": len(csv_bytes),
                    "type": "text/csv",
                },
                {
                    "name": "vendor_comparison_report.xlsx",
                    "size": len(xlsx_bytes),
                    "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                },
            ]
            results_payload = {
                "comparison": comparison_df.to_dict(orient="records"),
                "best_vendor": best_vendor,
                "final_score": float(comparison_df.iloc[0]["final_score"]) if not comparison_df.empty else 0.0,
                "explanation": explanation,
                "why_table": why_df.to_dict(orient="records"),
                "cost_breakdown": cb.to_dict(orient="records") if not cb.empty else [],
                "vendors": scored,
            }
            save_session(
                DB_PATH,
                vendor_count=len(comparison_df),
                best_vendor=best_vendor,
                final_score=float(results_payload["final_score"]),
                data=results_payload,
                file_names=file_names,
                uploaded_files=uploaded_files_meta,
                output_files=output_files_meta,
            )
            st.info("Saved this analysis to History (sidebar).")

            with st.expander("Audit trail (per vendor)"):
                for v in scored:
                    st.markdown(f"**{v.get('vendor_name', 'Unknown Vendor')}**")
                    st.json(
                        {
                            "source_fields": {
                                "delivery_text": v.get("delivery_text"),
                                "payment_terms_text": v.get("payment_terms_text"),
                                "penalty_clause": v.get("penalty_clause"),
                            },
                            "normalized_values": {
                                "quantity": v.get("quantity"),
                                "unit_price_inr": v.get("unit_price"),
                                "base_cost_inr": v.get("base_cost"),
                                "gst_percent": v.get("gst_percent"),
                                "freight_cost_inr": v.get("freight_cost"),
                                "delivery_days": v.get("delivery_days"),
                                "payment_days": v.get("payment_days"),
                            },
                            "hidden_costs": {
                                "gst_amount": v.get("gst_amount"),
                                "credit_cost": v.get("credit_cost"),
                                "delay_penalty_cost": v.get("delay_penalty_cost"),
                                "missing_data_risk_cost": v.get("missing_data_risk_cost"),
                                "total_cost_inr": v.get("total_cost"),
                            },
                            "scoring": {
                                "cost_score": v.get("cost_score"),
                                "delivery_score": v.get("delivery_score"),
                                "terms_score": v.get("terms_score"),
                                "final_score": v.get("final_score"),
                            },
                            "missing_fields": v.get("missing_fields"),
                            "extraction_evidence": v.get("extraction_evidence"),
                        }
                    )

elif selected != "New analysis":
    session = get_session(DB_PATH, int(selected))
    if session:
        files = session.get("file_names") or []
        file_str = ", ".join(files[:6]) + ("..." if len(files) > 6 else "")
        st.caption(
            f"Loaded from history — {session['timestamp']} (UTC), {session['vendor_count']} vendors. Files: {file_str}"
        )
        _render_results(session["data"])

_render_file_previews(uploaded_files or [])
