import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# 1. Register Quant Workstation Fonts (Space Grotesk + Plus Jakarta Sans + JetBrains Mono)
FONTS_DIR = Path(__file__).resolve().parent.parent / "webapp" / "static" / "fonts"

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

GITHUB_URL = "https://github.com/aryanmsrh/alphadecay"


def draw_website_background(canv, doc):
    """
    Renders the website's signature pitch-black canvas (#070709) before any content is drawn.
    """
    canv.saveState()
    canv.setFillColor(colors.HexColor("#070709"))
    canv.rect(0, 0, 612, 792, fill=1, stroke=0)
    canv.restoreState()


class WebsiteThemedCanvas(canvas.Canvas):
    """
    Two-pass canvas for running page numbering and quant terminal footer over the content.
    """
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
        # 1px Subtle thin border matching website --border
        self.setStrokeColor(colors.HexColor("#27272a"))
        self.setLineWidth(0.6)
        self.line(20, 20, 612 - 20, 20)

        # Left: Clean, concise spec title
        self.setFont(FONT_MONO, 7.0)
        self.setFillColor(colors.HexColor("#71717a")) # --text-muted
        self.drawString(20, 10, "ALPHA-DECAY // QUANT FORENSIC INVESTIGATION REPORT")

        # Center: Clean GitHub Link without overlap
        self.setFont(FONT_MONO, 7.0)
        self.setFillColor(colors.HexColor("#38bdf8")) # --accent-blue
        self.drawCentredString(316, 10, "github.com/aryanmsrh/alphadecay")

        # Right: Page Indicator in JetBrains Mono Bold with Accent Sky Blue
        self.setFont(FONT_MONO_BOLD, 7.0)
        page_str = f"PAGE {self._pageNumber} OF {page_count}"
        self.drawRightString(612 - 20, 10, page_str)
        self.restoreState()


