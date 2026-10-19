import os
import sys
from pathlib import Path
import pypdf
import pymupdf
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# 1. Register Exact Website Fonts (Space Grotesk + Plus Jakarta Sans + JetBrains Mono)
FONTS_DIR = Path("webapp/static/fonts")

pdfmetrics.registerFont(TTFont("SpaceGrotesk-Bold", str(FONTS_DIR / "SpaceGrotesk-Bold.ttf")))
pdfmetrics.registerFont(TTFont("SpaceGrotesk", str(FONTS_DIR / "SpaceGrotesk-Bold.ttf")))
pdfmetrics.registerFont(TTFont("PlusJakartaSans", str(FONTS_DIR / "PlusJakartaSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("JetBrainsMono", str(FONTS_DIR / "JetBrainsMono-Regular.ttf")))
pdfmetrics.registerFont(TTFont("JetBrainsMono-Bold", str(FONTS_DIR / "JetBrainsMono-Bold.ttf")))

registerFontFamily("JetBrainsMono", normal="JetBrainsMono", bold="JetBrainsMono-Bold")

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
        self.setFont("JetBrainsMono", 7.0)
        self.setFillColor(colors.HexColor("#71717a")) # --text-muted
        self.drawString(20, 10, "ALPHA-DECAY // QUANT FORENSIC SPECIFICATION")

        # Center: Clean GitHub Link without overlap
        self.setFont("JetBrainsMono", 7.0)
        self.setFillColor(colors.HexColor("#38bdf8")) # --accent-blue
        self.drawCentredString(316, 10, "github.com/aryanmsrh/alphadecay")

        # Right: Page Indicator in JetBrains Mono Bold with Accent Sky Blue
        self.setFont("JetBrainsMono-Bold", 7.0)
        page_str = f"PAGE {self._pageNumber} OF {page_count}"
        self.drawRightString(612 - 20, 10, page_str)
        self.restoreState()

def build_pdf(filename="ALPHA_DECAY_PROJECT_OVERVIEW.pdf"):
    # Usable width: 612 - 40 = 572pt
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=20,
        rightMargin=20,
        topMargin=14,
        bottomMargin=23
    )

    styles = getSampleStyleSheet()

    # Enhanced Typography matching website theme.css with larger, high-readability font sizes
    title_style = ParagraphStyle(
        "WebTitle",
        parent=styles["Normal"],
        fontName="SpaceGrotesk-Bold",
        fontSize=13.5,
        leading=15.5,
        textColor=colors.HexColor("#f4f4f6")
    )
    subtitle_style = ParagraphStyle(
        "WebSubtitle",
        parent=styles["Normal"],
        fontName="PlusJakartaSans",
        fontSize=8.0,
        leading=10.0,
        textColor=colors.HexColor("#a1a1aa")
    )
    h1_style = ParagraphStyle(
        "WebH1",
        parent=styles["Normal"],
        fontName="SpaceGrotesk-Bold",
        fontSize=9.0,
        leading=11.5,
        textColor=colors.HexColor("#38bdf8"), # --accent-blue
        spaceBefore=2.0,
        spaceAfter=1.0
    )
    body_style = ParagraphStyle(
        "WebBody",
        parent=styles["Normal"],
        fontName="PlusJakartaSans",
        fontSize=7.4,
        leading=9.5,
        textColor=colors.HexColor("#e4e4e7") # High-contrast primary text
    )
    mono_style = ParagraphStyle(
        "WebMono",
        parent=styles["Normal"],
        fontName="JetBrainsMono",
        fontSize=6.7,
        leading=8.3,
        textColor=colors.HexColor("#38bdf8")
    )
    table_head = ParagraphStyle(
        "WebTHead",
        parent=styles["Normal"],
        fontName="JetBrainsMono-Bold",
        fontSize=7.2,
        leading=9.0,
        textColor=colors.HexColor("#38bdf8")
    )
    table_cell = ParagraphStyle(
        "WebTCell",
        parent=styles["Normal"],
        fontName="PlusJakartaSans",
        fontSize=7.0,
        leading=8.8,
        textColor=colors.HexColor("#e4e4e7")
    )
    table_cell_bold = ParagraphStyle(
        "WebTCellBold",
        parent=styles["Normal"],
        fontName="SpaceGrotesk-Bold",
        fontSize=7.2,
        leading=8.8,
        textColor=colors.HexColor("#f4f4f6")
    )

    story = []

    # ---------------- PAGE 1 ----------------
    # Top Entity Header Card with Repository Link (colWidths total = 572)
    header_data = [
        [
            Paragraph("<b>ALPHA-DECAY</b>: Autonomous Financial Forensic Research Agent", title_style),
            Paragraph("<b>ATMOS 2026 // BITS PILANI HYDERABAD</b><br/><font color='#22c55e'>Track C: Consumer, FMCG & Retail (NIFTY 50)</font>", ParagraphStyle("TR", parent=styles["Normal"], fontName="JetBrainsMono-Bold", fontSize=7.2, leading=9.2, alignment=2, textColor=colors.HexColor("#f4f4f6")))
        ],
        [
            Paragraph("System Architecture, Multi-Agent Nodes, Deterministic Math Sandbox & Development Timeline", subtitle_style),
            Paragraph("<font color='#38bdf8'>REPOSITORY:</font> <a href='https://github.com/aryanmsrh/alphadecay'><font color='#38bdf8'><u>github.com/aryanmsrh/alphadecay</u></font></a>", ParagraphStyle("TR2", parent=styles["Normal"], fontName="JetBrainsMono-Bold", fontSize=7.0, leading=8.8, alignment=2, textColor=colors.HexColor("#38bdf8")))
        ]
    ]
    header_table = Table(header_data, colWidths=[364, 208])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#131318")), # --bg-surface
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#27272a")), # --border
        ('LINEBELOW', (0,1), (-1,1), 1.0, colors.HexColor("#38bdf8")) # Cyan accent line
    ]))
    story.append(header_table)
    story.append(Spacer(1, 2))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Overview: Autonomous Discovery vs. Summarisation", h1_style))
    story.append(Paragraph(
        "Traditional financial AI tools act as superficial news summarizers or chat wrappers that hallucinate arithmetic and exhibit confirmatory bias. <b>ALPHA-DECAY</b> is an autonomous financial research agent built for the ATMOS 2026 Hackathon ('Finding the Next Signal'). Given any NIFTY 50 FMCG company from Track C, ALPHA-DECAY independently ingests public statutory filings, derives non-obvious mathematical accounting relationships, forms an original hypothesis, subjects it to adversarial falsification challenges, and generates an auditable, evidence-backed research deliverable meeting all 8 brief requirements.",
        body_style
    ))
    story.append(Spacer(1, 2))

    # Section 2: End-to-End System Process Workflow
    story.append(Paragraph("2. Autonomous Investigation Process Workflow (6 Phases)", h1_style))
    proc_data = [
        [Paragraph("Phase", table_head), Paragraph("Engine Component", table_head), Paragraph("Operational Execution & Forensic Safeguards", table_head)],
        [
            Paragraph("<b>Phase 1: Ingestion</b>", table_cell_bold),
            Paragraph("Statutory Scrapers (Screener & BSE)", table_cell),
            Paragraph("Harvests multi-year quarterly P&L, annual balance sheets, and cash flow statements from audited SEBI LODR filings; extracts verbatim dialogue blocks from official BSE concall PDFs via PyPDF.", table_cell)
        ],
        [
            Paragraph("<b>Phase 2: Math Sandbox</b>", table_cell_bold),
            Paragraph("Deterministic Python Engine (analytics.py)", table_cell),
            Paragraph("100% pure Python execution. Enforces strict period matching: annual CFO benchmarked against audited annual EBITDA ex-Other Income; quarterly sales YoY matched to identical quarter t-4. Zero LLM math.", table_cell)
        ],
        [
            Paragraph("<b>Phase 3: Triage</b>", table_cell_bold),
            Paragraph("Forensic Scoring & Ranking (forensics.py)", table_cell),
            Paragraph("Ranks observed divergences into candidate anomalies by severity (/10): CFO-to-EBITDA decoupling, supplier payable stretches, DSO debtor velocity shifts, inventory DIO expansions, and margin wedges.", table_cell)
        ],
        [
            Paragraph("<b>Phase 4: Adversarial Loop</b>", table_cell_bold),
            Paragraph("Cyclic Pipeline (cyclic_pipeline.py)", table_cell),
            Paragraph("Investigative Agent formulates a causal hypothesis. Disproving Agent acts as skeptical defense, testing whether ordinary FMCG commercial dynamics explain the shift. If broken down, Attempt 2 is refined.", table_cell)
        ],
        [
            Paragraph("<b>Phase 5: Adjudication</b>", table_cell_bold),
            Paragraph("Binary Verification Gate", table_cell),
            Paragraph("Emits strictly binary verdicts: <b><font color='#22c55e'>HYPOTHESIS PASSED</font></b> (withstood adversarial scrutiny) or <b><font color='#f43f5e'>HYPOTHESIS FAILED</font></b> (refuted by operational context). Synthesizes the official 8-point research brief.", table_cell)
        ],
        [
            Paragraph("<b>Phase 6: Delivery</b>", table_cell_bold),
            Paragraph("ReportLab PDF & Flask Quant Terminal", table_cell),
            Paragraph("Renders a publication-grade 2-page dark research report, dual-axis trajectory chart, and interactive web dashboard featuring live execution polling, audited formulas, and direct BSE clickable links.", table_cell)
        ]
    ]
    proc_table = Table(proc_data, colWidths=[84, 142, 346])
    proc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#18181f")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#27272a")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#111116"), colors.HexColor("#15151c")])
    ]))
    story.append(proc_table)
    story.append(Spacer(1, 2))

    # Section 3: The Multi-Agent Nodes & Adversarial Loop
    story.append(Paragraph("3. Multi-Agent Architecture: The Nodes & Cyclic Adversarial Logic", h1_style))
    story.append(Paragraph(
        "ALPHA-DECAY utilizes a specialized multi-agent graph with distinct epistemic boundaries. To eliminate confirmation bias, no single agent is allowed to declare a finding without adversarial cross-examination:",
        body_style
    ))
    story.append(Spacer(1, 1.2))

    nodes_data = [
        [Paragraph("Agent / Node", table_head), Paragraph("Role & Epistemic Mandate", table_head), Paragraph("Implementation Mechanics & Failure Modes Prevented", table_head)],
        [
            Paragraph("<b>Investigative Agent</b><br/>(Prosecution)", table_cell_bold),
            Paragraph("Formulates causal hypotheses connecting mathematical divergences to operational anomalies.", table_cell),
            Paragraph("Analyzes top-ranked anomaly candidates against concall transcripts. Pinpoints non-obvious operational explanations (e.g., vendor payable optimization, marketing accrual cash drain).", table_cell)
        ],
        [
            Paragraph("<b>Disproving Agent</b><br/>(Defense)", table_cell_bold),
            Paragraph("Adversarial stress-tester. Seeks to refute the hypothesis using benign commercial context.", table_cell),
            Paragraph("Challenges hypotheses using structural FMCG realities (e.g. negative CCC of -89 days proving supplier leverage, raw material price buffering). Breaks down ungrounded claims.", table_cell)
        ],
        [
            Paragraph("<b>Cyclic Refinement</b><br/>(Attempt 1 -> 2)", table_cell_bold),
            Paragraph("Self-correcting iterative retry loop across anomalous candidates.", table_cell),
            Paragraph("If Attempt 1 is refuted by the defense, the agent synthesizes defense critique to formulate an airtight Attempt 2, or abandons the thesis and marks it as refuted.", table_cell)
        ],
        [
            Paragraph("<b>Adjudication Node</b><br/>(Independent Judge)", table_cell_bold),
            Paragraph("Enforces strictly binary terminal verdicts and audits evidence strength.", table_cell),
            Paragraph("Evaluates whether the defense broke down the hypothesis. Assigns binary <b><font color='#22c55e'>HYPOTHESIS PASSED</font></b> or <b><font color='#f43f5e'>HYPOTHESIS FAILED</font></b>, audits evidence trail, and frames falsification criteria.", table_cell)
        ]
    ]
    nodes_table = Table(nodes_data, colWidths=[96, 146, 330])
    nodes_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#18181f")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#27272a")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#111116"), colors.HexColor("#15151c")])
    ]))
    story.append(nodes_table)
    story.append(Spacer(1, 2))

    # Section 4: Deterministic Accounting Engine
    story.append(Paragraph("4. Deterministic Financial Math Sandbox: Exact Accounting Identities", h1_style))
    story.append(Paragraph(
        "To guarantee mathematical integrity, arithmetic is decoupled from LLM inference. All indicators are calculated directly in pure Python using audited balance sheets and SEBI LODR disclosures:",
        body_style
    ))
    story.append(Spacer(1, 1.2))

    math_data = [
        [Paragraph("Forensic Indicator", table_head), Paragraph("Exact Formula", table_head), Paragraph("Period Alignment", table_head), Paragraph("Forensic Significance & Diagnostic Insight", table_head)],
        [
            Paragraph("<b>CFO-to-EBITDA Ratio</b>", table_cell_bold),
            Paragraph("(Audited_CFO / Audited_Operating_Profit) * 100", mono_style),
            Paragraph("Audited Annual to Annual", table_cell),
            Paragraph("Earnings quality test. A drop below 80% (e.g. HUL: 80.9% to 73.1%) reveals operating profit decoupling from physical cash flow.", table_cell)
        ],
        [
            Paragraph("<b>EBITDA (ex-Other Inc)</b>", table_cell_bold),
            Paragraph("Net_Sales - Total_Operating_Expenses", mono_style),
            Paragraph("Quarterly & Annual", table_cell),
            Paragraph("Isolates pure manufacturing/distribution operating profit, stripping non-operating treasury income gains.", table_cell)
        ],
        [
            Paragraph("<b>Cash Conversion Cycle</b>", table_cell_bold),
            Paragraph("DSO (Debtor) + DIO (Inv) - DPO (Payable)", mono_style),
            Paragraph("Audited Annual", table_cell),
            Paragraph("Measures working capital financing. A deeply negative cycle (-89d for HUL) proves vendors are funding operational inventory.", table_cell)
        ],
        [
            Paragraph("<b>Debtor / DSO Velocity</b>", table_cell_bold),
            Paragraph("(Trade_Receivables / Audited_Sales) * 365", mono_style),
            Paragraph("Annual Audited", table_cell),
            Paragraph("Distributor credit terms. Measures how fast wholesale trade partners settle receivables (HUL: improved 23d -> 19d).", table_cell)
        ]
    ]
    math_table = Table(math_data, colWidths=[108, 156, 88, 220])
    math_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#18181f")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#27272a")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#111116"), colors.HexColor("#15151c")])
    ]))
    story.append(math_table)

    # ---------------- PAGE 2 ----------------
    story.append(PageBreak())

    # Page 2 Header Card with Repository Link
    p2_header_data = [
        [
            Paragraph("<b>ALPHA-DECAY</b> // Technology Stack, Development Timeline & Deliverable Compliance", title_style),
            Paragraph("<b>REPOSITORY:</b> <a href='https://github.com/aryanmsrh/alphadecay'><font color='#38bdf8'><u>github.com/aryanmsrh/alphadecay</u></font></a>", ParagraphStyle("TRP2", parent=styles["Normal"], fontName="JetBrainsMono-Bold", fontSize=7.0, leading=8.8, alignment=2, textColor=colors.HexColor("#38bdf8")))
        ]
    ]
    p2_header_table = Table(p2_header_data, colWidths=[364, 208])
    p2_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#131318")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#27272a")),
        ('LINEBELOW', (0,0), (-1,0), 1.0, colors.HexColor("#38bdf8"))
    ]))
    story.append(p2_header_table)
    story.append(Spacer(1, 2))

    # Section 5: Tech Stack (Strictly verified against actual codebase)
    story.append(Paragraph("5. Verified Technology Stack & Production Infrastructure (Audited Against Codebase)", h1_style))
    stack_data = [
        [Paragraph("Layer", table_head), Paragraph("Actual Technology Used", table_head), Paragraph("Codebase Verification & Architectural Implementation Details", table_head)],
        [
            Paragraph("<b>Core & Runtime</b>", table_cell_bold),
            Paragraph("Python 3.10+, Flask 3.1, Atomic JSON Store", table_cell),
            Paragraph("Pure Python deterministic core; lightweight Flask microservice (run_web.py); transactional JSON run store (webapp/run_store.py) with atomic .tmp swap.", table_cell)
        ],
        [
            Paragraph("<b>LLM & Reasoning</b>", table_cell_bold),
            Paragraph("Google Gemini 3.5 Flash Lite + Ollama (DeepSeek-R1)", table_cell),
            Paragraph("Direct HTTP client (httpx) with high thinking level; cloud Gemini 3.5 Flash Lite primary; local Ollama deepseek-r1:7b offline reasoning fallback.", table_cell)
        ],
        [
            Paragraph("<b>Ingestion & Harvest</b>", table_cell_bold),
            Paragraph("Requests, BeautifulSoup4, PyPDF, Tavily API", table_cell),
            Paragraph("Screener.in scraping via requests/BS4; official BSE concall PDFs downloaded via httpx and parsed via PyPDF; targeted financial search via Tavily.", table_cell)
        ],
        [
            Paragraph("<b>Exporters & Visuals</b>", table_cell_bold),
            Paragraph("ReportLab 5.0, Matplotlib 3.11, Chart.js", table_cell),
            Paragraph("ReportLab custom flowables for strictly 2-page dark research PDF; Matplotlib dual-axis sales vs margin chart; Chart.js in browser workstation.", table_cell)
        ],
        [
            Paragraph("<b>Frontend UI</b>", table_cell_bold),
            Paragraph("Pitch-Black Quant Terminal (#070709)", table_cell),
            Paragraph("Space Grotesk + Plus Jakarta Sans + JetBrains Mono typography; zero neon glow; responsive math cards; micro-elevation shadows.", table_cell)
        ]
    ]
    stack_table = Table(stack_data, colWidths=[92, 152, 328])
    stack_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#18181f")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#27272a")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#111116"), colors.HexColor("#15151c")])
    ]))
    story.append(stack_table)
    story.append(Spacer(1, 2))

    # Section 6: Development Timeline (16th - 19th Oct)
    story.append(Paragraph("6. Development Timeline: Day-by-Day Engineering Milestones (16th – 19th Oct 2026)", h1_style))
    tl_data = [
        [Paragraph("Date & Phase", table_head), Paragraph("Milestone Target", table_head), Paragraph("Key Technical Hurdles Solved & Architecture Built", table_head)],
        [
            Paragraph("<b>16 October 2026</b><br/>Day 1: Foundations", table_cell_bold),
            Paragraph("Problem Framing & Data Ingestion Scaffolding", table_cell),
            Paragraph("Scoped Track C (Consumer, FMCG & Retail). Built robust Screener.in scraper parsing audited quarterly P&L, annual balance sheets, and cash flows. Engineered BSE India concall PDF downloader and dialogue extractor.", table_cell)
        ],
        [
            Paragraph("<b>17 October 2026</b><br/>Day 2: Deterministic Math", table_cell_bold),
            Paragraph("Pure Python Analytics & Period Alignment", table_cell),
            Paragraph("Eliminated LLM arithmetic hallucinations by writing pure Python formulas for YoY revenue growth, EBITDA ex-other income, CFO conversion, DIO, DSO, and CCC. Resolved quarterly-vs-annual mismatch by locking audited annual period baselines.", table_cell)
        ],
        [
            Paragraph("<b>18 October 2026</b><br/>Day 3: Adversarial Pipeline", table_cell_bold),
            Paragraph("Cyclic Agent Loop & ReportLab Exporter", table_cell),
            Paragraph("Architected the 2-attempt adversarial challenge loop (Investigative Agent vs Disproving Agent). Built binary adjudication verdict logic (HYPOTHESIS PASSED / FAILED). Authored custom ReportLab canvas strictly constrained to 2 pages.", table_cell)
        ],
        [
            Paragraph("<b>19 October 2026</b><br/>Day 4: Polish & Packaging", table_cell_bold),
            Paragraph("Quant Terminal UI, Bug Fixes & Live Auditing", table_cell),
            Paragraph("Redesigned UI to pitch-black quant workstation (#070709) with Space Grotesk / JetBrains Mono typography. Fixed double-sign (+- / ++) artifacts and hardcoded significance strings. Tested clean run on HUL with verified 2-page PDF and merged to main.", table_cell)
        ]
    ]
    tl_table = Table(tl_data, colWidths=[92, 132, 348])
    tl_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#18181f")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#27272a")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#111116"), colors.HexColor("#15151c")])
    ]))
    story.append(tl_table)
    story.append(Spacer(1, 2))

    # Section 7: Official 8-Point Hackathon Brief Compliance
    story.append(Paragraph("7. Official 8-Point Hackathon Deliverable Brief Compliance", h1_style))
    brief_data = [
        [Paragraph("Brief Requirement", table_head), Paragraph("AlphaDecay Implementation", table_head), Paragraph("Brief Requirement", table_head), Paragraph("AlphaDecay Implementation", table_head)],
        [
            Paragraph("<b>1. The Discovery</b>", table_cell_bold), Paragraph("One clear sentence describing the non-obvious finding.", table_cell),
            Paragraph("<b>5. Numbers</b>", table_cell_bold), Paragraph("Deterministic calculations & formulas substantiating finding.", table_cell)
        ],
        [
            Paragraph("<b>2. Why It Matters</b>", table_cell_bold), Paragraph("3 to 5 bullets detailing operational & capital significance.", table_cell),
            Paragraph("<b>6. Counterargument</b>", table_cell_bold), Paragraph("Strongest alternative explanation evaluated by defense agent.", table_cell)
        ],
        [
            Paragraph("<b>3. Evidence</b>", table_cell_bold), Paragraph("Multiple independent sources with direct, clickable links.", table_cell),
            Paragraph("<b>7. Falsification</b>", table_cell_bold), Paragraph("Explicit future empirical condition that would disprove finding.", table_cell)
        ],
        [
            Paragraph("<b>4. Timeline</b>", table_cell_bold), Paragraph("Chronological emergence across sequential reporting periods.", table_cell),
            Paragraph("<b>8. Evidence Strength</b>", table_cell_bold), Paragraph("Strong, Moderate, or Weak rating with audit rationale.", table_cell)
        ]
    ]
    brief_table = Table(brief_data, colWidths=[92, 194, 92, 194])
    brief_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#18181f")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.1),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#27272a")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#111116"), colors.HexColor("#15151c")])
    ]))
    story.append(brief_table)
    story.append(Spacer(1, 2))

    # Section 8: Key Architectural Advantages
    story.append(Paragraph("8. Key Architectural Edge for Finals Live Testing", h1_style))
    story.append(Paragraph(
        "<b><font color='#38bdf8'>1. Zero Arithmetic Hallucination:</font></b> Pure Python deterministic calculations guarantee accurate numbers during live evaluations.<br/>"
        "<b><font color='#38bdf8'>2. Multi-Company Generalizability:</font></b> Works out-of-the-box across any Track C listed company (HUL, ITC, Nestle, Britannia, Tata Consumer).<br/>"
        "<b><font color='#38bdf8'>3. Dual-Provider Resilience:</font></b> Seamless switch to local Ollama (deepseek-r1:7b) via <code>--offline</code> routes LLM reasoning locally without cloud API keys.<br/>"
        "<b><font color='#38bdf8'>4. Complete Auditability:</font></b> Every claim links back to SEBI LODR filings, eliminating subjective LLM assertions.",
        body_style
    ))

    # Build the document with background drawing callback
    doc.build(
        story,
        onFirstPage=draw_website_background,
        onLaterPages=draw_website_background,
        canvasmaker=WebsiteThemedCanvas
    )

    # Check page count
    reader = pypdf.PdfReader(filename)
    page_count = len(reader.pages)
    print(f"Generated {filename}: {page_count} pages")
    assert page_count == 2, f"Expected exactly 2 pages, got {page_count}"

    # Render PNGs for visual inspection
    doc_fitz = pymupdf.open(filename)
    doc_fitz[0].get_pixmap(dpi=150).save("page_1.png")
    doc_fitz[1].get_pixmap(dpi=150).save("page_2.png")
    print("Exported page_1.png and page_2.png for visual verification.")

if __name__ == "__main__":
    build_pdf()
