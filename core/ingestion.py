"""
ingestion.py
------------
Detects file type and routes to appropriate extractor.
Supports PDF (PyMuPDF), Images (OCR), and CSV/XLSX (lightweight parsing).
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
import logging
import pandas as pd
import fitz  # PyMuPDF

from core.ocr import extract_text_from_image

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".csv",
    ".xlsx",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".tif",
)


def ingest_file(uploaded_file) -> str:
    """
    Accept a Streamlit UploadedFile object, detect its type,
    and return raw extracted text (or a stringified DataFrame for Excel).

    Args:
        uploaded_file: Streamlit UploadedFile object

    Returns:
        str: Raw text extracted from the file
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    return ingest_bytes(file_bytes, filename)


def ingest_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Ingest by raw bytes + filename.
    Streamlit preview/UI can safely call this without consuming file handles.
    """
    filename_l = (filename or "").lower()

    if filename_l.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if filename_l.endswith((".xlsx", ".csv")):
        return _extract_table(file_bytes, filename_l)
    if filename_l.endswith(".xls"):
        raise ValueError("'.xls' is not supported. Please export as .xlsx or .csv.")
    if filename_l.endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif")):
        return extract_text_from_image(file_bytes)
    raise ValueError(
        f"Unsupported file format: '{filename}'. Please upload PDF, CSV/XLSX, or image files."
    )


def preview_file(file_bytes: bytes, filename: str) -> dict:
    """
    Lightweight preview helper for the UI.
    Returns a dict describing what to render.
    """
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return {"type": "pdf"}
    if name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif")):
        return {"type": "image"}
    if name.endswith(".csv"):
        return {"type": "table", "df": _preview_csv(file_bytes)}
    if name.endswith(".xlsx"):
        return {"type": "table", "df": _preview_xlsx(file_bytes)}
    return {"type": "unknown"}


def _extract_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF using PyMuPDF (fitz).
    Falls back to OCR on the first page if no text is found (scanned PDF).

    Args:
        file_bytes: Raw bytes of the PDF file

    Returns:
        str: Full extracted text
    """
    text_parts = []
    try:
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in pdf_doc:
            page_text = page.get_text("text")
            text_parts.append(page_text)
        pdf_doc.close()
    except Exception as e:
        logger.exception("Failed to parse PDF")
        raise RuntimeError(f"Failed to parse PDF: {e}")

    full_text = "\n".join(text_parts).strip()

    # If no text extracted, document might be a scanned image-based PDF
    if not full_text:
        full_text = _ocr_fallback_pdf(file_bytes)

    return full_text


def _ocr_fallback_pdf(file_bytes: bytes) -> str:
    """
    Render the first page of a scanned PDF to an image and run OCR.

    Args:
        file_bytes: Raw bytes of the PDF

    Returns:
        str: OCR-extracted text
    """
    try:
        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            # OCR the first few pages; many quotes put totals on page 1.
            max_pages = min(len(pdf_doc), 3)
            parts: list[str] = []
            for i in range(max_pages):
                page = pdf_doc[i]
                # Render page to a PNG image at 2× zoom for better OCR accuracy
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                parts.append(extract_text_from_image(img_bytes))
            return "\n".join([p for p in parts if p]).strip()
        finally:
            pdf_doc.close()
    except Exception as e:
        logger.exception("OCR fallback failed for PDF")
        raise RuntimeError(f"OCR fallback failed for PDF: {e}")


def _extract_table(file_bytes: bytes, filename: str) -> str:
    """
    Read a CSV or XLSX file and convert it to a plain-text representation
    for downstream regex extraction.

    Args:
        file_bytes: Raw bytes of the spreadsheet
        filename:   Original filename (used to detect CSV vs XLSX)

    Returns:
        str: String representation of the DataFrame
    """
    try:
        if filename.endswith(".csv"):
            # Keep CSV structured so extraction can parse it reliably.
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    return file_bytes.decode(enc)
                except UnicodeDecodeError:
                    continue
            return file_bytes.decode("utf-8", errors="replace")
        else:
            # Try pandas first (enterprise expectation), then fall back.
            try:
                df = pd.read_excel(io.BytesIO(file_bytes))
            except Exception:
                df = _read_xlsx_minimal(file_bytes)

            # Emit as CSV text for downstream parsing/extraction
            return df.to_csv(index=False)
    except Exception as e:
        raise RuntimeError(f"Failed to read spreadsheet: {e}")


