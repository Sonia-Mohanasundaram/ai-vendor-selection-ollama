"""Streamlit interface for Ollama-powered quotation evaluation."""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Any

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.ai_evaluation import (
    OllamaEvaluationError,
    evaluate_vendors,
    extract_constraints,
    vendor_evaluation_dict,
)
from core.extraction import extract_fields
from core.history import clear_history, get_session, init_db, list_sessions, save_session
from core.ingestion import ingest_bytes, preview_file
from core.normalization import normalize
from core.quotation import to_quotation_evidence
from utils.xlsx_writer import df_to_xlsx_bytes


st.set_page_config(page_title="AI Vendor Comparison System", layout="wide")
st.title("AI Vendor Comparison System")
st.write(
    "Upload vendor quotations and let a local Ollama model compare the extracted evidence "
    "against your purchase priorities. No paid AI API is used."
)
usd_to_inr = st.sidebar.number_input(
    "USD → INR conversion rate", min_value=1.0, max_value=500.0, value=83.0, step=0.5
)

uploaded_files = st.file_uploader(
    "Upload quotation files",
    type=["pdf", "docx", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "csv", "xlsx"],
    accept_multiple_files=True,
)
requirements = st.text_area(
    "Purchase priorities and mandatory constraints",
    placeholder="For example: prioritize delivery within 10 days; maximum budget ₹2,00,000.",
    max_chars=2000,
)
file_count = len(uploaded_files or [])
analyze = st.button(
    "Evaluate with Ollama",
    type="primary",
    use_container_width=True,
    disabled=file_count < 2 or file_count > 10,
)
if uploaded_files and file_count < 2:
    st.info("Upload at least 2 quotation files to compare.")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "outputs", "history.db")
init_db(DB_PATH)
st.sidebar.title("📜 History")
sessions = list_sessions(DB_PATH, limit=100)
session_labels = {
    session["id"]: (
        f'Analysis {session["id"]} — {session["vendor_count"]} vendors — '
        f'{session["best_vendor"]} — {str(session["timestamp"])[:10]}'
    )
    for session in sessions
}
selected = st.sidebar.radio(
    "Previous analyses",
    options=["New analysis"] + [session["id"] for session in sessions],
    format_func=lambda value: value if value == "New analysis" else session_labels.get(value, f"Analysis {value}"),
)
if st.sidebar.button("Clear History", use_container_width=True):
    clear_history(DB_PATH)
    st.rerun()


