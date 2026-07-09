# AI-Powered Vendor Quotation Comparison System (Rule-Based, CPU-Only)

A clean, modular Streamlit prototype to compare multiple vendor quotations (PDF, images, CSV, XLSX) using **regex + heuristics** (no LLMs, no external APIs).

## Quick Start (Streamlit)

```bash
python -m pip install -r requirements.txt
python -m streamlit run app/streamlit_app.py
```

## Quick Start (React UI + API backend)

Backend (FastAPI):

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Frontend (Vite/React):

```bash
cd "ui/ai-outreach-hub-main (2)/ai-outreach-hub-main"
npm install
npm run dev
```

On Windows, activate the virtual environment first, then use `python -m ...` commands. This avoids broken launcher paths if the project folder was moved.

The UI calls the backend at `http://localhost:8000` by default. To change it, set `VITE_API_BASE_URL` in the frontend.

### Sample files

This repo includes sample quotations in `data/sample_quotes/` (CSV + PDF + PNG).

Optional: regenerate them anytime:

```bash
python data/sample_quotes/generate_sample_quotes.py
```

## History (SQLite)

Every analysis run is saved as a session to SQLite at `data/outputs/history.db`.
Use the left sidebar (**📜 History**) to open past sessions or clear history.

## Export

- CSV export: built-in
- Excel export: generated as `.xlsx` without extra dependencies (see `utils/xlsx_writer.py`)

## Supported Inputs

- PDF: text extraction via PyMuPDF (`fitz`), with OCR fallback for scanned PDFs (first page)
- Images (`.png/.jpg`): OCR via `pytesseract` with OpenCV preprocessing
- CSV: `pandas.read_csv`
- XLSX: lightweight stdlib-based parser (no `openpyxl` required)

## Extracted Fields (Rule-Based)

- `vendor_name`
- `item_name`
- `quantity`
- `unit_price`
- `total_price`
- `gst_percent`
- `delivery_days`
- `payment_terms_days`
- `delivery_text`
- `payment_terms_text`
- `penalty_clause`
- `freight_cost`

Missing values are filled with defaults and tracked in `missing_fields` for scoring penalties.

## Normalization

- Currency normalized to INR
- Assumption: `1 USD = 83 INR`
- Delivery/payment text normalized to numeric days (e.g. `Net 30`, `2 weeks`, `Immediate`)
- Produces `base_cost` for the cost engine

## Scoring

Final score (0-100):

```
(0.60 * Cost Score) + (0.25 * Delivery Score) + (0.15 * Terms Score)
```

- Lower `total_cost` -> higher cost score
- Faster delivery -> higher delivery score
- Longer payment terms -> higher terms score
- Missing fields reduce the relevant sub-score

## Cost Engine (Total Landed Cost)

The system computes a transparent landed-cost breakdown in `core/cost_engine.py`:

```
total_cost =
    base_cost
  + gst_amount
  + freight_cost
  + credit_cost            (penalizes payment terms shorter than baseline)
  + delay_penalty_cost     (risk cost when delivery > SLA)
  + missing_data_risk_cost
```

- Assumptions: interest rate = 12% p.a., baseline payment terms = 30 days, SLA delivery = 14 days

## Project Structure

```
vendor-selection/
  app/
    streamlit_app.py
  core/
    ingestion.py
    ocr.py
    extraction.py
    normalization.py
    cost_engine.py
    scoring.py
    comparison.py
    explanation.py
    history.py
  utils/
    currency.py
    date_parser.py
    xlsx_writer.py
  data/
    sample_quotes/
    outputs/
  requirements.txt
  README.md
```

## Notes (OCR)

`pytesseract` requires the Tesseract binary installed on your machine.

- Windows: install Tesseract and ensure `tesseract.exe` is in PATH.
- If OCR is not available, image-based quotes will show an OCR-unavailable message.

### Windows OCR setup (recommended)

- Install Tesseract OCR (Windows):
  - Option A (winget): `winget install --id UB-Mannheim.TesseractOCR -e`
  - Option B: install from the UB Mannheim build and note the install path.
- If it is not on PATH, set an environment variable:
  - `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

The app will auto-detect common install locations, but setting `TESSERACT_CMD` is the most reliable.
