
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
from typing import Any, List, Optional
import datetime
import hashlib

from core.comparison import build_comparison
from core.cost_engine import CostConfig, compute_total_landed_cost
from core.extraction import extract_fields
from core.history import init_db, save_session
from core.ingestion import ingest_bytes
from core.normalization import normalize
from core.scoring import compute_scores
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


def _to_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _to_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def _build_explanation_points(best_vendor: dict[str, Any], all_vendors: list[dict[str, Any]]) -> list[str]:
    others = [v for v in all_vendors if v.get("id") != best_vendor.get("id")]
    avg_cost = sum(float(v.get("total_cost", 0.0) or 0.0) for v in others) / max(1, len(others))
    avg_delivery = sum(float(v.get("delivery_days", 0.0) or 0.0) for v in others) / max(1, len(others))

    cost_saving = avg_cost - float(best_vendor.get("total_cost", 0.0) or 0.0)
    delivery_gain = avg_delivery - float(best_vendor.get("delivery_days", 0.0) or 0.0)

    points: list[str] = []
    points.append(
        f"{best_vendor.get('vendor_name', 'Best vendor')} achieves the highest weighted score of "
        f"{(float(best_vendor.get('final_score', 0.0) or 0.0) * 100):.1f}%, driven by a strong cost-to-quality balance."
    )
    if cost_saving > 0:
        points.append(f"Total cost is ₹{int(round(cost_saving)):,} lower than the average competitor.")
    if delivery_gain > 0:
        points.append(f"Delivery is {delivery_gain:.1f} days faster than the field average.")
    payment_days = int(best_vendor.get("payment_days", 0) or 0)
    if payment_days > 0:
        points.append(f"Payment terms of Net {payment_days} provide healthy working-capital flexibility.")
    credit_cost = float(best_vendor.get("credit_cost", 0.0) or 0.0)
    points.append(
        f"GST and freight are normalized; the credit-cost adjustment of ₹{int(round(credit_cost)):,} is included in the total."
    )
    return points