def _preview_csv(file_bytes: bytes, max_rows: int = 30) -> pd.DataFrame:
    # best-effort decode and preview
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            text = ""
    if not text:
        text = file_bytes.decode("utf-8", errors="replace")

    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        # fallback: show raw lines
        lines = text.splitlines()[: max_rows + 1]
        return pd.DataFrame({"preview": lines})
    return df.head(max_rows)


def _preview_xlsx(file_bytes: bytes, max_rows: int = 30) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception:
        df = _read_xlsx_minimal(file_bytes)
    return df.head(max_rows)


def _read_xlsx_minimal(file_bytes: bytes) -> pd.DataFrame:
    """
    Minimal XLSX reader implemented with the Python stdlib (zip + xml).
    This keeps setup simple and avoids optional Excel engines.

    Limitations:
        - Reads only the first worksheet (sheet1 or first sheet*.xml)
        - Basic cell types: shared strings and numbers
        - Ignores formulas/styles/merged cells
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        sheet_name = _pick_first_sheet_xml(zf.namelist())
        if not sheet_name:
            raise ValueError("Could not find worksheet XML inside XLSX.")

        shared_strings = _read_shared_strings(zf)
        sheet_xml = zf.read(sheet_name)

    root = ET.fromstring(sheet_xml)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    cells: dict[tuple[int, int], str] = {}
    max_row = 0
    max_col = 0

    for row in root.findall(".//m:sheetData/m:row", ns):
        row_r = row.get("r")
        row_idx = int(row_r) if row_r and row_r.isdigit() else None

        for c in row.findall("m:c", ns):
            r = c.get("r")  # e.g. "B3"
            if not r:
                continue
            col_letters, row_digits = _split_cell_ref(r)
            if not row_digits:
                continue
            r_idx = int(row_digits)
            c_idx = _col_letters_to_index(col_letters)
            row_idx = row_idx or r_idx

            value = ""
            cell_type = c.get("t", "")
            v = c.find("m:v", ns)
            if cell_type == "s" and v is not None and v.text is not None:
                si = int(v.text)
                value = shared_strings.get(si, "")
            elif cell_type == "inlineStr":
                t = c.find(".//m:t", ns)
                value = (t.text or "") if t is not None else ""
            else:
                value = (v.text or "") if v is not None else ""

            value = str(value).strip()
            cells[(row_idx, c_idx)] = value
            max_row = max(max_row, row_idx)
            max_col = max(max_col, c_idx)

    if max_row == 0 or max_col == 0:
        return pd.DataFrame()

    rows: list[list[str]] = []
    for r in range(1, max_row + 1):
        row_vals = [cells.get((r, c), "") for c in range(1, max_col + 1)]
        rows.append(row_vals)

    # Heuristic: treat first non-empty row as header if it looks like labels
    header_row_idx = None
    for idx, row_vals in enumerate(rows):
        non_empty = [v for v in row_vals if v.strip()]
        if not non_empty:
            continue
        looks_like_header = all(not _looks_like_number(v) for v in non_empty)
        if looks_like_header:
            header_row_idx = idx
        break

    if header_row_idx is not None:
        headers = [h.strip() or f"col_{i+1}" for i, h in enumerate(rows[header_row_idx])]
        data_rows = rows[header_row_idx + 1 :]
        return pd.DataFrame(data_rows, columns=headers)

    return pd.DataFrame(rows)


def _pick_first_sheet_xml(names: list[str]) -> str | None:
    if "xl/worksheets/sheet1.xml" in names:
        return "xl/worksheets/sheet1.xml"
    sheet_candidates = sorted([n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)])
    return sheet_candidates[0] if sheet_candidates else None


def _read_shared_strings(zf: zipfile.ZipFile) -> dict[int, str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return {}
    xml = zf.read("xl/sharedStrings.xml")
    root = ET.fromstring(xml)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: dict[int, str] = {}
    for idx, si in enumerate(root.findall("m:si", ns)):
        # shared string can be split across multiple <t> nodes
        parts = [t.text or "" for t in si.findall(".//m:t", ns)]
        strings[idx] = "".join(parts).strip()
    return strings


def _split_cell_ref(ref: str) -> tuple[str, str]:
    m = re.match(r"^([A-Z]+)(\d+)$", ref.upper())
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def _col_letters_to_index(letters: str) -> int:
    # A -> 1, B -> 2, Z -> 26, AA -> 27
    idx = 0
    for ch in letters.upper():
        if "A" <= ch <= "Z":
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def _looks_like_number(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    return bool(re.match(r"^[+-]?(\d+(\.\d+)?|\.\d+)$", value.replace(",", "")))
