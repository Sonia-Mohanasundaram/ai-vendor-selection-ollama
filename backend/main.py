
from __future__ import annotations
import os
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from backend import models, schemas, crud
from backend.database import SessionLocal, engine, Base
from backend.migrations import ensure_analysis_columns, ensure_uploaded_files_columns
from typing import Any, List
import datetime
import hashlib
import logging
import math
import pandas as pd

from core.ai_evaluation import (
    OllamaEvaluationError,
    evaluate_vendors,
    extract_constraints,
    vendor_evaluation_dict,
)
from core.extraction import extract_fields
from core.history import init_db, save_session
from core.ingestion import ingest_bytes
from core.normalization import normalize
from core.quotation import to_quotation_evidence
from utils.xlsx_writer import df_to_xlsx_bytes

Base.metadata.create_all(bind=engine)
try:
    ensure_analysis_columns(engine)
    ensure_uploaded_files_columns(engine)
except Exception as _e:
    # Best-effort only; analysis should still run even if schema sync fails.
    # (e.g., insufficient privileges on managed Postgres)
    pass
app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- File Upload Endpoint ---
@app.post("/upload_file", response_model=schemas.UploadedFileResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    content = await file.read()
    upload_time = datetime.datetime.utcnow().isoformat()
    # Optionally, save file content to disk or process as needed
    db_file = crud.save_uploaded_file(db, schemas.UploadedFileCreate(
        filename=file.filename,
        content_type=file.content_type,
        upload_time=upload_time,
        output_json=None
    ))
    return db_file

# --- Get All Uploaded Files ---
@app.get("/uploaded_files", response_model=List[schemas.UploadedFileResponse])
def get_uploaded_files(db: Session = Depends(get_db)):
    return crud.get_all_uploaded_files(db)

# --- Analysis Endpoints ---
@app.post("/analysis", response_model=schemas.AnalysisResponse)
def create_analysis(analysis: schemas.AnalysisCreate, db: Session = Depends(get_db)):
    return crud.save_analysis(db, analysis)

@app.get("/analysis", response_model=List[schemas.AnalysisResponse])
def read_analysis(db: Session = Depends(get_db)):
    return crud.get_all_analysis(db)


APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(APP_ROOT, "data", "outputs", "history.db")
logger = logging.getLogger(__name__)


def _analysis_from_uploads(
    files: list[UploadFile],
    usd_to_inr: float,
    requirements: str,
    compute_output_files_meta: bool = False,
) -> dict[str, Any]:
    if not math.isfinite(float(usd_to_inr)) or float(usd_to_inr) <= 0:
        raise HTTPException(
            status_code=422,
            detail="USD-to-INR conversion rate must be a finite positive number.",
        )
    extracted: list[dict[str, Any]] = []
    file_meta: list[dict[str, Any]] = []
    file_errors: list[dict[str, Any]] = []

    for idx, f in enumerate(files):
        filename = f.filename or f"file-{idx + 1}"
        try:
            b = f.file.read()
            if not b:
                raise ValueError("Empty file")

            logger.info(
                "Received quotation filename=%s size_bytes=%s content_type=%s",
                filename,
                len(b),
                f.content_type or "unknown",
            )
            raw_text = ingest_bytes(b, filename)
            fields = extract_fields(raw_text, filename=filename)
            norm = normalize(fields, usd_to_inr=float(usd_to_inr))

            norm["source_file"] = filename
            extracted.append(norm)
            logger.info(
                "Quotation parsed filename=%s present_fields=%s missing_fields=%s warning_count=%s",
                filename,
                sorted(
                    key for key, value in fields.items()
                    if value is not None and key not in {"extraction_evidence", "missing_fields"}
                ),
                norm.get("missing_fields", []),
                len(norm.get("data_warnings", [])),
            )

            file_meta.append(
                {
                    "name": filename,
                    "size": len(b),
                    "type": f.content_type or "",
                    "sha256": hashlib.sha256(b).hexdigest(),
                }
            )
        except Exception as e:
            logger.exception("Quotation processing failed for %s: %s", filename, e)
            file_errors.append({"name": filename, "error": str(e)})
            continue

    if len(extracted) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Need at least 2 valid quotations to compare.",
                "processed": len(extracted),
                "errors": file_errors,
            },
        )

    quotes = [
        to_quotation_evidence(vendor, f"vendor-{index}")
        for index, vendor in enumerate(extracted, start=1)
    ]
    evaluation, constraint_warnings = evaluate_vendors(quotes, requirements)
    vendor_by_id = {quote["vendor_id"]: quote for quote in quotes}
    evaluation_by_id = {item.vendor_id: vendor_evaluation_dict(item) for item in evaluation.ranked_vendors}
    ui_vendors = [
        {
            **vendor_by_id[item.vendor_id],
            **evaluation_by_id[item.vendor_id],
            "id": item.vendor_id,
        }
        for item in evaluation.ranked_vendors
    ]
    best_id = evaluation.best_recommendation_vendor_id
    best = next((vendor for vendor in ui_vendors if vendor["id"] == best_id), None)
    alternative = next(
        (vendor for vendor in ui_vendors if vendor["id"] == evaluation.alternative_vendor_id),
        None,
    )
    comparison_df = pd.DataFrame(
        [
            {
                "rank": vendor["rank"],
                "vendor_name": vendor["vendor_name"],
                "total_cost": vendor["total_cost"],
                "delivery_days": vendor["delivery_days"],
                "payment_days": vendor["payment_days"],
                "recommendation_status": vendor["recommendation_status"],
                "explanation": vendor["explanation"],
            }
            for vendor in ui_vendors
        ]
    )
    best_vendor_name = (
        best["vendor_name"] or "Vendor name not extracted"
        if best
        else "Inconclusive"
    )

    output_files_meta: list[dict[str, Any]] = []
    if compute_output_files_meta:
        csv_bytes = comparison_df.to_csv(index=False).encode("utf-8")
        xlsx_bytes = df_to_xlsx_bytes(comparison_df, sheet_name="Vendor Comparison")
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

    created_at_ms = int(time.time() * 1000)
    result: dict[str, Any] = {
        "id": f"analysis-{created_at_ms}",
        "title": f"{len(ui_vendors)}-vendor analysis",
        "createdAt": created_at_ms,
        "vendors": ui_vendors,
        "best": best,
        "alternative": alternative,
        "inconclusive": evaluation.inconclusive,
        "evaluation_summary": evaluation.overall_explanation,
        "requirements": requirements,
        "constraints": extract_constraints(requirements),
        "constraint_warnings": constraint_warnings,
        "explanation": [evaluation.overall_explanation],
        "differences": [],
        "files": file_meta,
        "output_files": output_files_meta,
        "file_errors": file_errors,
        "audit": {
            "best_vendor": best_vendor_name,
            "comparison": comparison_df.to_dict(orient="records"),
            "vendors_raw": quotes,
        },
    }
    return result


