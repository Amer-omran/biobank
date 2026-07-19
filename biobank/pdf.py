"""Minimal PDF writer for sample reception forms (standard library only).

Generates a one-page A4 "Sample Reception Form" auto-filled from a sample
record, using the built-in Helvetica fonts (no embedding, no dependencies).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .options import FIELD_LABELS, SAMPLE_FIELDS

WIDTH, HEIGHT = 595, 842  # A4 in points
_TEAL = (0.031, 0.569, 0.698)
_DARK = (0.07, 0.10, 0.14)
_GRAY = (0.45, 0.50, 0.56)
_LITE = (0.85, 0.87, 0.90)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text(x: float, y: float, size: float, font: str, s: str) -> str:
    return f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({_esc(s)}) Tj ET\n"


def _line(x1: float, y1: float, x2: float, y2: float, w: float = 1) -> str:
    return f"{w} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S\n"


def _fill(rgb: tuple[float, float, float]) -> str:
    return f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg\n"


def _stroke(rgb: tuple[float, float, float]) -> str:
    return f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} RG\n"


def _compose(sample: dict[str, Any]) -> str:
    M = 50
    c: list[str] = []
    # header
    c.append(_fill(_TEAL)); c.append(_text(M, 795, 22, "F2", "Biobank"))
    c.append(_fill(_GRAY)); c.append(_text(M, 779, 10, "F1", "Animal Sample Registry"))
    c.append(_stroke(_TEAL)); c.append(_line(M, 769, WIDTH - M, 769, 1.5))

    c.append(_fill(_DARK)); c.append(_text(M, 745, 15, "F2", "SAMPLE RECEPTION FORM"))
    c.append(_fill(_GRAY)); c.append(_text(430, 745, 12, "F2", f"Receipt #{sample.get('id', '')}"))
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    c.append(_text(M, 729, 9, "F1", f"Generated: {gen}     Recorded by: {sample.get('created_by') or '-'}"))

    # field rows
    y = 702
    for field in SAMPLE_FIELDS:
        label = FIELD_LABELS.get(field, field)
        val = sample.get(field)
        val = "-" if val in (None, "") else str(val)
        c.append(_fill(_GRAY)); c.append(_text(M, y, 9, "F2", label.upper()))
        c.append(_fill(_DARK)); c.append(_text(M + 155, y, 11, "F1", val))
        c.append(_stroke(_LITE)); c.append(_line(M, y - 7, WIDTH - M, y - 7, 0.6))
        y -= 24

    # signature block
    sy = y - 22
    c.append(_fill(_DARK))
    c.append(_text(M, sy, 10, "F1", "Received by:"))
    c.append(_stroke(_GRAY)); c.append(_line(M + 72, sy - 2, M + 240, sy - 2, 0.8))
    c.append(_text(330, sy, 10, "F1", "Signature:"))
    c.append(_line(392, sy - 2, WIDTH - M, sy - 2, 0.8))
    c.append(_text(M, sy - 32, 10, "F1", "Date:"))
    c.append(_line(M + 42, sy - 34, M + 210, sy - 34, 0.8))

    # footer
    c.append(_fill(_GRAY))
    c.append(_text(M, 42, 8, "F1", "Generated automatically by the Biobank sample registry."))
    return "".join(c)


def build_receipt_pdf(sample: dict[str, Any]) -> bytes:
    content = _compose(sample).encode("latin-1", "replace")
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[tuple[int, int]] = []

    def add_obj(num: int, body: bytes) -> None:
        offsets.append((num, len(out)))
        out.extend(f"{num} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    add_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add_obj(3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
               b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>")
    add_obj(4, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    add_obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    add_obj(6, b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")

    xref_pos = len(out)
    count = len(offsets) + 1
    out.extend(f"xref\n0 {count}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for _num, off in sorted(offsets):
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode())
    return bytes(out)