def _render_results(results: dict[str, Any]) -> None:
    if results.get("inconclusive"):
        st.warning("No verified winner. Review the limitations and missing evidence below.")
    elif results.get("best_vendor"):
        st.success(f"Recommended vendor: {results['best_vendor']}")

    st.write(results.get("evaluation_summary", ""))
    for warning in results.get("constraint_warnings", []):
        st.warning(warning)
    if results.get("requirements"):
        st.caption(f"Requirements: {results['requirements']}")
    constraints = results.get("constraints") or {}
    enforced = []
    if constraints.get("max_budget_inr") is not None:
        enforced.append(f"Maximum budget ₹{constraints['max_budget_inr']:,.2f}")
    if constraints.get("max_delivery_days") is not None:
        enforced.append(f"Delivery within {constraints['max_delivery_days']:g} days")
    if enforced:
        st.info("Hard constraints checked: " + "; ".join(enforced))

    vendors = results.get("vendors", [])
    comparison = pd.DataFrame(
        [
            {
                "Rank": vendor["rank"],
                "Vendor": vendor["vendor_name"] or "Vendor name not extracted",
                "Recommendation": vendor["recommendation_status"].replace("_", " "),
                "Total cost (INR)": vendor.get("total_cost"),
                "Delivery days": vendor.get("delivery_days"),
                "Payment days": vendor.get("payment_days"),
            }
            for vendor in vendors
        ]
    )
    if not comparison.empty:
        st.subheader("AI-ranked comparison")
        st.dataframe(comparison, use_container_width=True, hide_index=True)

    if results.get("alternative_vendor"):
        st.info(f"Alternative to consider: {results['alternative_vendor'] or 'Vendor name not extracted'}")

    st.subheader("Vendor evaluations")
    for vendor in vendors:
        vendor_name = vendor.get("vendor_name") or "Vendor name not extracted"
        with st.expander(f"#{vendor['rank']} {vendor_name} — {vendor['recommendation_status'].replace('_', ' ')}"):
            st.markdown(f"**Reasoning:** {vendor['explanation']}")
            st.markdown(
                f"**Extracted cost fields (INR):** Base {vendor.get('base_amount')}; "
                f"GST {vendor.get('gst_percent')}% / {vendor.get('gst_amount')}; "
                f"freight {vendor.get('freight')}; other taxes {vendor.get('other_taxes')}; "
                f"additional charges {vendor.get('additional_charges')}."
            )
            st.markdown(
                f"**Cost:** {vendor['cost_comparison']}  \n"
                f"**Delivery:** {vendor['delivery_comparison']}  \n"
                f"**Payment terms:** {vendor['payment_terms_comparison']}"
            )
            st.markdown("**Advantages**")
            st.write(vendor.get("advantages") or ["None identified"])
            st.markdown("**Disadvantages**")
            st.write(vendor.get("disadvantages") or ["None identified"])
            st.markdown("**Risks**")
            st.write(vendor.get("risks") or ["None identified"])
            st.markdown("**Extraction / consistency warnings**")
            st.write(vendor.get("data_warnings") or ["None identified"])
            missing = list(dict.fromkeys(
                (vendor.get("missing_information") or []) + (vendor.get("missing_fields") or [])
            ))
            st.markdown("**Missing information**")
            st.write(missing or ["None identified"])
            st.caption(f"Confidence / uncertainty: {vendor['confidence_explanation']}")

    if vendors:
        report = pd.DataFrame(
            [
                {
                    "Rank": vendor["rank"],
                    "Vendor": vendor.get("vendor_name") or "Vendor name not extracted",
                    "Recommendation": vendor["recommendation_status"],
                    "Total cost (INR)": vendor.get("total_cost"),
                    "Base amount (INR)": vendor.get("base_amount"),
                    "GST %": vendor.get("gst_percent"),
                    "GST amount (INR)": vendor.get("gst_amount"),
                    "Freight (INR)": vendor.get("freight"),
                    "Other taxes (INR)": vendor.get("other_taxes"),
                    "Additional charges (INR)": vendor.get("additional_charges"),
                    "Delivery days": vendor.get("delivery_days"),
                    "Payment days": vendor.get("payment_days"),
                    "Reasoning": vendor["explanation"],
                    "Risks": "; ".join(vendor.get("risks") or []),
                    "Missing information": "; ".join(missing for missing in (
                        vendor.get("missing_information") or []
                    ) + (vendor.get("missing_fields") or [])),
                    "Confidence": vendor["confidence_explanation"],
                    "Extraction warnings": "; ".join(vendor.get("data_warnings") or []),
                }
                for vendor in vendors
            ]
        )
        st.subheader("Export")
        st.download_button(
            "Download CSV report",
            data=report.to_csv(index=False).encode("utf-8"),
            file_name="vendor_evaluation_report.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "Download Excel report (.xlsx)",
            data=df_to_xlsx_bytes(report, sheet_name="AI Evaluation"),
            file_name="vendor_evaluation_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        with st.expander("Audit trail (extracted evidence)"):
            for vendor in vendors:
                st.markdown(f"**{vendor.get('vendor_name') or 'Vendor name not extracted'}**")
                st.json(vendor)


if analyze and uploaded_files:
    with st.spinner("Extracting quotations and evaluating with Ollama..."):
        extracted: list[dict[str, Any]] = []
        file_names = [file.name for file in uploaded_files]
        uploaded_files_meta: list[dict[str, Any]] = []
        errors: list[str] = []
        progress = st.progress(0, text="Processing quotations...")
        for index, file in enumerate(uploaded_files, start=1):
            try:
                contents = file.getvalue()
                raw_text = ingest_bytes(contents, file.name)
                fields = extract_fields(raw_text, filename=file.name)
                normalized = normalize(fields, usd_to_inr=float(usd_to_inr))
                normalized["source_file"] = file.name
                extracted.append(normalized)
                uploaded_files_meta.append(
                    {
                        "name": file.name,
                        "size": len(contents),
                        "type": getattr(file, "type", "") or "",
                        "sha256": hashlib.sha256(contents).hexdigest(),
                    }
                )
            except Exception as exc:
                errors.append(f"{file.name}: {exc}")
            progress.progress(int(index * 100 / len(uploaded_files)), text=f"Processed {index}/{len(uploaded_files)}")

        for error in errors:
            st.warning(error)

        if len(extracted) < 2:
            st.error("At least 2 valid quotations are required for an AI evaluation.")
        else:
            try:
                quotes = [
                    to_quotation_evidence(item, f"vendor-{index}")
                    for index, item in enumerate(extracted, start=1)
                ]
                evaluation, constraint_warnings = evaluate_vendors(quotes, requirements)
                by_id = {quote["vendor_id"]: quote for quote in quotes}
                ranked = []
                for item in evaluation.ranked_vendors:
                    ranked.append(
                        {
                            **by_id[item.vendor_id],
                            **vendor_evaluation_dict(item),
                            "id": item.vendor_id,
                        }
                    )
                best = next(
                    (vendor for vendor in ranked if vendor["id"] == evaluation.best_recommendation_vendor_id),
                    None,
                )
                alternative = next(
                    (vendor for vendor in ranked if vendor["id"] == evaluation.alternative_vendor_id),
                    None,
                )
                payload = {
                    "vendors": ranked,
                    "best_vendor": (
                        (best.get("vendor_name") or "Vendor name not extracted") if best else "Inconclusive"
                    ),
                    "alternative_vendor": (
                        (alternative.get("vendor_name") or "Vendor name not extracted")
                        if alternative else None
                    ),
                    "inconclusive": evaluation.inconclusive,
                    "evaluation_summary": evaluation.overall_explanation,
                    "requirements": requirements,
                    "constraints": extract_constraints(requirements),
                    "constraint_warnings": constraint_warnings,
                }
                output = pd.DataFrame(
                    [
                        {
                            "rank": vendor["rank"],
                            "vendor_name": vendor["vendor_name"],
                            "recommendation_status": vendor["recommendation_status"],
                            "total_cost": vendor["total_cost"],
                            "delivery_days": vendor["delivery_days"],
                            "payment_days": vendor["payment_days"],
                            "explanation": vendor["explanation"],
                        }
                        for vendor in ranked
                    ]
                )
                csv_data = output.to_csv(index=False).encode("utf-8")
                xlsx_data = df_to_xlsx_bytes(output, sheet_name="AI Evaluation")
                output_files = [
                    {"name": "vendor_evaluation_report.csv", "size": len(csv_data), "type": "text/csv"},
                    {
                        "name": "vendor_evaluation_report.xlsx",
                        "size": len(xlsx_data),
                        "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    },
                ]
                results_payload = {**payload, "comparison": output.to_dict(orient="records")}
                save_session(
                    DB_PATH,
                    vendor_count=len(ranked),
                    best_vendor=payload["best_vendor"],
                    final_score=0.0,
                    data=results_payload,
                    file_names=file_names,
                    uploaded_files=uploaded_files_meta,
                    output_files=output_files,
                )
                st.info("Saved this evaluation to History.")
                _render_results(results_payload)
            except OllamaEvaluationError as exc:
                st.error(str(exc))

elif selected != "New analysis":
    session = get_session(DB_PATH, int(selected))
    if session:
        st.caption(f"Loaded from history — {session['timestamp']} (UTC), {session['vendor_count']} vendors.")
        if "evaluation_summary" not in session["data"]:
            st.warning("This saved result used the previous rule-based scoring system.")
        else:
            _render_results(session["data"])

if uploaded_files:
    st.subheader("File preview")
    st.caption("Preview is for verification; extraction uses the full document text/OCR.")
    for file in uploaded_files:
        info = preview_file(file.getvalue(), file.name)
        with st.expander(file.name, expanded=False):
            if info["type"] == "pdf":
                import fitz

                try:
                    document = fitz.open(stream=file.getvalue(), filetype="pdf")
                    for page_number in range(min(2, document.page_count)):
                        pixmap = document[page_number].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        st.image(pixmap.tobytes("png"), caption=f"Page {page_number + 1}", use_container_width=True)
                    document.close()
                except Exception as exc:
                    st.error(f"PDF preview failed: {exc}")
            elif info["type"] == "image":
                st.image(file.getvalue(), caption=file.name, use_container_width=True)
            elif info["type"] == "table":
                st.dataframe(info["df"], use_container_width=True)
            else:
                st.write("Preview is available for uploaded images and tables.")