app = FastAPI(title="Vendor Selection API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(
    files: list[UploadFile] = File(...),
    requirements: str = Form("", max_length=2000),
    usd_to_inr: float = Form(83.0),
    interest_rate_pct: float = Form(12.0),
    baseline_payment_days: int = Form(30),
    sla_delivery_days: int = Form(14),
    delay_penalty_rate_per_day_pct: float = Form(0.10),
    delay_penalty_cap_pct: float = Form(5.0),
    save_history_flag: bool = Form(True),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    init_db(DB_PATH)
    try:
        result = _analysis_from_uploads(
            files=files,
            usd_to_inr=float(usd_to_inr),
            requirements=requirements,
            compute_output_files_meta=bool(save_history_flag),
        )
    except OllamaEvaluationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


    if save_history_flag:
        vendors = result.get("vendors") or []
        best_vendor = (
            (result.get("best") or {}).get("vendor_name")
            or ((result.get("best") or {}).get("id") if result.get("best") else None)
            or "Inconclusive"
        )
        final_score = 0.0
        save_session(
            DB_PATH,
            vendor_count=len(vendors),
            best_vendor=str(best_vendor),
            final_score=float(final_score),
            data=result,
            file_names=[(f.get("name") or "") for f in (result.get("files") or [])],
            uploaded_files=(result.get("files") or []),
            output_files=(result.get("output_files") or []),
        )
        # --- Save to PostgreSQL as well ---
        from backend import crud, schemas
        from backend.database import SessionLocal
        import datetime
        db = SessionLocal()
        try:
            output_payload = {
                "id": result.get("id"),
                "title": result.get("title"),
                "createdAt": result.get("createdAt"),
                "vendors": result.get("vendors"),
                "best": result.get("best"),
                "alternative": result.get("alternative"),
                "inconclusive": result.get("inconclusive"),
                "evaluation_summary": result.get("evaluation_summary"),
                "requirements": result.get("requirements"),
                "constraints": result.get("constraints"),
                "constraint_warnings": result.get("constraint_warnings"),
                "explanation": result.get("explanation"),
                "differences": result.get("differences"),
                "files": result.get("files"),
                "output_files": result.get("output_files"),
            }
            audit = result.get("audit") or {}
            input_payload = {
                "files": result.get("files"),
                "vendors_raw": audit.get("vendors_raw"),
                "comparison": audit.get("comparison"),
                "requirements": result.get("requirements"),
                "constraints": result.get("constraints"),
            }

            analysis_obj = schemas.AnalysisCreate(
                title=str(result.get("title") or ""),
                timestamp=str(datetime.datetime.utcnow().isoformat()),
                vendor_count=len(vendors),
                best_vendor=str(best_vendor),
                final_score=float(final_score),
                data_json=jsonable_encoder(result),
                input_json=jsonable_encoder(input_payload),
                output_json=jsonable_encoder(output_payload),
                files_json=jsonable_encoder(result.get("files") or []),
                output_files_json=jsonable_encoder(result.get("output_files") or []),
                uploaded_file_id=None
            )
            try:
                saved = crud.save_analysis(db, analysis_obj)

                # Also persist one row per uploaded file into `uploaded_files`.
                upload_time = str(datetime.datetime.utcnow().isoformat())
                for fm in (result.get("files") or []):
                    crud.save_uploaded_file(
                        db,
                        schemas.UploadedFileCreate(
                            filename=str(fm.get("name") or ""),
                            content_type=str(fm.get("type") or ""),
                            upload_time=upload_time,
                            output_json=jsonable_encoder(
                                {
                                    "size": fm.get("size"),
                                    "sha256": fm.get("sha256"),
                                    "analysis_id": getattr(saved, "id", None),
                                }
                            ),
                            analysis_id=getattr(saved, "id", None),
                        ),
                    )
            except Exception as e:
                # SQLite history is already saved; preserve the result if PostgreSQL persistence fails.
                db.rollback()
                logger.warning("PostgreSQL analysis persistence failed: %s", e)
        finally:
            db.close()

    # Keep response small(ish): UI uses main fields; audit is optional.
    return {
        "id": result["id"],
        "title": result["title"],
        "createdAt": result["createdAt"],
        "vendors": result["vendors"],
        "best": result["best"],
        "alternative": result["alternative"],
        "inconclusive": result["inconclusive"],
        "evaluation_summary": result["evaluation_summary"],
        "requirements": result["requirements"],
        "constraints": result["constraints"],
        "constraint_warnings": result["constraint_warnings"],
        "explanation": result["explanation"],
        "differences": result["differences"],
        "files": result["files"],
        "file_errors": result["file_errors"],
    }
