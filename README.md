# AI Vendor Selection and Quotation Analysis

Compare supplier quotations using existing PDF, image/OCR, CSV, and Excel extraction, then ask a local Ollama model to rank the extracted evidence according to your purchasing priorities. The backend validates the response and enforces explicit budget and delivery limits; it does not use a weighted score to select a winner.

## What the application does

1. Accepts quotations in PDF, DOCX, PNG/JPG, CSV, or XLSX format.
2. Extracts fields using the existing text, table, and OCR pipeline.
3. Normalizes known monetary values to INR. The default conversion assumption is `1 USD = 83 INR`.
4. Keeps an explicitly quoted payable total separate from a calculated total. Calculations use extracted amounts only; missing charges remain unknown and are reported rather than silently treated as zero.
5. Sends only structured quotation evidence and the user's requirements to Ollama.
6. Validates the JSON response, vendor IDs, and ranks. Invalid responses receive one repair attempt.
7. Applies explicitly stated maximum budget and delivery constraints as hard eligibility checks. If no vendor can be verified against the constraints, the result is inconclusive.

The model explains each vendor's advantages, disadvantages, costs, delivery, payment terms, risks, missing information, and confidence. It must not infer vendor reliability without evidence. Content from quotations is treated as untrusted data, not as instructions to the model.

## Requirements

- Python 3.11 or later
- Node.js and npm (for the React frontend)
- Ollama installed and running locally
- Tesseract OCR installed and on `PATH` for scanned PDFs and image quotations
- Python dependencies from `requirements.txt`, including `python-docx` for DOCX

## Ollama setup

1. Install Ollama from [ollama.com/download](https://ollama.com/download).
2. Start the Ollama application/service.
3. Pull the default model:

   ```powershell
   ollama pull llama3.2
   ```

4. Confirm the local API is responding:

   ```powershell
   ollama list
   ```

The default local API URL is `http://localhost:11434`. The model is configurable with `OLLAMA_MODEL`; a different locally pulled Ollama chat model may be used if it supports JSON output. Model speed and quality depend on available system resources.

## Environment variables

Copy `.env.example` to `.env` in the repository root and edit it as needed. The backend loads this file at startup; process environment variables override its values. Ollama configuration is not exposed to the browser.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama API base URL |
| `OLLAMA_MODEL` | `llama3.2` | Model name available to Ollama |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Request timeout |

Alternatively, set values directly in PowerShell:

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
$env:OLLAMA_TIMEOUT_SECONDS = "120"
```

## Run the application

Install Python dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

### React UI with FastAPI

Start the backend from the repository root:

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

In another terminal, start the React frontend:

```powershell
cd "ui\ai-outreach-hub-main (2)\ai-outreach-hub-main"
npm install
npm run dev
```

The frontend calls `http://localhost:8000` by default. Set `VITE_API_BASE_URL` in the frontend `.env` to change the API address. Ollama URL/model settings belong only in the backend environment.

### Streamlit UI

From the repository root:

```powershell
python -m streamlit run app\streamlit_app.py
```

Both interfaces require the backend runtime dependencies and an available Ollama model. Streamlit calls the same local evaluation service directly.

## Evaluation behavior and limitations

- The LLM ranks quotations qualitatively against the user's stated priorities. No fixed cost/delivery/payment weights or score are used.
- Values marked missing by extraction stay `null`/missing evidence; quantity, GST, delivery, payment, currency, and charges are not assigned fabricated defaults.
- Field status distinguishes a source-backed value, a calculated value, an explicit not-applicable charge, a value that was not provided, and a value that is present but could not be parsed.
- A quoted payable total, when clearly labeled, is kept separately from the deterministic breakdown total. The breakdown applies explicit discount, GST, freight, other taxes, and additional charges only when the inputs are available. Unmentioned charges remain unknown instead of being treated as zero.
- Tax-inclusive quotations are identified when the document states this and GST is not added a second time. Totals that conflict with the known breakdown are flagged for review.
- Extracted fields include source text/evidence and a confidence label (`source-backed`, `calculated`, or `unavailable`). These labels describe provenance, not statistical OCR confidence.
- INR and USD quotations (using the configured USD conversion rate) can be compared. Other or unidentified currencies remain unknown rather than being silently treated as INR.
- `delivery_reliability` is not currently extracted from vendor history. The application does not claim reliability unless the evidence actually contains it.
- Explicit limits phrased as a maximum/under/within budget or delivery period are enforced deterministically. Review the extracted data because OCR and heuristic extraction can still be wrong.
- The model's explanation is advisory, not a substitute for procurement review. Check the uploaded quotation and audit details before placing an order.
- Ollama does not need external paid APIs. The frontend does not call the model directly.

## Troubleshooting

- **Ollama unavailable:** start the Ollama service and confirm `OLLAMA_BASE_URL` is reachable.
- **Model not found:** run `ollama pull <model>` and ensure `OLLAMA_MODEL` matches `ollama list`.
- **Timeout:** increase `OLLAMA_TIMEOUT_SECONDS` or use a smaller model that fits available memory.
- **Invalid AI response:** the service retries once with a schema repair prompt; persistent invalid output returns an explicit API error rather than a fabricated ranking.
- **OCR unavailable:** install Tesseract OCR and ensure `tesseract.exe` is on `PATH`. PDF text extraction does not require OCR when text is embedded.
- **Incorrect values:** check the file preview and audit trail. Correct the source quotation or extraction result before relying on an evaluation.
- **DOCX table extraction:** tables with a header row are mapped by their column labels. Review extracted source evidence for unusual multi-line or merged-cell layouts.

## Manual quotation checks

The repository includes example quotations under `data/sample_quotes/`. To verify a PDF-only run, upload `sample_alpha.pdf`, `sample_beta.pdf`, and `sample_gamma.pdf` together in the React dashboard and enter priorities/limits that reflect your purchase. For a mixed-format run, upload `sample_alpha.pdf`, `vendor_beta_traders.csv`, and `sample_gamma.png` together. Check the displayed source evidence and missing-field warnings against each original document before relying on the recommendation.

The separate Apex/BrightTech/Nova values in the feature request are not present in the repository's sample documents. The automated constraint test uses those values only as test inputs; no vendor names or expected ranks are hardcoded in production code.

## History and exports

Analysis history is stored in SQLite at `data/outputs/history.db`. Results can be exported to CSV or Excel. The older database `final_score` field is retained for schema compatibility and is stored as `0`; it is not an AI score or used for ranking.

## Project layout

```text
app/                 Streamlit UI
backend/             FastAPI endpoints, persistence models, database
core/                Extraction, OCR, normalization, Ollama evaluation, history
data/sample_quotes/  Example quotations
ui/                  React + TypeScript frontend
utils/               Currency/date helpers and Excel export
```

## Tests

Run the mocked Ollama service tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Run frontend checks from `ui\ai-outreach-hub-main (2)\ai-outreach-hub-main`:

```powershell
npm test
npm run build
```
