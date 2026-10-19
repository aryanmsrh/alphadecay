import os
import sys
from pathlib import Path
import pypdf
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

class NumberedCanvas(canvas.Canvas):
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
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(26, 24, 612 - 26, 24)
        self.drawString(26, 14, "ALPHA-DECAY // AUTONOMOUS FINANCIAL RESEARCH AGENT — TECHNICAL SPECIFICATION")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 26, 14, page_str)
        self.restoreState()

def build_pdf(filename="ALPHA_DECAY_PROJECT_OVERVIEW.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=24,
        rightMargin=24,
        topMargin=20,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        textColor=colors.HexColor("#0f172a")
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#475569")
    )
    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=3,
        spaceAfter=2
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.0,
        leading=8.8,
        textColor=colors.HexColor("#1e293b")
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.0,
        leading=8.8,
        textColor=colors.HexColor("#0f172a")
    )
    mono_style = ParagraphStyle(
        "Mono",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=6.5,
        leading=8.0,
        textColor=colors.HexColor("#0f172a")
    )
    table_head = ParagraphStyle(
        "THead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.5,
        textColor=colors.white
    )
    table_cell = ParagraphStyle(
        "TCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.0,
        textColor=colors.HexColor("#1e293b")
    )
    table_cell_bold = ParagraphStyle(
        "TCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8.0,
        textColor=colors.HexColor("#0f172a")
    )

    story = []

    # ---------------- PAGE 1 ----------------
    # Header Banner
    header_data = [
        [
            Paragraph("<b>ALPHA-DECAY</b>: Autonomous Financial Forensic Research Agent", title_style),
            Paragraph("<b>ATMOS 2026 // BITS PILANI HYDERABAD</b><br/>Track C: Consumer, FMCG & Retail (NIFTY 50)", ParagraphStyle("TR", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9.2, alignment=2, textColor=colors.HexColor("#334155")))
        ],
        [
            Paragraph("System Architecture, Agentic Graph Pipeline, Deterministic Accounting Sandbox & Development Timeline", subtitle_style),
            Paragraph("<b>Evaluation Target:</b> Finding the Next Signal Hackathon", ParagraphStyle("TR2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.0, leading=9, alignment=2, textColor=colors.HexColor("#0284c7")))
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 204])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('LINEBELOW', (0,1), (-1,1), 1.0, colors.HexColor("#0f172a"))
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Overview: Autonomous Discovery vs. Summarisation", h1_style))
    story.append(Paragraph(
        "Most financial AI systems are superficial news summarizers or chat wrappers that hallucinate calculations and exhibit confirmatory bias. <b>ALPHA-DECAY</b> is an autonomous forensic research agent designed for the ATMOS 2026 BITS Pilani Hackathon ('Finding the Next Signal'). Given any NIFTY 50 company from Track C (Consumer, FMCG & Retail), ALPHA-DECAY independently investigates public filings, executes deterministic accounting mathematics, discovers hidden operational anomalies, subjects each anomaly to an adversarial disproving challenge, and outputs an auditable, evidence-backed research deliverable adhering strictly to the 8 mandatory brief requirements.",
        body_style
    ))
    story.append(Spacer(1, 3))

    # Section 2: End-to-End System Process Workflow
    story.append(Paragraph("2. Autonomous Investigation Process Workflow (6 Phases)", h1_style))
    proc_data = [
        [Paragraph("Phase", table_head), Paragraph("Engine Component", table_head), Paragraph("Operational Execution & Forensic Safeguards", table_head)],
        [
            Paragraph("<b>Phase 1: Ingestion</b>", table_cell_bold),
            Paragraph("Statutory Scrapers (Screener.in & BSE)", table_cell),
            Paragraph("Pulls multi-year quarterly P&L, annual balance sheets, and cash flow statements from audited SEBI LODR filings; harvests official BSE concall PDFs and extracts verbatim management commentary.", table_cell)
        ],
        [
            Paragraph("<b>Phase 2: Math Sandbox</b>", table_cell_bold),
            Paragraph("Deterministic Python Engine (analytics.py)", table_cell),
            Paragraph("100% pure Python execution. Enforces strict period matching: annual CFO matched against audited annual EBITDA ex-Other Income; quarterly sales YoY matched to identical seasonal quarter t-4. Zero LLM arithmetic.", table_cell)
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
            Paragraph("Emits strictly binary verdicts: <b>HYPOTHESIS PASSED</b> (withstood adversarial scrutiny) or <b>HYPOTHESIS FAILED</b> (refuted by operational context). Synthesizes the official 8-point research brief.", table_cell)
        ],
        [
            Paragraph("<b>Phase 6: Delivery</b>", table_cell_bold),
            Paragraph("ReportLab PDF & Flask Quant Terminal", table_cell),
            Paragraph("Renders a publication-grade 2-page dark research report, dual-axis trajectory chart, and interactive web dashboard featuring live execution polling, audited formulas, and direct BSE clickable links.", table_cell)
        ]
    ]
    proc_table = Table(proc_data, colWidths=[80, 140, 344])
    proc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(proc_table)
    story.append(Spacer(1, 4))

    # Section 3: The Multi-Agent Nodes & Adversarial Loop
    story.append(Paragraph("3. Multi-Agent Architecture: The Nodes & Cyclic Adversarial Logic", h1_style))
    story.append(Paragraph(
        "ALPHA-DECAY utilizes a specialized multi-agent graph with distinct epistemic boundaries. To eliminate confirmation bias, no single agent is allowed to declare a finding without adversarial cross-examination:",
        body_style
    ))
    story.append(Spacer(1, 2))

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
            Paragraph("Evaluates whether the defense broke down the hypothesis. Assigns binary <b>HYPOTHESIS PASSED</b> or <b>HYPOTHESIS FAILED</b>, audits evidence trail, and frames falsification criteria.", table_cell)
        ]
    ]
    nodes_table = Table(nodes_data, colWidths=[95, 145, 324])
    nodes_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(nodes_table)
    story.append(Spacer(1, 4))

    # Section 4: Deterministic Accounting Engine
    story.append(Paragraph("4. Deterministic Financial Math Sandbox: Exact Accounting Identities", h1_style))
    story.append(Paragraph(
        "To guarantee mathematical integrity, arithmetic is decoupled from LLM inference. All indicators are calculated directly in pure Python using audited balance sheets and SEBI LODR disclosures:",
        body_style
    ))
    story.append(Spacer(1, 2))

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
    math_table = Table(math_data, colWidths=[105, 155, 85, 219])
    math_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(math_table)

    # ---------------- PAGE 2 ----------------
    story.append(PageBreak())

    # Page 2 Header
    story.append(Paragraph("<b>ALPHA-DECAY</b> // Technology Stack, Development Timeline & Deliverable Compliance", title_style))
    story.append(Spacer(1, 4))

    # Section 5: Tech Stack
    story.append(Paragraph("5. Complete Technology Stack & Infrastructure", h1_style))
    stack_data = [
        [Paragraph("Layer", table_head), Paragraph("Technology / Framework", table_head), Paragraph("Design Rationale & Implementation Details", table_head)],
        [
            Paragraph("<b>Core & Runtime</b>", table_cell_bold),
            Paragraph("Python 3.10+, Flask, SQLite", table_cell),
            Paragraph("Pure Python deterministic core; lightweight Flask microservice; SQLite persistent caching for instant multi-company audit recall.", table_cell)
        ],
        [
            Paragraph("<b>LLM & Reasoning</b>", table_cell_bold),
            Paragraph("Google Gemini 2.5 Flash + Ollama (DeepSeek-R1)", table_cell),
            Paragraph("Dual-provider resilience: cloud-first Gemini 2.5 Flash for high-speed chain-of-thought; local Ollama zero-cost offline fallback.", table_cell)
        ],
        [
            Paragraph("<b>Ingestion & Scraping</b>", table_cell_bold),
            Paragraph("Requests, BeautifulSoup4, DuckDuckGo API", table_cell),
            Paragraph("Extracts statutory filings from Screener.in; downloads official BSE PDF concalls; harvests triangulating financial press articles.", table_cell)
        ],
        [
            Paragraph("<b>Exporters & Visuals</b>", table_cell_bold),
            Paragraph("ReportLab Canvas, Matplotlib, Chart.js", table_cell),
            Paragraph("ReportLab custom flowables for strict 2-page institutional PDF; Matplotlib dual-axis sales vs margin chart; Chart.js in browser.", table_cell)
        ],
        [
            Paragraph("<b>Frontend UI</b>", table_cell_bold),
            Paragraph("Pitch-Black Quant Terminal (#070709)", table_cell),
            Paragraph("Space Grotesk + Plus Jakarta Sans + JetBrains Mono typography; zero neon glow; responsive math cards; micro-elevation shadows.", table_cell)
        ]
    ]
    stack_table = Table(stack_data, colWidths=[90, 150, 324])
    stack_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(stack_table)
    story.append(Spacer(1, 4))

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
    tl_table = Table(tl_data, colWidths=[90, 130, 344])
    tl_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(tl_table)
    story.append(Spacer(1, 4))

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
    brief_table = Table(brief_data, colWidths=[90, 192, 90, 192])
    brief_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white])
    ]))
    story.append(brief_table)
    story.append(Spacer(1, 4))

    # Section 8: Key Architectural Advantages
    story.append(Paragraph("8. Key Architectural Edge for Finals Live Testing", h1_style))
    story.append(Paragraph(
        "<b>1. Zero Arithmetic Hallucination:</b> Pure Python deterministic calculations guarantee accurate numbers during live evaluations.<br/>"
        "<b>2. Multi-Company Generalizability:</b> Works out-of-the-box across any Track C listed company (HUL, ITC, Nestle, Britannia, Tata Consumer).<br/>"
        "<b>3. Dual-Provider Resilience:</b> Seamless switch to local Ollama (deepseek-r1:7b) via <code>--offline</code> protects against venue Wi-Fi drops.<br/>"
        "<b>4. Complete Auditability:</b> Every claim links back to SEBI LODR filings, eliminating subjective LLM assertions.",
        body_style
    ))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)

    # Check page count
    reader = pypdf.PdfReader(filename)
    page_count = len(reader.pages)
    print(f"Generated {filename}: {page_count} pages")
    assert page_count == 2, f"Expected exactly 2 pages, got {page_count}"

if __name__ == "__main__":
    build_pdf()
