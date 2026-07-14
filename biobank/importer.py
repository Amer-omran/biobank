"""Spreadsheet import for the biobank system (standard library only).

Parses CSV and native .xlsx files into sample records. Handles:

* real lab forms where the column header sits below title rows,
* Excel date serial numbers (converted to YYYY-MM-DD),
* a range of column-header spellings via options.IMPORT_ALIASES.

.xlsx is read directly with zipfile + xml.etree — no third-party libraries.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from .options import IMPORT_ALIASES, SAMPLE_FIELDS

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_EXCEL_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)


def _col_index(ref: str) -> int:
    letters = "".join(c for c in ref if c.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def normalize_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return value
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    try:
        serial = float(value)
    except ValueError:
        return value
    return (_EXCEL_EPOCH + timedelta(days=round(serial))).strftime("%Y-%m-%d")


def parse_csv(text: str) -> list[list[str]]:
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader if any(cell.strip() for cell in row)]


def parse_xlsx(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss.iter(_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_NS + "t")))
        sheet_name = next(
            (n for n in z.namelist() if n == "xl/worksheets/sheet1.xml"),
            next((n for n in z.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")), None),
        )
        if sheet_name is None:
            raise ValueError("no worksheet found in .xlsx")
        sheet = ET.fromstring(z.read(sheet_name))

    rows: list[list[str]] = []
    for row in sheet.iter(_NS + "row"):
        cells: list[str] = []
        for c in row.findall(_NS + "c"):
            idx = _col_index(c.get("r", "A1"))
            while len(cells) <= idx:
                cells.append("")
            t = c.get("t")
            v = c.find(_NS + "v")
            if t == "s" and v is not None:
                cells[idx] = shared[int(v.text)] if v.text is not None else ""
            elif t == "inlineStr":
                is_el = c.find(_NS + "is")
                cells[idx] = "".join(x.text or "" for x in is_el.iter(_NS + "t")) if is_el is not None else ""
            elif v is not None:
                cells[idx] = v.text or ""
        rows.append(cells)
    return [r for r in rows if any(str(x).strip() for x in r)]


def rows_to_records(rows: list[list[str]]) -> tuple[list[dict[str, str]], int]:
    """Map a table of cells to sample records.

    Returns (records, header_row_index). The header row is auto-detected as
    the row (within the first 30) matching the most known column names.
    """
    if not rows:
        raise ValueError("the file is empty")

    header_idx, best, idx_map = -1, 0, {}
    for i, row in enumerate(rows[:30]):
        mapping: dict[str, int] = {}
        for j, cell in enumerate(row):
            key = IMPORT_ALIASES.get(str(cell).strip().lower())
            if key and key != "_no" and key not in mapping:
                mapping[key] = j
        if len(mapping) > best:
            best, header_idx, idx_map = len(mapping), i, mapping
    if best < 2:
        raise ValueError("no recognizable columns — use the template")

    records: list[dict[str, str]] = []
    for row in rows[header_idx + 1:]:
        if not any(str(x).strip() for x in row):
            continue
        rec: dict[str, str] = {}
        for field in SAMPLE_FIELDS:
            if field in idx_map and idx_map[field] < len(row):
                rec[field] = str(row[idx_map[field]]).strip()
        if rec.get("storage_date"):
            rec["storage_date"] = normalize_date(rec["storage_date"])
        records.append(rec)
    return records, header_idx


def parse_file(data: bytes, filename: str) -> list[dict[str, str]]:
    """Parse raw file bytes (csv or xlsx) into a list of record dicts."""
    if filename.lower().endswith(".csv"):
        rows = parse_csv(data.decode("utf-8-sig", errors="replace"))
    else:
        rows = parse_xlsx(data)
    records, _ = rows_to_records(rows)
    return records
