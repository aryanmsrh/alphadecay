from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONTS_DIR = Path(__file__).resolve().parent.parent / "web" / "static" / "fonts"

try:
    pdfmetrics.registerFont(TTFont("SpaceGrotesk-Bold", str(FONTS_DIR / "SpaceGrotesk-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("SpaceGrotesk", str(FONTS_DIR / "SpaceGrotesk-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("PlusJakartaSans", str(FONTS_DIR / "PlusJakartaSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("JetBrainsMono", str(FONTS_DIR / "JetBrainsMono-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("JetBrainsMono-Bold", str(FONTS_DIR / "JetBrainsMono-Bold.ttf")))
    registerFontFamily("JetBrainsMono", normal="JetBrainsMono", bold="JetBrainsMono-Bold")
    FONT_HEAD = "SpaceGrotesk-Bold"
    FONT_BODY = "PlusJakartaSans"
    FONT_MONO = "JetBrainsMono"
    FONT_MONO_BOLD = "JetBrainsMono-Bold"
except Exception:
    FONT_HEAD = "Helvetica-Bold"
    FONT_BODY = "Helvetica"
    FONT_MONO = "Courier"
    FONT_MONO_BOLD = "Helvetica-Bold"


def _esc(val: Any) -> str:
    if val is None:
        return ""
    return escape(str(val))


def draw_background(canv, doc):
    canv.saveState()
    canv.setFillColor(colors.HexColor("#070709"))
    canv.rect(0, 0, 612, 792, fill=1, stroke=0)
    canv.restoreState()


class ReportCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setStrokeColor(colors.HexColor("#27272a"))
        self.setLineWidth(0.6)
        self.line(20, 20, 612 - 20, 20)

        self.setFont(FONT_MONO, 7.0)
        self.setFillColor(colors.HexColor("#71717a"))
        self.drawString(20, 10, "AlphaDecay")

        self.setFont(FONT_MONO_BOLD, 7.0)
        page_str = f"PAGE {self._pageNumber} OF {page_count}"
        self.drawRightString(612 - 20, 10, page_str)
        self.restoreState()


def generate_pdf_report(
    output_path: str,
    company: str,
    ticker: str,
    investigated_anomalies: List[Dict[str, Any]],
    indicators: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> str:
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_p),
        pagesize=letter,
        leftMargin=24,
        rightMargin=24,
        topMargin=20,
        bottomMargin=26,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=FONT_HEAD,
        fontSize=13.0,
        leading=16.0,
        textColor=colors.HexColor("#f4f4f6"),
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName=FONT_MONO,
        fontSize=7.5,
        leading=10.0,
        textColor=colors.HexColor("#a1a1aa"),
    )
    section_h = ParagraphStyle(
        "SectionH",
        parent=styles["Normal"],
        fontName=FONT_HEAD,
        fontSize=8.5,
        leading=11.0,
        textColor=colors.HexColor("#38bdf8"),
        spaceBefore=4.0,
        spaceAfter=2.0,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName=FONT_BODY,
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#e4e4e7"),
    )
    mono_style = ParagraphStyle(
        "Mono",
        parent=styles["Normal"],
        fontName=FONT_MONO,
        fontSize=7.0,
        leading=9.5,
        textColor=colors.HexColor("#38bdf8"),
    )
    attacker_box_style = ParagraphStyle(
        "AtkBox",
        parent=styles["Normal"],
        fontName=FONT_BODY,
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#fca5a5"),
    )
    defender_box_style = ParagraphStyle(
        "DefBox",
        parent=styles["Normal"],
        fontName=FONT_BODY,
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#86efac"),
    )

    story = []

    header_table = Table(
        [[
            Paragraph(
                f"<b>{_esc(company)} ({_esc(ticker)})</b><br/>"
                f"<font size=8 color='#a1a1aa'>Anomalies Analyzed: {len(investigated_anomalies)}</font>",
                title_style,
            ),
            Paragraph("AlphaDecay Report", meta_style),
        ]],
        colWidths=[430, 134],
    )
    header_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111116")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#27272a")),
            ("LINEBELOW", (0, 0), (-1, -1), 1.0, colors.HexColor("#38bdf8")),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 6))

    for idx, item in enumerate(investigated_anomalies, start=1):
        rpt = item.get("report", {})
        metric_title = item.get("metric", f"Anomaly #{idx}")

        if idx > 1:
            story.append(PageBreak())

        story.append(Paragraph(f"<b>Anomaly {idx}: {_esc(metric_title)}</b>", title_style))
        story.append(Spacer(1, 4))

        disc = _esc(rpt.get("discovery") or rpt.get("the_discovery", ""))
        disc_table = Table(
            [[
                Paragraph(f"<b>1. The Discovery:</b> {disc}", body_style)
            ]],
            colWidths=[564],
        )
        disc_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#131318")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#38bdf8")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(disc_table)
        story.append(Spacer(1, 4))

        story.append(Paragraph("<b>2. Why It Matters:</b>", section_h))
        why_bullets = rpt.get("why_it_matters", [])
        if isinstance(why_bullets, list):
            for b in why_bullets:
                story.append(Paragraph(f"• {_esc(b)}", body_style))
                story.append(Spacer(1, 1.5))
        else:
            story.append(Paragraph(f"• {_esc(why_bullets)}", body_style))
        story.append(Spacer(1, 3))

        story.append(Paragraph("<b>3. Evidence:</b>", section_h))
        ev_items = rpt.get("evidence", [])
        if isinstance(ev_items, list):
            for e in ev_items:
                if isinstance(e, dict):
                    src = _esc(e.get("source", ""))
                    url = _esc(e.get("url", ""))
                    link_txt = f"<a href='{url}'><font color='#38bdf8'><u>[{src}]</u></font></a> — {url}" if url else f"[{src}]"
                    story.append(Paragraph(f"• {link_txt}", body_style))
                else:
                    story.append(Paragraph(f"• {_esc(e)}", body_style))
                story.append(Spacer(1, 1.5))
        else:
            story.append(Paragraph(f"• {_esc(ev_items)}", body_style))
        story.append(Spacer(1, 3))

        story.append(Paragraph("<b>4. Timeline:</b>", section_h))
        story.append(Paragraph(_esc(rpt.get("timeline", "")), body_style))
        story.append(Spacer(1, 4))

        story.append(Paragraph("<b>5. Numbers:</b>", section_h))
        num_items = rpt.get("numbers", [])
        num_rows = []
        if isinstance(num_items, list):
            for n in num_items:
                num_rows.append([Paragraph(f"• {_esc(n)}", mono_style)])
        else:
            num_rows.append([Paragraph(_esc(num_items), mono_style)])

        num_table = Table(num_rows, colWidths=[564])
        num_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#000000")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#27272a")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ])
        )
        story.append(num_table)
        story.append(Spacer(1, 4))

        atk = rpt.get("attacker", {})
        atk_verdict = _esc(atk.get("verdict", "")) if isinstance(atk, dict) else _esc(atk)
        atk_strength = _esc(atk.get("evidence_strength", "")) if isinstance(atk, dict) else ""
        atk_conf = _esc(atk.get("confidence", "") or atk.get("confidence_rating", "")) if isinstance(atk, dict) else ""
        atk_table = Table(
            [[
                Paragraph(
                    f"<b>6. Attacker</b> ({atk_conf})<br/>"
                    f"<b>Verdict:</b> {atk_verdict}<br/>"
                    f"<b>Evidence Strength:</b> {atk_strength}",
                    attacker_box_style,
                )
            ]],
            colWidths=[564],
        )
        atk_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1c0303")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dc2626")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(atk_table)
        story.append(Spacer(1, 4))

        dfn = rpt.get("defender", {})
        dfn_counter = _esc(dfn.get("counterargument", "") or dfn.get("alternative_explanation", "")) if isinstance(dfn, dict) else _esc(dfn)
        dfn_fals = _esc(dfn.get("falsification_condition", "")) if isinstance(dfn, dict) else ""
        dfn_strength = _esc(dfn.get("evidence_strength", "")) if isinstance(dfn, dict) else ""
        dfn_conf = _esc(dfn.get("confidence", "") or dfn.get("confidence_rating", "")) if isinstance(dfn, dict) else ""
        dfn_table = Table(
            [[
                Paragraph(
                    f"<b>7. Defender</b> ({dfn_conf})<br/>"
                    f"<b>Counterargument:</b> {dfn_counter}<br/>"
                    f"<b>Falsification Condition:</b> {dfn_fals}<br/>"
                    f"<b>Evidence Strength:</b> {dfn_strength}",
                    defender_box_style,
                )
            ]],
            colWidths=[564],
        )
        dfn_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#021a0c")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#16a34a")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(dfn_table)
        story.append(Spacer(1, 4))

        strength_str = _esc(rpt.get("strength", f"Attacker: {atk_conf} | Defender: {dfn_conf}"))
        strength_table = Table(
            [[Paragraph(f"<b>8. Strength:</b> {strength_str}", body_style)]],
            colWidths=[564],
        )
        strength_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111116")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#27272a")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(strength_table)

    doc.build(
        story,
        onFirstPage=draw_background,
        onLaterPages=draw_background,
        canvasmaker=ReportCanvas,
    )
    return str(out_p)
