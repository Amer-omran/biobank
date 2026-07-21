"""Fill the lab's Word storage-request form from a sample record.

Dependency-free (standard library zipfile + xml.etree). The .docx template is
NOT bundled with the code; its path is provided at runtime via the
BIOBANK_FORM_TEMPLATE environment variable so the (potentially internal) form
never has to live in the repository.

Only the fields the application actually captures are filled in; the workflow
sections (approvals, adequacy, preparation …) are left blank for manual
completion.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Any, Optional
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _cell_text(tc: ET.Element) -> str:
    return "".join(t.text or "" for t in tc.iter(W + "t"))


def _set_cell_text(tc: ET.Element, text: str) -> None:
    """Write `text` into a table cell, reusing existing run formatting."""
    texts = list(tc.iter(W + "t"))
    if texts:
        texts[0].text = text
        texts[0].set(XML_SPACE, "preserve")
        for extra in texts[1:]:
            extra.text = ""
        return
    para = next(iter(tc.iter(W + "p")), None)
    if para is None:
        para = ET.SubElement(tc, W + "p")
    run = ET.SubElement(para, W + "r")
    t = ET.SubElement(run, W + "t")
    t.set(XML_SPACE, "preserve")
    t.text = text


def _value_map(sample: dict[str, Any]) -> dict[str, str]:
    """Map the lab form's field labels to values from a sample record."""
    q = sample.get("quantity_ml")
    try:
        qty = f"{float(q):g} ml" if q not in (None, "") else ""
    except (TypeError, ValueError):
        qty = f"{q} ml"
    sid = sample.get("id", "")
    return {
        "request id": str(sid),
        "request date": (sample.get("created_at") or "")[:10],
        "primary sample id": sample.get("sample_number") or (f"#{sid}" if sid != "" else ""),
        "sample type": sample.get("sample_type") or "",
        "disease / organism name": sample.get("disease") or "",
        "collection location": sample.get("area") or "",
        "sample volume / quantity": qty,
        "required storage temperature": sample.get("storage_method") or "",
        "biobank accession number": f"BB-{sid}" if sid != "" else "",
        "storage barcode": sample.get("barcode") or "",
        "freezer number": sample.get("freezer_no") or "",
        "rack number": sample.get("shelf_no") or "",
        "box number": sample.get("plate_no") or "",
        "storage date": sample.get("storage_date") or "",
        "biobank officer": sample.get("created_by") or "",
    }


def _register_namespaces(raw: bytes) -> None:
    head = raw[:2000].decode("utf-8", "ignore")
    for prefix, uri in re.findall(r'xmlns:(\w+)="([^"]+)"', head):
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass


def fill_docx(template_bytes: bytes, sample: dict[str, Any]) -> bytes:
    """Return a copy of the .docx template with the sample's values filled in."""
    values = {_norm(k): v for k, v in _value_map(sample).items()}
    with zipfile.ZipFile(io.BytesIO(template_bytes)) as zin:
        infos = zin.infolist()
        doc_xml = zin.read("word/document.xml")
        _register_namespaces(doc_xml)
        root = ET.fromstring(doc_xml)
        for tbl in root.iter(W + "tbl"):
            for tr in tbl.findall(W + "tr"):
                cells = tr.findall(W + "tc")
                if len(cells) < 2:
                    continue
                key = _norm(_cell_text(cells[0]))
                val = values.get(key)
                if val and str(val).strip():
                    _set_cell_text(cells[1], str(val))
        body = ET.tostring(root, encoding="unicode")
        new_doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n' + body).encode("utf-8")

        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in infos:
                data = new_doc if info.filename == "word/document.xml" else zin.read(info.filename)
                zout.writestr(info, data)
    return out.getvalue()


def template_path() -> Optional[str]:
    p = os.environ.get("BIOBANK_FORM_TEMPLATE")
    return p if p and os.path.exists(p) else None


def build_form_docx(sample: dict[str, Any]) -> bytes:
    path = template_path()
    if not path:
        raise FileNotFoundError("form template not configured")
    with open(path, "rb") as fh:
        return fill_docx(fh.read(), sample)
