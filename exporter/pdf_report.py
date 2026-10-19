import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from xml.sax.saxutils import escape
from exporter.forensic_chart import generate_forensic_chart
from engine.models import ForensicSummary
from exporter.theme import (
    HEX_BG_PRIMARY, HEX_BG_SECONDARY, HEX_BG_CARD, HEX_BG_CARD_ALT,
    HEX_TEXT_PRIMARY, HEX_TEXT_SECONDARY, HEX_TEXT_MUTED,
    HEX_ACCENT_GREEN, HEX_ACCENT_RED, HEX_ACCENT_BLUE, HEX_ACCENT_YELLOW,
    HEX_BORDER, HEX_BORDER_LIGHT, HEX_BORDER_ACCENT,
    COLOR_BG_PRIMARY, COLOR_BG_SECONDARY, COLOR_BG_CARD, COLOR_BG_CARD_ALT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT_GREEN, COLOR_ACCENT_RED, COLOR_ACCENT_BLUE, COLOR_ACCENT_YELLOW,
    COLOR_BORDER, COLOR_BORDER_LIGHT, COLOR_BORDER_ACCENT,
    VERDICT_THEME, DATA_SUFFICIENCY_THEME,
    get_semantic_color, format_signed_metric_html
)


def safe_text(val: Any) -> str:
    """Sanitizes dynamic text for ReportLab Paragraphs."""
    if val is None:
        return ""
    s = re.sub(r"\*+", "", str(val)).strip()
    return escape(s)


class DarkTerminalCanvas(canvas.Canvas):
    """
    Custom two-pass canvas that paints a deep terminal black background on every page,
    renders technical running headers, footers with page counts, and prevents white flashes.
    """
    default_track = "Consumer, FMCG & Retail"

    def __init__(self, *args, **kwargs):
        super(DarkTerminalCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super(DarkTerminalCanvas, self).showPage()
        super(DarkTerminalCanvas, self).save()

    def draw_decorations(self, page_count):
        self.saveState()
        w, h = A4
        margin = 28

        # Running Top Accent Rule (Electric Blue)
        self.setFillColor(COLOR_BORDER_ACCENT)
        self.rect(margin, h - 16, w - (2 * margin), 1.8, fill=1, stroke=0)

        # Running Header
        self.setFont("Helvetica-Bold", 7.2)
        self.setFillColor(COLOR_TEXT_PRIMARY)
        self.drawString(margin, h - 25, "ALPHA-DECAY // FINANCIAL FORENSIC INTELLIGENCE NOTE")

        self.setFont("Helvetica", 7.2)
        self.setFillColor(COLOR_TEXT_SECONDARY)
        track_str = getattr(self, "track_name", self.default_track)
        self.drawRightString(w - margin, h - 25, f"TRACK: {track_str.upper()}")

        # Running Footer Divider
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.6)
        self.line(margin, 24, w - margin, 24)

        # Footer Notes
        self.setFont("Helvetica", 6.8)
        self.setFillColor(COLOR_TEXT_MUTED)
        self.drawString(margin, 14, "CONFIDENTIAL & FORENSIC ONLY — Zero investment recommendations, price targets, or buy/sell calls.")

        page_str = f"PAGE {self._pageNumber} OF {page_count}"
        self.setFont("Helvetica-Bold", 7.0)
        self.setFillColor(COLOR_TEXT_SECONDARY)
        self.drawRightString(w - margin, 14, page_str)
        self.restoreState()


def draw_dark_background(canvas_obj, doc_obj):
    """Callback passed to SimpleDocTemplate to ensure background is painted before flowables."""
    canvas_obj.saveState()
    w, h = A4
    canvas_obj.setFillColor(COLOR_BG_PRIMARY)
    canvas_obj.rect(0, 0, w, h, fill=1, stroke=0)
    canvas_obj.restoreState()