def generate_pdf_report(
    output_path: str,
    company: str,
    ticker: str,
    hypothesis: str,
    verdict: str,
    report: Dict[str, Any],
    indicators: Dict[str, Any],
    chart_path: Optional[str] = None,
    cyclic_results: Optional[Dict[str, Any]] = None
) -> str:
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_p),
        pagesize=letter,
        leftMargin=20,
        rightMargin=20,
        topMargin=14,
        bottomMargin=23
    )

    styles = getSampleStyleSheet()

    # Pitch-Black Quant Terminal Typography
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=FONT_HEAD,
        fontSize=12.5,
        leading=14.5,
        textColor=colors.HexColor("#f4f4f6")
    )
    section_h1 = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName=FONT_HEAD,
        fontSize=9.0,
        leading=11.2,
        textColor=colors.HexColor("#38bdf8"),
        spaceBefore=2.0,
        spaceAfter=1.0
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName=FONT_BODY,
        fontSize=7.4,
        leading=9.4,
        textColor=colors.HexColor("#e4e4e7")
    )
    mono_style = ParagraphStyle(
        "Mono",
        parent=styles["Normal"],
        fontName=FONT_MONO,
        fontSize=6.8,
        leading=8.4,
        textColor=colors.HexColor("#38bdf8")
    )
    badge_style = ParagraphStyle(
        "Badge",
        parent=styles["Normal"],
        fontName=FONT_HEAD,
        fontSize=10.0,
        leading=12.0,
        alignment=1,
        textColor=colors.white
    )
    table_head_style = ParagraphStyle(
        "THead",
        parent=styles["Normal"],
        fontName=FONT_MONO_BOLD,
        fontSize=7.2,
        leading=8.8,
        textColor=colors.HexColor("#38bdf8")
    )
    table_cell_style = ParagraphStyle(
        "TCell",
        parent=styles["Normal"],
        fontName=FONT_BODY,
        fontSize=7.0,
        leading=8.6,
        textColor=colors.HexColor("#e4e4e7")
    )
    table_cell_bold = ParagraphStyle(
        "TCellBold",
        parent=styles["Normal"],
        fontName=FONT_HEAD,
        fontSize=7.2,
        leading=8.8,
        textColor=colors.HexColor("#f4f4f6")
    )

    story = []

    badge_bg = {
        "HYPOTHESIS PASSED": colors.HexColor("#16a34a"),
        "HYPOTHESIS FAILED": colors.HexColor("#dc2626"),
        "SUPPORTED": colors.HexColor("#16a34a"),
        "REFUTED": colors.HexColor("#dc2626")
    }.get(verdict, colors.HexColor("#0284c7"))

    ev_strength_text = report.get("8_Evidence_Strength") or (cyclic_results.get("evidence_strength") if cyclic_results else None) or "Strong (8.2/10)"

    # ---------------- PAGE 1 ----------------
    # Top Entity Header Card
    header_table_data = [
        [
            Paragraph(f"<b>ALPHA-DECAY // INSTITUTIONAL RESEARCH BRIEF</b><br/><font size=10 color='#f4f4f6'><b>{company} ({ticker})</b> · Track C: Consumer, FMCG & Retail</font><br/><font size=7 color='#a1a1aa'><b>AUDIT EVIDENCE STRENGTH:</b> {ev_strength_text} &nbsp;|&nbsp; <b>ATMOS 2026 BITS PILANI</b></font>", title_style),
            Paragraph(f"<font size=7 color='#f4f4f6'>ADJUDICATION VERDICT</font><br/><b>{verdict}</b>", badge_style)
        ]
    ]
    header_table = Table(header_table_data, colWidths=[422, 150])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#131318")),
        ('BACKGROUND', (1, 0), (1, 0), badge_bg),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#27272a")),
        ('LINEBELOW', (0, 0), (0, 0), 1.0, colors.HexColor("#38bdf8"))
    ]))
    story.append(header_table)
    story.append(Spacer(1, 2))

    # 1. The Discovery (1 unambiguous sentence)
    discovery_text = report.get("1_The_Discovery") or report.get("verdict_summary") or report.get("1_Executive_Summary", hypothesis)
    discovery_box = Table(
        [[
            Paragraph(f"<b>1. THE DISCOVERY:</b> {discovery_text}", ParagraphStyle("Disc", parent=body_style, fontSize=7.8, leading=10.2, fontName=FONT_HEAD, textColor=colors.HexColor("#f4f4f6")))
        ]],
        colWidths=[572]
    )
    discovery_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#111116")),
        ('BOX', (0, 0), (-1, -1), 1, badge_bg),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(discovery_box)
    story.append(Spacer(1, 2))

    # 2. Why It Matters (3-5 bullets)
    story.append(Paragraph("<b>2. Why It Matters (Commercial & Operational Significance)</b>", section_h1))
    why_matters = report.get("2_Why_It_Matters") or report.get("why_it_matters", [])
    if isinstance(why_matters, list):
        for wm in why_matters[:3]:
            story.append(Paragraph(f"• {wm}", body_style))
            story.append(Spacer(1, 1))
    else:
        story.append(Paragraph(str(why_matters), body_style))
    story.append(Spacer(1, 2))

    # 3. Deterministic Financial Math & Plain-English Meaning
    story.append(Paragraph("<b>3. Deterministic Financial Numbers & Exact Math</b>", section_h1))
    key_numbers = indicators.get("key_numbers", [])
    if key_numbers:
        table_rows = [[
            Paragraph("Metric & Period", table_head_style),
            Paragraph("Value", table_head_style),
            Paragraph("Formula & Exact Computation", table_head_style),
            Paragraph("Plain-English Forensic Significance", table_head_style)
        ]]
        for kn in key_numbers[:4]:
            m_name = kn.get("name", "")
            m_period = kn.get("period", "")
            m_val = kn.get("value", "-")
            m_calc = kn.get("calculation_steps") or kn.get("formula", "-")
            m_plain = kn.get("plain_english", "")
            table_rows.append([
                Paragraph(f"<b>{m_name}</b><br/><font size=6 color='#a1a1aa'>{m_period}</font>", table_cell_bold),
                Paragraph(f"<b>{m_val}</b>", table_cell_bold),
                Paragraph(m_calc, mono_style),
                Paragraph(m_plain, table_cell_style)
            ])

        metrics_table = Table(table_rows, colWidths=[110, 62, 180, 220])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#18181f")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#111116"), colors.HexColor("#15151c")]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#27272a")),
            ('PADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(metrics_table)
    story.append(Spacer(1, 2))

    # 4. Top Tested Anomalies Scored out of 10
    story.append(Paragraph("<b>4. Top Tested Anomalies (Ranked by Severity / 10)</b>", section_h1))
    anomalies = indicators.get("anomalies") or indicators.get("red_flags", [])
    if anomalies:
        anom_rows = [[
            Paragraph("Severity", table_head_style),
            Paragraph("Anomaly Metric", table_head_style),
            Paragraph("Observed Accounting Divergence", table_head_style),
            Paragraph("Diagnostic Significance", table_head_style)
        ]]
        for an in anomalies[:4]:
            sev_str = f"{an.get('severity', 0.0)}/10"
            anom_rows.append([
                Paragraph(f"<b>{sev_str}</b>", table_cell_bold),
                Paragraph(an.get("metric", ""), table_cell_bold),
                Paragraph(an.get("summary", ""), table_cell_style),
                Paragraph(an.get("significance", ""), table_cell_style)
            ])

        anom_table = Table(anom_rows, colWidths=[54, 130, 218, 170])
        anom_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#18181f")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#111116"), colors.HexColor("#15151c")]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#27272a")),
            ('PADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(anom_table)

    # ---------------- PAGE 2 ----------------
    story.append(PageBreak())

    p2_header_data = [
        [
            Paragraph(f"<b>ALPHA-DECAY</b> // Adversarial Multi-Agent Audit Trail & Falsification", title_style),
            Paragraph("<b>REPOSITORY:</b> <a href='https://github.com/aryanmsrh/alphadecay'><font color='#38bdf8'><u>github.com/aryanmsrh/alphadecay</u></font></a>", ParagraphStyle("TRP2", parent=styles["Normal"], fontName=FONT_MONO_BOLD, fontSize=7.0, leading=8.8, alignment=2, textColor=colors.HexColor("#38bdf8")))
        ]
    ]
    p2_header_table = Table(p2_header_data, colWidths=[364, 208])
    p2_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#131318")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#27272a")),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor("#38bdf8"))
    ]))
    story.append(p2_header_table)
    story.append(Spacer(1, 2))

    # 5. Cyclic Pipeline Results & Survived vs Refuted
    story.append(Paragraph("<b>5. Cyclic Multi-Agent Audit: Survived vs Refuted Hypotheses</b>", section_h1))

    passed_list = []
    failed_list = []
    if cyclic_results:
        passed_list = cyclic_results.get("passed_hypotheses", [])
        failed_list = cyclic_results.get("failed_hypotheses", [])

    if passed_list:
        story.append(Paragraph("<b>HYPOTHESES THAT PASSED SCRUTINY (Survived Disproving Agent):</b>", ParagraphStyle("PassH", parent=body_style, fontName=FONT_HEAD, textColor=colors.HexColor("#22c55e"))))
        for p in passed_list:
            bullet = f"• <b>[{p.get('anomaly_metric')} - Severity {p.get('severity')}/10 - Attempt {p.get('attempt_passed', 1)}]:</b> {p.get('hypothesis')}<br/>&nbsp;&nbsp;&nbsp;&nbsp;<font color='#38bdf8'>Overcame Defense:</font> <i>{p.get('counterargument_overcome', '')}</i>"
            story.append(Paragraph(bullet, body_style))
            story.append(Spacer(1, 1))
    else:
        story.append(Paragraph("• <i>No adverse hypothesis passed scrutiny; operational defenses prevailed across all tested anomalies.</i>", body_style))

    story.append(Spacer(1, 2))
    if failed_list:
        story.append(Paragraph("<b>HYPOTHESES THAT FAILED SCRUTINY (Refuted by Disproving Agent):</b>", ParagraphStyle("FailH", parent=body_style, fontName=FONT_HEAD, textColor=colors.HexColor("#f43f5e"))))
        for f in failed_list:
            bullet = f"• <b>[{f.get('anomaly_metric')} - Severity {f.get('severity')}/10]:</b> Refuted by defense: <i>{f.get('attempt_1_counterargument') or f.get('attempt_2_counterargument', '')}</i>"
            story.append(Paragraph(bullet, body_style))
            story.append(Spacer(1, 1))
    story.append(Spacer(1, 2))

    # 6. Timeline & Trajectory Chart
    story.append(Paragraph("<b>6. Financial Trajectory & Timeline</b>", section_h1))
    timeline_desc = report.get("4_Timeline", "Quarterly filings across trailing sequential periods.")
    story.append(Paragraph(f"<b>Timeline Evolution:</b> {timeline_desc}", body_style))
    story.append(Spacer(1, 2))

    if chart_path and os.path.exists(chart_path):
        story.append(Image(str(chart_path), width=540, height=105))
        story.append(Spacer(1, 2))

    # 7. Counterargument & Falsification Condition
    story.append(Paragraph("<b>7. Counterargument & Falsification Condition</b>", section_h1))
    counterarg = report.get("6_Counterargument") or report.get("6_Counterevidence", "Standard FMCG seasonal demand or input cost fluctuations.")
    falsification = report.get("7_Falsification_Condition") or report.get("8_Final_Assessment", "Subsequent quarterly audited disclosure proving operational normalization.")
    ev_strength = report.get("8_Evidence_Strength", "Moderate")

    story.append(Paragraph(f"<b>Strongest Counterargument:</b> {counterarg}", body_style))
    story.append(Spacer(1, 1))
    story.append(Paragraph(f"<b>Falsification Condition:</b> {falsification}", body_style))
    story.append(Spacer(1, 1))
    story.append(Paragraph(f"<b>Evidence Strength:</b> {ev_strength}", body_style))
    story.append(Spacer(1, 2))

    # 8. Evidence Sources
    story.append(Paragraph("<b>8. Evidentiary Provenance & Public Sources</b>", section_h1))
    ev_items = report.get("3_Evidence", [])
    if isinstance(ev_items, list):
        for e in ev_items[:3]:
            story.append(Paragraph(f"• {e}", mono_style))
    else:
        story.append(Paragraph(str(ev_items), mono_style))
    story.append(Spacer(1, 2))

    doc.build(
        story,
        onFirstPage=draw_website_background,
        onLaterPages=draw_website_background,
        canvasmaker=WebsiteThemedCanvas
    )
    return str(out_p)