def _analysis_from_uploads(
    files: list[UploadFile],
    cfg: CostConfig,
    usd_to_inr: float,
    compute_output_files_meta: bool = False,
) -> dict[str, Any]:
    extracted: list[dict[str, Any]] = []
    file_meta: list[dict[str, Any]] = []
    file_errors: list[dict[str, Any]] = []

    for idx, f in enumerate(files):
        filename = f.filename or f"file-{idx + 1}"
        try:
            b = f.file.read()
            if not b:
                raise ValueError("Empty file")

            raw_text = ingest_bytes(b, filename)
            fields = extract_fields(raw_text, filename=filename)
            norm = normalize(fields, usd_to_inr=float(usd_to_inr))

            costed, _breakdown = compute_total_landed_cost(norm, cfg=cfg)
            costed["source_file"] = filename
            extracted.append(costed)

            file_meta.append(
                {
                    "name": filename,
                    "size": len(b),
                    "type": f.content_type or "",
                    "sha256": hashlib.sha256(b).hexdigest(),
                }
            )
        except Exception as e:
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

    scored = compute_scores(extracted)

    # Sort + rank for UI
    scored_sorted = sorted(scored, key=lambda v: float(v.get("final_score", 0.0) or 0.0), reverse=True)
    for i, v in enumerate(scored_sorted, start=1):
        v["rank"] = i

    # Convert into the UI's expected shape
    ui_vendors: list[dict[str, Any]] = []
    for v in scored_sorted:
        vendor_name = str(v.get("vendor_name") or "Vendor").strip()
        source_file = str(v.get("source_file") or "")
        vid = f"{source_file or vendor_name}-{int(v.get('rank') or 0)}"

        ui_vendors.append(
            {
                "id": vid,
                "vendor_name": vendor_name,
                "item_name": str(v.get("item_name") or "Item"),
                "quantity": _to_int(v.get("quantity"), 1),
                "unit_price": _to_float(v.get("unit_price"), 0.0),
                "base_amount": _to_float(v.get("base_cost", v.get("total_price")), 0.0),
                "gst_pct": _to_float(v.get("gst_percent"), 18.0),
                "gst_amount": _to_float(v.get("gst_amount"), 0.0),
                "freight": _to_float(v.get("freight_cost"), 0.0),
                "delivery_days": _to_int(v.get("delivery_days"), 30),
                "payment_days": _to_int(v.get("payment_days", v.get("payment_terms_days")), 30),
                "credit_cost": _to_float(v.get("credit_cost"), 0.0),
                "delay_penalty_cost": _to_float(v.get("delay_penalty_cost"), 0.0),
                "missing_data_risk_cost": _to_float(v.get("missing_data_risk_cost"), 0.0),
                "total_cost": _to_float(v.get("total_cost"), 0.0),
                "currency": "INR",
                "source_file": source_file,
                "cost_score": _to_float(v.get("cost_score"), 0.0) / 100.0,
                "delivery_score": _to_float(v.get("delivery_score"), 0.0) / 100.0,
                "terms_score": _to_float(v.get("terms_score"), 0.0) / 100.0,
                "final_score": _to_float(v.get("final_score"), 0.0) / 100.0,
                "rank": _to_int(v.get("rank"), 0),
            }
        )

    # Differences vs best-in-class (UI expects)
    min_cost = min(float(v.get("total_cost") or 0.0) for v in ui_vendors)
    min_delivery = min(int(v.get("delivery_days") or 0) for v in ui_vendors)
    max_payment = max(int(v.get("payment_days") or 0) for v in ui_vendors)
    differences = [
        {
            "vendor_name": v["vendor_name"],
            "cost_diff": float(v["total_cost"]) - min_cost,
            "delivery_diff": int(v["delivery_days"]) - min_delivery,
            "terms_diff": max_payment - int(v["payment_days"]),
        }
        for v in ui_vendors
    ]

    best = ui_vendors[0]

    # Keep the original comparison DataFrame available for history/audit
    comparison_df, best_vendor_name = build_comparison(scored_sorted)

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
        "explanation": _build_explanation_points(best, ui_vendors),
        "differences": differences,
        "files": file_meta,
        "output_files": output_files_meta,
        "file_errors": file_errors,
        "audit": {
            "best_vendor": best_vendor_name,
            "comparison": comparison_df.to_dict(orient="records"),
            "vendors_raw": scored_sorted,
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

    cfg = CostConfig(
        usd_to_inr=float(usd_to_inr),
        interest_rate=float(interest_rate_pct) / 100.0,
        baseline_payment_days=int(baseline_payment_days),
        sla_delivery_days=int(sla_delivery_days),
        delay_penalty_rate_per_day=float(delay_penalty_rate_per_day_pct) / 100.0,
        delay_penalty_cap_pct=float(delay_penalty_cap_pct) / 100.0,
    )

    init_db(DB_PATH)
    result = _analysis_from_uploads(
        files=files,
        cfg=cfg,
        usd_to_inr=float(usd_to_inr),
        compute_output_files_meta=bool(save_history_flag),
    )


    if save_history_flag:
        vendors = result.get("vendors") or []
        best_vendor = (result.get("best") or {}).get("vendor_name") or "N/A"
        final_score = float((result.get("best") or {}).get("final_score") or 0.0) * 100.0
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
                # Do not fail the analysis response if Postgres persistence fails.
                # Frontend has a backend-fallback path; raising here would cause it to silently switch.
                db.rollback()
                print(f"[warn] Postgres save failed: {e}")
        finally:
            db.close()

    # Keep response small(ish): UI uses main fields; audit is optional.
    return {
        "id": result["id"],
        "title": result["title"],
        "createdAt": result["createdAt"],
        "vendors": result["vendors"],
        "best": result["best"],
        "explanation": result["explanation"],
        "differences": result["differences"],
        "files": result["files"],
    }