def get_canvas_maker(track_name: str):
    class ConfiguredCanvas(DarkTerminalCanvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.track_name = track_name
    return ConfiguredCanvas


def find_value(data: Dict[str, Any], *patterns, default=None):
    """Case-insensitive, symbol-agnostic key lookup."""
    for p in patterns:
        norm_p = re.sub(r"[^a-zA-Z0-9]", "", p).lower()
        for k, v in data.items():
            norm_k = re.sub(r"[^a-zA-Z0-9]", "", k).lower()
            if norm_p in norm_k or norm_k in norm_p:
                return v
    return default


def export_forensic_pdf(
    ticker: str,
    company_name: str,
    summary_data: Any,
    discovery: Dict[str, Any],
    output_path: str
) -> str:
    """
    Renders an institutional 2-page dark financial terminal PDF research note.
    """
    ticker = ticker.upper()
    track_name = getattr(summary_data, "sector", "Consumer, FMCG & Retail") or "Consumer, FMCG & Retail"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=32,
        bottomMargin=32
    )

    styles = getSampleStyleSheet()

    # Base Dark Styles
    style_entity = ParagraphStyle(
        'DarkEntityHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=COLOR_TEXT_PRIMARY
    )
    style_meta = ParagraphStyle(
        'DarkMetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=COLOR_TEXT_SECONDARY
    )
    style_sec_title = ParagraphStyle(
        'DarkSectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=COLOR_ACCENT_BLUE
    )
    style_body = ParagraphStyle(
        'DarkBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=COLOR_TEXT_PRIMARY
    )
    style_body_secondary = ParagraphStyle(
        'DarkBodySecondary',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=COLOR_TEXT_SECONDARY
    )
    style_bullet = ParagraphStyle(
        'DarkBulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.0,
        textColor=COLOR_TEXT_PRIMARY,
        leftIndent=10
    )
    style_table_head = ParagraphStyle(
        'DarkTableHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=8.5,
        textColor=COLOR_ACCENT_BLUE
    )
    style_table_cell = ParagraphStyle(
        'DarkTableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=8.5,
        textColor=COLOR_TEXT_PRIMARY
    )
    style_card_title = ParagraphStyle(
        'DarkCardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.0,
        textColor=COLOR_TEXT_SECONDARY
    )

    story = []

    # --------------------------------------------------------------------------
    # 1. HEADER STRIP (Terminal Metadata)
    # --------------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc).strftime("%B %d, %Y (UTC)")
    model_name = getattr(summary_data, "model_used", None) or config.GEMINI_MODEL
    provider_used = getattr(summary_data, "provider_used", None) or ("Ollama" if config.USE_OFFLINE_MODE else "Gemini Cloud")
    as_of_date = getattr(summary_data, "as_of_date", None)
    thinking_level = getattr(summary_data, "thinking_level", None) or config.GEMINI_THINKING_LEVEL

    cutoff_str = f" // As-Of Cutoff: <font color='{HEX_ACCENT_YELLOW}'><b>{as_of_date}</b></font>" if as_of_date else ""

    header_data = [
        [
            Paragraph(f"<b>{safe_text(company_name.upper())}</b>", style_entity),
            Paragraph(f"<b>ENGINE:</b> AlphaDecay v2.0 // Execution: {safe_text(provider_used.upper())}<br/>"
                      f"<b>MODEL:</b> {safe_text(model_name)} ({safe_text(thinking_level).capitalize()} Thinking){cutoff_str}",
                      style_meta)
        ],
        [
            Paragraph(f"<font color='{HEX_ACCENT_BLUE}'><b>TICKER: {ticker}</b></font> | SECTOR: {track_name} | GENERATED: {now_utc}", style_meta),
            ""
        ]
    ]
    t_header = Table(header_data, colWidths=[310, 229])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('SPAN', (0,1), (1,1))
    ]))
    story.append(t_header)
    story.append(Spacer(1, 4))

    # --------------------------------------------------------------------------
    # 2. HERO FINDING PANEL
    # --------------------------------------------------------------------------
    finding_heading = find_value(discovery, "finding_heading", default="Verified Finding")
    disc_text = find_value(discovery, "discovery", "1_The_Discovery", default="Quantitative analysis complete.")
    timeline = find_value(discovery, "timeline", "4_Timeline", default="Trailing Reporting Cycle")

    # Extract primary anomaly metrics for hero badge
    selected_anom = None
    if getattr(summary_data, "anomalies", None):
        selected_anom = summary_data.anomalies[0]

    delta_val = selected_anom.delta if selected_anom else None
    delta_unit = selected_anom.unit if selected_anom else ""
    delta_basis = selected_anom.comparison_basis if selected_anom else "YoY"
    delta_dir = selected_anom.direction if selected_anom else "adverse"
    anom_metric = selected_anom.metric_name if selected_anom else "Financial Velocity"

    hero_delta_html = format_signed_metric_html(delta_val, delta_unit, anom_metric, delta_dir)

    hero_content = [
        [
            Paragraph(f"<font color='{HEX_ACCENT_BLUE}'><b>// {safe_text(finding_heading).upper()}</b></font> "
                      f"<font color='{HEX_TEXT_SECONDARY}'>({safe_text(timeline)})</font>", style_sec_title),
            Paragraph(f"DELTA: {hero_delta_html} <font color='{HEX_TEXT_SECONDARY}'>({delta_basis})</font>", ParagraphStyle('R_Align', parent=style_body, alignment=2))
        ],
        [
            Paragraph(f"<b>{safe_text(disc_text)}</b>", style_body),
            ""
        ]
    ]
    t_hero = Table(hero_content, colWidths=[380, 149])
    t_hero.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_CARD),
        ('BOX', (0,0), (-1,-1), 0.8, COLOR_BORDER_LIGHT),
        ('LINEBEFORE', (0,0), (0,-1), 2.5, COLOR_BORDER_ACCENT),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('SPAN', (0,1), (1,1))
    ]))
    story.append(t_hero)
    story.append(Spacer(1, 4))

    # --------------------------------------------------------------------------
    # 3. KEY METRICS MATRIX (Compact Terminal KPI Panels)
    # --------------------------------------------------------------------------
    quarters = getattr(summary_data, "quarters_analyzed", [])
    latest_q = quarters[-1] if quarters else "Latest"

    sales_growth = getattr(summary_data, "sales_growth_yoy", {})
    debtor_days = getattr(summary_data, "debtor_days", {})
    expense_residual = getattr(summary_data, "expense_adjusted_residual", {})
    
    latest_sales_g = sales_growth.get(latest_q)
    opm_delta = getattr(summary_data, "operating_margin_delta_bps", None)
    cfo_ratio = getattr(summary_data, "cfo_to_operating_profit", None)
    peer_spread = getattr(summary_data, "peer_spread_days", None)

    # Calculate statutory debtor days delta across valid observations
    valid_dd = [(q, debtor_days[q]) for q in quarters if debtor_days.get(q) is not None]
    dd_change = None
    if len(valid_dd) >= 2:
        dd_change = round(valid_dd[-1][1] - valid_dd[-2][1], 1)
    elif selected_anom and selected_anom.metric_type == "debtor_days":
        dd_change = selected_anom.delta

    # Format 4 Key Metric Cards
    card_sales = format_signed_metric_html(latest_sales_g, "%", "sales growth")
    card_opm = format_signed_metric_html(opm_delta, "bps", "operating margin")
    card_dd = format_signed_metric_html(dd_change, "d", "debtor days")
    card_cfo = f"<font color='{HEX_ACCENT_GREEN}'><b>{cfo_ratio*100.0:.1f}%</b></font>" if cfo_ratio is not None else f"<font color='{HEX_ACCENT_YELLOW}'><b>N/A</b></font>"

    kpi_matrix = [
        [
            Paragraph("<b>NET SALES YoY</b>", style_card_title),
            Paragraph("<b>OPERATING MARGIN Δ</b>", style_card_title),
            Paragraph("<b>DEBTOR DAYS Δ</b>", style_card_title),
            Paragraph("<b>CFO CONVERSION</b>", style_card_title)
        ],
        [
            Paragraph(card_sales, style_body),
            Paragraph(card_opm, style_body),
            Paragraph(card_dd, style_body),
            Paragraph(card_cfo, style_body)
        ],
        [
            Paragraph(f"<font color='{HEX_TEXT_MUTED}'>{latest_q} vs Prior Year</font>", style_meta),
            Paragraph(f"<font color='{HEX_TEXT_MUTED}'>Trailing YoY Shift</font>", style_meta),
            Paragraph(f"<font color='{HEX_TEXT_MUTED}'>Annual Audit Basis</font>", style_meta),
            Paragraph(f"<font color='{HEX_TEXT_MUTED}'>CFO / Operating Profit</font>", style_meta)
        ]
    ]
    t_kpis = Table(kpi_matrix, colWidths=[134.7, 134.7, 134.7, 134.7])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_CARD),
        ('BOX', (0,0), (-1,-1), 0.6, COLOR_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.4, COLOR_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 4))

    # --------------------------------------------------------------------------
    # 4. SECTION 2: WHY IT MATTERS (Business & Operational Implications)
    # --------------------------------------------------------------------------
    story.append(Paragraph("<font color='#58A6FF'><b>2. WHY IT MATTERS (OPERATIONAL & WORKING CAPITAL IMPACT)</b></font>", style_sec_title))
    story.append(Spacer(1, 1.5))
    why_matters = find_value(discovery, "why_it_matters", "2_Why_It_Matters", default=[])
    if isinstance(why_matters, list):
        for idx, item in enumerate(why_matters[:3], 1):
            story.append(Paragraph(f"<font color='{HEX_ACCENT_BLUE}'>◆</font> {safe_text(item)}", style_bullet))
    story.append(Spacer(1, 3))

    # --------------------------------------------------------------------------
    # 5. SECTION 3: DUAL-PANEL FORENSIC AUDIT VISUALIZER (Dark Matplotlib Chart)
    # --------------------------------------------------------------------------
    chart_path = None
    try:
        chart_path = generate_forensic_chart(summary_data)
    except Exception as e:
        print(f"[PDF Exporter Warning] Chart generation failed: {e}")

    if chart_path and os.path.exists(chart_path):
        story.append(Paragraph("<font color='#58A6FF'><b>3. HISTORICAL FORENSIC AUDIT VISUALIZER (TRAILING REPORTING CYCLES)</b></font>", style_sec_title))
        story.append(Spacer(1, 1.5))
        story.append(Image(chart_path, width=539, height=205))
        story.append(Paragraph(
            f"<font color='{HEX_TEXT_MUTED}'><i>Figure 1: Dual-panel quantitative audit trail. "
            f"Top: Reported Net Sales YoY (%) vs Expense-Adjusted Residual ({HEX_ACCENT_YELLOW} Heuristic screening metric). "
            f"Bottom: Audited Debtor Days channel credit velocity against sector reference threshold. Strictly backward-looking historical audit data.</i></font>",
            style_meta
        ))
        story.append(Spacer(1, 4))

    # --------------------------------------------------------------------------
    # 6. SECTION 4: FORENSIC RATIOS & DIAGNOSTIC MATRIX
    # --------------------------------------------------------------------------
    story.append(Paragraph("<font color='#58A6FF'><b>4. FORENSIC RATIOS & MULTI-PEER SPREAD MATRIX</b></font>", style_sec_title))
    story.append(Spacer(1, 1.5))

    dsri_val = getattr(summary_data, "beneish_dsri", None)
    dd_proxy_val = getattr(summary_data, "debtor_days_ratio_proxy", None)
    sgi_val = getattr(summary_data, "beneish_sgi", None)
    gmi_val = getattr(summary_data, "beneish_gmi", None)
    drag_val = getattr(summary_data, "expense_to_sales_ratio_change_bps", None)
    wedge_val = getattr(summary_data, "margin_wedge_bps", None)
    is_canonical_wedge = getattr(summary_data, "margin_wedge_is_canonical", False)

    wedge_title = "<b>QC Margin Wedge:</b>" if is_canonical_wedge else "<b>Operating Margin Δ:</b>"
    wedge_desc = "(Gross vs OPM)" if is_canonical_wedge else "(OPM Trailing Shift)"
    wedge_display_val = wedge_val if is_canonical_wedge else opm_delta
    wedge_html = format_signed_metric_html(wedge_display_val, "bps", "operating margin")

    dsri_html = f"<font color='{HEX_TEXT_PRIMARY}'><b>{dsri_val:.3f}</b></font>" if dsri_val is not None else f"<font color='{HEX_ACCENT_YELLOW}'><b>N/A</b></font>"
    dd_proxy_html = f"<font color='{HEX_TEXT_PRIMARY}'><b>{dd_proxy_val:.3f}</b></font>" if dd_proxy_val is not None else f"<font color='{HEX_ACCENT_YELLOW}'><b>N/A</b></font>"
    sgi_html = f"{sgi_val:.3f}" if sgi_val is not None else "N/A"
    gmi_html = f"{gmi_val:.3f}" if gmi_val is not None else "N/A"
    drag_html = format_signed_metric_html(drag_val, "bps", "expense drag")
    peer_sp_html = format_signed_metric_html(peer_spread, "d", "peer spread")

    matrix_rows = [
        [
            Paragraph("<b>Beneish DSRI (Canonical):</b>", style_table_head),
            Paragraph(f"{dsri_html} (Receivables/Sales YoY)", style_table_cell),
            Paragraph(wedge_title, style_table_head),
            Paragraph(f"{wedge_html} {wedge_desc}", style_table_cell)
        ],
        [
            Paragraph("<b>Debtor Days Ratio Proxy:</b>", style_table_head),
            Paragraph(f"{dd_proxy_html} (Debtor Days_t / Days_t-1)", style_table_cell),
            Paragraph("<b>Distribution Drag:</b>", style_table_head),
            Paragraph(f"{drag_html} (Exp/Sales Shift)", style_table_cell)
        ],
        [
            Paragraph("<b>Beneish SGI / GMI:</b>", style_table_head),
            Paragraph(f"SGI: <b>{sgi_html}</b> | GMI: <b>{gmi_html}</b>", style_table_cell),
            Paragraph("<b>Peer Relative Spread:</b>", style_table_head),
            Paragraph(f"{peer_sp_html} (vs Sector Median)", style_table_cell)
        ]
    ]
    t_matrix = Table(matrix_rows, colWidths=[120, 149.5, 120, 149.5])
    t_matrix.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_CARD),
        ('BACKGROUND', (0,0), (0,-1), COLOR_BG_CARD_ALT),
        ('BACKGROUND', (2,0), (2,-1), COLOR_BG_CARD_ALT),
        ('BOX', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.4, COLOR_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 1.8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.8),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(t_matrix)

    # --------------------------------------------------------------------------
    # PAGE BREAK FOR CRISP 2-PAGE INSTITUTIONAL LAYOUT
    # --------------------------------------------------------------------------
    story.append(PageBreak())

    # --------------------------------------------------------------------------
    # 7. SECTION 5: STATUTORY FINANCIAL TRAILING METRICS (Period-Aligned Table)
    # --------------------------------------------------------------------------
    story.append(Paragraph("<font color='#58A6FF'><b>5. STATUTORY FINANCIAL TRAILING METRICS (PERIOD-ALIGNED)</b></font>", style_sec_title))
    story.append(Spacer(1, 1.5))

    if quarters:
        cols_count = min(6, len(quarters))
        display_q = quarters[-cols_count:]

        header_row = [Paragraph("<b>Metric / Quarter</b>", style_table_head)] + [
            Paragraph(f"<b>{safe_text(q)}</b>", style_table_head) for q in display_q
        ]

        row_sales = [Paragraph("<b>Net Sales YoY (%)</b>", style_table_cell)] + [
            Paragraph(format_signed_metric_html(sales_growth.get(q), "%", "sales growth"), style_table_cell) for q in display_q
        ]

        row_debtor = [Paragraph("<b>Debtor Days (d)</b>", style_table_cell)] + [
            Paragraph(f"<font color='{HEX_TEXT_PRIMARY}'><b>{debtor_days.get(q):.1f}d</b></font>" if debtor_days.get(q) is not None else f"<font color='{HEX_ACCENT_YELLOW}'>N/A</font>", style_table_cell) for q in display_q
        ]

        row_residual = [Paragraph("<b>Expense Residual (%)</b>", style_table_cell)] + [
            Paragraph(f"<font color='{HEX_ACCENT_YELLOW}'><b>{expense_residual.get(q):+.2f}%</b></font>" if expense_residual.get(q) is not None else f"<font color='{HEX_ACCENT_YELLOW}'>N/A</font>", style_table_cell) for q in display_q
        ]

        col_w = [140] + [399 / cols_count] * cols_count
        t_trailing = Table([header_row, row_sales, row_debtor, row_residual], colWidths=col_w)
        t_trailing.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_BG_SECONDARY),
            ('BACKGROUND', (0,1), (-1,-1), COLOR_BG_CARD),
            ('BOX', (0,0), (-1,-1), 0.5, COLOR_BORDER),
            ('INNERGRID', (0,0), (-1,-1), 0.4, COLOR_BORDER),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        story.append(t_trailing)
        story.append(Spacer(1, 2))

    num_summary = find_value(discovery, "numbers", "5_Numbers", default="")
    if num_summary:
        story.append(Paragraph(f"<font color='{HEX_TEXT_SECONDARY}'><b>Forensic Calculation Summary:</b> {safe_text(num_summary)}</font>", style_meta))
    story.append(Spacer(1, 3))

    # --------------------------------------------------------------------------
    # 8. SECTION 6: TIMELINE & AUDITABLE EVIDENCE TRAIL (Statutory Filings)
    # --------------------------------------------------------------------------
    story.append(Paragraph("<font color='#58A6FF'><b>6. TIMELINE & TRACEABLE EVIDENCE TRAIL (STATUTORY FILINGS)</b></font>", style_sec_title))
    story.append(Spacer(1, 1.5))

    evidence_urls = find_value(discovery, "evidence", "3_Evidence", default=[])
    story.append(Paragraph(f"<font color='{HEX_TEXT_SECONDARY}'><b>Divergence Timeline:</b> {safe_text(timeline)}</font>", style_body))
    story.append(Paragraph(f"<font color='{HEX_TEXT_SECONDARY}'><b>Auditable Regulatory Filings & Excerpt Sources:</b></font>", style_body_secondary))
    if isinstance(evidence_urls, list):
        for u in evidence_urls[:4]:
            u_clean = safe_text(u)
            story.append(Paragraph(f"<font color='{HEX_ACCENT_BLUE}'>🔗 <a href='{u_clean}' color='{HEX_ACCENT_BLUE}'><u>{u_clean}</u></a></font>", style_meta))
    story.append(Spacer(1, 3))

    # --------------------------------------------------------------------------
    # 9. SECTION 7: ADVERSARIAL COUNTERARGUMENT (Defense / Alternative Explanations)
    # --------------------------------------------------------------------------
    story.append(Paragraph("<font color='#58A6FF'><b>7. ADVERSARIAL COUNTERARGUMENT (DEFENSE / ALTERNATIVE EXPLANATIONS)</b></font>", style_sec_title))
    story.append(Spacer(1, 1.5))
    counter_text = find_value(discovery, "counterargument", "6_Counterargument", default="Operational variance within screening tolerances.")
    story.append(Paragraph(f"<font color='{HEX_TEXT_SECONDARY}'><b>Strongest Plausible Macro / Operational Explanation:</b></font> {safe_text(counter_text)}", style_body))
    story.append(Spacer(1, 3))

    # --------------------------------------------------------------------------
    # 10. SECTION 8: OBJECTIVE FALSIFICATION & FINAL ADJUDICATION VERDICT
    # --------------------------------------------------------------------------
    story.append(Paragraph("<font color='#58A6FF'><b>8. OBJECTIVE FALSIFICATION CONDITION & ADJUDICATION VERDICT</b></font>", style_sec_title))
    story.append(Spacer(1, 1.5))

    falsify_text = find_value(discovery, "falsification", "7_Falsification_Condition", default="Normalization across trailing periods.")
    ev_strength_text = find_value(discovery, "strength", "8_Evidence_Strength", default="NOT_ESTABLISHED")

    # Resolve structured verdict and styling tokens
    verdict_raw = "NOT_ESTABLISHED"
    data_suff_raw = "SUFFICIENT"
    for v_key in ("SUPPORTED", "REFUTED", "NOT_ESTABLISHED"):
        if v_key in str(ev_strength_text).upper():
            verdict_raw = v_key
            break

    for s_key in ("INSUFFICIENT", "LIMITED", "SUFFICIENT"):
        if s_key in str(ev_strength_text).upper():
            data_suff_raw = s_key
            break

    v_theme = VERDICT_THEME.get(verdict_raw, VERDICT_THEME["NOT_ESTABLISHED"])
    s_theme = DATA_SUFFICIENCY_THEME.get(data_suff_raw, DATA_SUFFICIENCY_THEME["SUFFICIENT"])

    verdict_panel = [
        [
            Paragraph(f"<font color='{v_theme['hex']}'><b>VERDICT: {v_theme['label']}</b></font> "
                      f"<font color='{s_theme['hex']}'>// [{s_theme['label']}]</font>", style_sec_title)
        ],
        [
            Paragraph(f"<font color='{HEX_TEXT_SECONDARY}'><b>Falsification Criteria:</b> Disproven if: {safe_text(falsify_text)}</font>", style_body)
        ],
        [
            Paragraph(f"<font color='{HEX_TEXT_SECONDARY}'><b>Adjudication Rationale:</b> {safe_text(ev_strength_text)}</font>", style_body)
        ]
    ]
    t_verdict = Table(verdict_panel, colWidths=[539])
    t_verdict.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_CARD),
        ('BOX', (0,0), (-1,-1), 0.8, colors.HexColor(v_theme["border_hex"])),
        ('LINEBEFORE', (0,0), (0,-1), 3.0, colors.HexColor(v_theme["hex"])),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6)
    ]))
    story.append(t_verdict)
    story.append(Spacer(1, 3))

    # --------------------------------------------------------------------------
    # 11. METHODOLOGY & LIMITATIONS NOTE
    # --------------------------------------------------------------------------
    methodology_note = find_value(discovery, "methodology", "limitations", default=None)
    if not methodology_note:
        methodology_note = (
            "Audited using deterministic accounting math sandbox. All financial calculations strictly period-aligned. "
            "Expense residual is a screening proxy, not statutory unit volume. Zero predictive buy/sell recommendations."
        )
    story.append(Paragraph(
        f"<font color='{HEX_TEXT_MUTED}'><b>Methodological Caveat & Audit Parameters:</b> {safe_text(methodology_note)}</font>",
        style_meta
    ))

    # Build PDF Document with custom dark background on all pages
    canvas_maker = get_canvas_maker(track_name)
    doc.build(
        story,
        canvasmaker=canvas_maker,
        onFirstPage=draw_dark_background,
        onLaterPages=draw_dark_background
    )

    print(f"Successfully generated dark-theme PDF report: {output_path}")
    return output_path
