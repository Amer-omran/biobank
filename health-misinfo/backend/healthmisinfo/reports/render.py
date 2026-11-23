"""CSV and PDF rendering. CSV cells are protected against spreadsheet formula injection; PDF text
is shaped for Arabic (reshaping + bidi) using a font with Arabic glyphs."""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import UTC, datetime

from healthmisinfo.config import get_settings

_AR = re.compile("[؀-ۿ]")
_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(v):
    if v is None:
        return ""
    s = str(v)
    return "'" + s if s.startswith(_FORMULA_PREFIX) else s


def to_csv(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([safe_cell(c) for c in r])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens Arabic correctly


def shape(text: str) -> str:
    if not text or not _AR.search(text):
        return text or ""
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(text))


class PdfReport:
    """Small helper around reportlab platypus."""

    def __init__(self, title: str):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font = "Helvetica"
        fp = get_settings().pdf_font_path
        if fp.exists():
            try:
                pdfmetrics.registerFont(TTFont("ReportFont", str(fp)))
                font = "ReportFont"
            except Exception as e:  # fall back to Helvetica (no Arabic glyphs) but say so
                logging.getLogger("healthmisinfo").warning("Could not load PDF font %s: %s", fp, e)
        self.font = font
        self.colors = colors
        base = getSampleStyleSheet()
        self.h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName=font, textColor=colors.HexColor("#0b2545"))
        self.h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName=font, textColor=colors.HexColor("#0b2545"))
        self.body = ParagraphStyle("b", parent=base["BodyText"], fontName=font, fontSize=9, leading=12)
        self.note = ParagraphStyle("n", parent=self.body, textColor=colors.HexColor("#4b5563"), fontSize=8)
        self.banner = ParagraphStyle(
            "w",
            parent=self.body,
            backColor=colors.HexColor("#fff7ed"),
            borderColor=colors.HexColor("#c2410c"),
            borderWidth=1,
            borderPadding=6,
            textColor=colors.HexColor("#7c2d12"),
        )
        self.measured = ParagraphStyle(
            "m", parent=self.banner, backColor=colors.HexColor("#ecfeff"), borderColor=colors.HexColor("#0f766e"), textColor=colors.HexColor("#134e4a")
        )
        self.pagesize = A4
        self.story: list = []
        self.title = title
        self.p(title, self.h1)
        self.p(
            f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} — research platform output. Not medical advice; not a definitive fact-check.",
            self.note,
        )

    def p(self, text: str, style=None):
        from xml.sax.saxutils import escape

        from reportlab.platypus import Paragraph

        self.story.append(Paragraph(escape(shape(str(text))), style or self.body))

    def space(self, h: float = 6):
        from reportlab.platypus import Spacer

        self.story.append(Spacer(1, h))

    def table(self, header: list[str], rows: list[list], col_widths=None):
        from xml.sax.saxutils import escape

        from reportlab.platypus import Paragraph, Table, TableStyle

        data = [[Paragraph(escape(shape(str(h))), self.body) for h in header]]
        for r in rows:
            data.append([Paragraph(escape(shape("" if c is None else str(c))), self.body) for c in r])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors.HexColor("#e0f2f1")),
                    ("GRID", (0, 0), (-1, -1), 0.25, self.colors.HexColor("#9ca3af")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        self.story.append(t)

    def render(self) -> bytes:
        from reportlab.platypus import SimpleDocTemplate

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=self.pagesize, title=self.title, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        doc.build(self.story)
        return buf.getvalue()
