"""
xlsx_writer.py
--------------
Minimal XLSX writer (stdlib only) to export a single-sheet report without
extra dependencies like openpyxl/xlsxwriter.
"""

from __future__ import annotations

import html
import io
import zipfile
from typing import Dict, List, Tuple

import pandas as pd


def df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Report") -> bytes:
    sheet_name = (sheet_name or "Report")[:31]

    strings, sst_xml = _build_shared_strings(df)
    sheet_xml = _build_sheet_xml(df, strings)

    content_types = _content_types_xml()
    rels = _rels_xml()
    workbook = _workbook_xml(sheet_name)
    wb_rels = _workbook_rels_xml()
    styles = _styles_xml()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", sst_xml)
        zf.writestr("xl/styles.xml", styles)

    return buf.getvalue()


def _build_shared_strings(df: pd.DataFrame) -> Tuple[Dict[str, int], str]:
    # Include headers + cell string values
    seen: Dict[str, int] = {}
    items: List[str] = []

    def add(s: str) -> int:
        s = "" if s is None else str(s)
        if s in seen:
            return seen[s]
        idx = len(items)
        seen[s] = idx
        items.append(s)
        return idx

    for col in df.columns:
        add(str(col))

    for _, row in df.iterrows():
        for v in row.values:
            if _is_number(v):
                continue
            add("" if v is None else str(v))

    # Build SST XML
    si_parts = []
    for s in items:
        si_parts.append(f"<si><t xml:space=\"preserve\">{html.escape(s)}</t></si>")

    sst = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        f"count=\"{len(items)}\" uniqueCount=\"{len(items)}\">"
        + "".join(si_parts)
        + "</sst>"
    )
    return seen, sst


def _build_sheet_xml(df: pd.DataFrame, strings: Dict[str, int]) -> str:
    rows_xml: List[str] = []

    def cell_ref(col_idx: int, row_idx: int) -> str:
        return f"{_col_letters(col_idx)}{row_idx}"

    # Header row (row 1)
    header_cells = []
    for c, name in enumerate(df.columns, start=1):
        s_idx = strings.get(str(name), 0)
        header_cells.append(f"<c r=\"{cell_ref(c,1)}\" t=\"s\"><v>{s_idx}</v></c>")
    rows_xml.append(f"<row r=\"1\">{''.join(header_cells)}</row>")

    # Data rows
    for r, (_, row) in enumerate(df.iterrows(), start=2):
        cells = []
        for c, v in enumerate(row.values, start=1):
            if _is_number(v):
                num = _to_number(v)
                cells.append(f"<c r=\"{cell_ref(c,r)}\"><v>{num}</v></c>")
            else:
                s_idx = strings.get("" if v is None else str(v), 0)
                cells.append(f"<c r=\"{cell_ref(c,r)}\" t=\"s\"><v>{s_idx}</v></c>")
        rows_xml.append(f"<row r=\"{r}\">{''.join(cells)}</row>")

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<sheetData>"
        + "".join(rows_xml)
        + "</sheetData></worksheet>"
    )


def _content_types_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "<Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/>"
        "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>"
        "</Types>"
    )


def _rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    )


def _workbook_xml(sheet_name: str) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<sheets>"
        f"<sheet name=\"{html.escape(sheet_name)}\" sheetId=\"1\" r:id=\"rId1\"/>"
        "</sheets></workbook>"
    )


def _workbook_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings\" Target=\"sharedStrings.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>"
        "</Relationships>"
    )


def _styles_xml() -> str:
    # Minimal styles so Excel opens the file cleanly.
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts>"
        "<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
        "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
        "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
        "<cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/></cellXfs>"
        "</styleSheet>"
    )


def _col_letters(idx: int) -> str:
    # 1 -> A, 26 -> Z, 27 -> AA
    letters = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _is_number(v) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)) and v == v:
        return True
    # try parse numeric strings
    try:
        s = str(v).strip().replace(",", "")
        if not s:
            return False
        float(s)
        return True
    except Exception:
        return False


def _to_number(v) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    try:
        s = str(v).strip().replace(",", "")
        return str(float(s))
    except Exception:
        return "0"

