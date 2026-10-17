import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class ResearchNoteCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(ResearchNoteCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super(ResearchNoteCanvas, self).showPage()
        super(ResearchNoteCanvas, self).save()

    def draw_decorations(self, page_count):
        self.saveState()
        w, h = A4
        margin = 28
        
        # Header accent bar
        self.setFillColor(colors.HexColor("#1E3A8A"))
        self.rect(margin, h - 16, w - (2 * margin), 3, fill=1, stroke=0)
        
        # Running Header
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#0F172A"))
        self.drawString(margin, h - 26, "ALPHA-DECAY | Forensic Financial Discovery Note")
        
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(w - margin, h - 26, "Track C: Consumer, FMCG & Retail (ATMOS 2026)")
        
        # Footer
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(margin, 26, w - margin, 26)
        
        self.setFont("Helvetica", 7.0)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(margin, 16, "CONFIDENTIAL & FORENSIC ONLY — Zero investment recommendations, price targets, or buy/sell calls.")
        
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.setFont("Helvetica-Bold", 7.2)
        self.setFillColor(colors.HexColor("#334155"))
        self.drawRightString(w - margin, 16, page_str)
        self.restoreState()

def find_value(data: Dict[str, Any], *patterns, default=None):
    """
    Case-insensitive, symbol-agnostic key lookup to match keys like
    '1_The_Discovery', 'The Discovery', 'Discovery', '1. The Discovery'.
    """
    for p in patterns:
        p_clean = re.sub(r"[^a-zA-Z]", "", p).lower()
        for k, v in data.items():
            k_clean = re.sub(r"[^a-zA-Z]", "", k).lower()
            if p_clean in k_clean or k_clean in p_clean:
                return v
    return default

def export_forensic_pdf(
    ticker: str,
    company_name: str,
    summary_data: Dict[str, Any],
    discovery: Dict[str, Any],
    output_path: str = "forensic_report.pdf"
) -> str:
    """
    Compiles the mandatory 8-point schema and quantitative metrics into a publication-grade PDF research note.
    """
    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=32,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    
    # Palette
    c_primary = colors.HexColor("#0F172A")
    c_blue = colors.HexColor("#1E40AF")
    c_accent = colors.HexColor("#2563EB")
    c_text = colors.HexColor("#1E293B")
    c_muted = colors.HexColor("#475569")
    c_border = colors.HexColor("#CBD5E1")
    c_bg_callout = colors.HexColor("#EFF6FF") # Blue 50
    c_bg_head = colors.HexColor("#F8FAFC")

    # Typography
    title_style = ParagraphStyle(
        'NoteTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=c_primary
    )

    sec_title_style = ParagraphStyle(
        'NoteSecTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=11.5,
        textColor=colors.white
    )

    body_style = ParagraphStyle(
        'NoteBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11.0,
        textColor=c_text
    )

    body_bold = ParagraphStyle(
        'NoteBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    meta_style = ParagraphStyle(
        'NoteMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.0,
        textColor=c_muted
    )

    discovery_text_style = ParagraphStyle(
        'DiscoveryText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.0,
        textColor=colors.HexColor("#1E3A8A")
    )

    table_text = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.2,
        textColor=c_text
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.2,
        textColor=c_primary
    )

    story = []

    def make_section(title, color=c_blue):
        t = Table([[Paragraph(f"<b>{title}</b>", sec_title_style)]], colWidths=[539])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), color),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t

    # Header Meta Banner
    curr_date = datetime.now().strftime("%d %B %Y")
    head_data = [
        [
            Paragraph(f"<b>FORENSIC DISCOVERY NOTE: {company_name.upper()}</b><br/>"
                      f"<font size=8.5 color='#1E40AF'><b>Ticker: {ticker} | Track C: FMCG & Retail</b></font>", title_style),
            Paragraph(f"<b>Generated:</b> {curr_date}<br/>"
                      f"<b>Engine:</b> AlphaDecay v1.0<br/>"
                      f"<b>Mandate:</b> Autonomous Financial Research", meta_style)
        ]
    ]
    t_head = Table(head_data, colWidths=[350, 189])
    t_head.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_head)
    story.append(Spacer(1, 4))

    # 1. THE DISCOVERY (Callout Box)
    discovery_sentence = find_value(discovery, "discovery", default="No discovery recorded.")
    disc_box = [
        [
            Paragraph("<font size=7.5 color='#1E3A8A'><b>1. THE DISCOVERY (NON-OBVIOUS REALITY)</b></font><br/>"
                      f"{discovery_sentence}", discovery_text_style)
        ]
    ]
    t_disc = Table(disc_box, colWidths=[539])
    t_disc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_callout),
        ('BOX', (0,0), (-1,-1), 1.2, c_accent),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_disc)
    story.append(Spacer(1, 6))

    # 2. WHY IT MATTERS
    story.append(make_section("2. Why It Matters (Business & Operational Implications)"))
    story.append(Spacer(1, 3))
    why_matters = find_value(discovery, "whymatters", "why_it_matters", default=[])
    if isinstance(why_matters, list):
        bullets = "".join([f"• <b>{item}</b><br/>" for item in why_matters])
    else:
        bullets = str(why_matters)
    story.append(Paragraph(bullets, body_style))
    story.append(Spacer(1, 5))

    # 5. NUMBERS & QUANTITATIVE BREAKDOWN (Deterministic Math Sandbox Table)
    story.append(make_section("3. Quantitative Calculations & Trailing 8-Quarter Metrics"))
    story.append(Spacer(1, 3))
    
    quarters = summary_data.get("quarters_analyzed", [])
    sales_growth = summary_data.get("sales_growth_yoy", {})
    debtor_days = summary_data.get("debtor_days", {})

    # Build Numbers Table
    if quarters:
        cols_count = min(6, len(quarters))
        display_q = quarters[-cols_count:]
        
        num_header = [Paragraph("<b>Metric / Quarter</b>", table_header)] + [
            Paragraph(f"<b>{q}</b>", table_header) for q in display_q
        ]
        
        row_growth = [Paragraph("<b>Net Sales YoY (%)</b>", table_text)] + [
            Paragraph(f"{sales_growth.get(q, 'N/A')}%", table_text) for q in display_q
        ]
        
        row_debtor = [Paragraph("<b>Debtor Days</b>", table_text)] + [
            Paragraph(f"{debtor_days.get(q, 'N/A')}d", table_text) for q in display_q
        ]

        col_w = [149] + [390 / cols_count] * cols_count
        t_numbers = Table([num_header, row_growth, row_debtor], colWidths=col_w)
        t_numbers.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), c_bg_head),
            ('GRID', (0,0), (-1,-1), 0.5, c_border),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_numbers)
        story.append(Spacer(1, 3))

    num_summary = find_value(discovery, "numbers", default="")
    if num_summary:
        story.append(Paragraph(f"<b>Forensic Calculation Summary:</b> {num_summary}", body_style))
        story.append(Spacer(1, 5))

    # 4. TIMELINE & EVIDENCE TRAIL
    story.append(make_section("4. Timeline & Traceable Evidence Trail"))
    story.append(Spacer(1, 3))
    timeline_desc = find_value(discovery, "timeline", default="Timeline not specified.")
    evidence_urls = find_value(discovery, "evidence", default=[])
    if isinstance(evidence_urls, list):
        ev_str = "<br/>".join([f"• <font color='#1E40AF'><u>{u}</u></font>" for u in evidence_urls])
    else:
        ev_str = str(evidence_urls)

    time_ev_table = [
        [
            Paragraph("<b>Divergence Timeline:</b>", table_header),
            Paragraph(timeline_desc, body_style)
        ],
        [
            Paragraph("<b>Auditable Evidence Links:</b>", table_header),
            Paragraph(ev_str, body_style)
        ]
    ]
    t_time_ev = Table(time_ev_table, colWidths=[120, 419])
    t_time_ev.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (0,-1), c_bg_head),
    ]))
    story.append(t_time_ev)
    story.append(Spacer(1, 5))

    # 6. COUNTERARGUMENT (Devil's Advocate)
    story.append(make_section("5. Adversarial Counterargument (The Defense / Devil's Advocate)"))
    story.append(Spacer(1, 3))
    counter = find_value(discovery, "counterargument", default="None recorded.")
    story.append(Paragraph(f"<b>Strongest Alternative Macro Explanation:</b> {counter}", body_style))
    story.append(Spacer(1, 5))

    # 7. FALSIFICATION CONDITION & EVIDENCE STRENGTH
    story.append(make_section("6. Objective Falsification Condition & Evidence Rating"))
    story.append(Spacer(1, 3))
    falsify_cond = find_value(discovery, "falsification", default="None recorded.")
    ev_strength = find_value(discovery, "strength", default="Moderate")

    falsify_table = [
        [
            Paragraph("<b>Falsification Criteria:</b>", table_header),
            Paragraph(f"<b>Disproven if:</b> {falsify_cond}", body_style)
        ],
        [
            Paragraph("<b>Evidence Strength:</b>", table_header),
            Paragraph(f"<b>{ev_strength}</b>", body_style)
        ]
    ]
    t_falsify = Table(falsify_table, colWidths=[120, 419])
    t_falsify.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (0,-1), c_bg_head),
    ]))
    story.append(t_falsify)

    doc.build(story, canvasmaker=ResearchNoteCanvas)
    print(f"Successfully generated PDF report: {output_file}")
    return str(output_file)

if __name__ == "__main__":
    test_disc = {
        "1_The_Discovery": "Britannia Industries Ltd's reported +8.18% YoY sales growth conceals a fundamental depletion of pricing power, masking underlying operational volume contraction behind temporary realization carry-over.",
        "2_Why_It_Matters": [
            "Obscures core volume stagnation and ongoing market share erosion to regional unorganized competitors.",
            "Exposes operating margins to a severe cliff once pricing actions fully lap without organic volume normalization.",
            "Indicates balance sheet degradation as channel filling and stretched working capital artificially sustain top-line metrics."
        ],
        "3_Evidence": [
            "https://britannia.co.in/investors/financial-results",
            "https://www.bseindia.com/corporates/ann.html"
        ],
        "4_Timeline": "Q1 FY25 through Q1 FY27 (Ended June 2026)",
        "5_Numbers": "Reported Net Sales Growth of +8.18% YoY against stagnant-to-negative estimated volume growth (-1.5% to 0.0%).",
        "6_Counterargument": "Agricultural raw material deflation forced price cuts across mass SKUs, depressing nominal realization.",
        "7_Falsification_Condition": "Hypothesis is disproven if Britannia delivers >=2 consecutive quarters of positive volume growth with debtor days < 28d.",
        "8_Evidence_Strength": "Strong: Confirmed by wide price-volume divergence and peer triangulation."
    }
    test_summary = {
        "quarters_analyzed": ["Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025", "Sep 2025", "Dec 2025"],
        "sales_growth_yoy": {"Sep 2024": 4.5, "Dec 2024": 5.1, "Mar 2025": 6.2, "Jun 2025": 8.18},
        "debtor_days": {"Sep 2024": 22.4, "Dec 2024": 24.1, "Mar 2025": 28.5, "Jun 2025": 30.6}
    }
    export_forensic_pdf("BRITANNIA", "Britannia Industries Ltd", test_summary, test_disc, "test_note.pdf")
