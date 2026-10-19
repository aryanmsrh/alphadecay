# ALPHA-DECAY: Autonomous Financial Research Agent
### ATMOS 2026 · BITS Pilani, Hyderabad Campus
**Track C: Consumer, FMCG & Retail Financial Discovery**  
**Participant Brief:** Finding the Next Signal Hackathon  
**Lead:** Aryan Mishra (`f20261228@hyderabad.bits-pilani.ac.in`)

---

## 1. Executive Summary

**ALPHA-DECAY** is an autonomous financial research agent built for high-conviction accounting forensics and non-obvious story discovery in Indian FMCG & Retail listed entities.

Rather than passive summarization, the system executes an active, adversarial research loop:
1. **Direct Ingestion:** Ingests trailing quarterly statements, balance sheets, ratios, and earnings call transcripts from Screener.in and regulatory exchange disclosures.
2. **Deterministic Calculations Only:** *Zero LLM Arithmetic.* Net sales YoY growth, operating profit margins, margin change in percentage points, expense growth, debtor turnover days, and cash flow conversion are calculated deterministically in pure Python with step-by-step arithmetic explanations accessible to non-business users.
3. **Top 5 Anomalies Ranked by Severity / 10:** Scans for operational and accounting divergences (working capital drag, debtor days elongation, cost decoupling, margin compression, cash flow deficits) and ranks them strictly descending by severity score.
4. **Cyclic Hypothesis & Disproving Pipeline:** For each anomaly, the agent formulates a sharp, testable forensic hypothesis and pits it against an adversarial **Disproving Agent**. If scrutiny breaks down the claim, the agent reformulates a refined Hypothesis #2 before advancing to the next anomaly.
5. **Strict Binary Final Verdict:**
   - **`HYPOTHESIS PASSED`**: The scrutiny of the disproving agent could *not* break down the hypothesis. An evidence-backed, non-obvious discovery was substantiated.
   - **`HYPOTHESIS FAILED`**: The scrutiny broke down the hypothesis; observed variations are fully explained by standard business cycles or sector-wide dynamics.
6. **Official 8-Point Hackathon Deliverable:** Generates the mandatory 8 research elements (The Discovery, Why It Matters, Evidence Sources, Timeline, Numbers, Counterargument, Falsification Condition, Evidence Strength).
7. **Apple Glassmorphic UI:** OLED pitch black (`#000000`) theme with frosted translucent glass cards, modern SF typography, monospace technical metrics, and vibrant red/green/blue accents.

---

## 2. System Architecture

```
[Target Listed FMCG Ticker] (e.g. HINDUNILVR, ITC, NESTLEIND, BRITANNIA)
         │
         ▼
[1. Data Ingestion: Screener.in + Concall Transcripts + Tavily Search]
         │
         ▼
[2. Deterministic Financial Sandbox (Zero LLM Math)]
  • YoY Revenue Growth, OPM %, YoY Margin Delta, Debtor Days, CFO Conversion
  • Step-by-Step Arithmetic + Plain-English Meanings & Significances
  • Detect up to 5 anomalies, score severity /10, and sort descending
         │
         ▼
[3. Cyclic Hypothesis & Disproving Pipeline]
  • Loop through sorted anomalies:
      ┌──────────────────────────────────────────────────────────────┐
      │ Anomaly #i (Severity: X/10)                                  │
      │   ├─ Formulate Hypothesis 1                                  │
      │   ├─ Pit against Disproving Agent                            │
      │   ├─ [HYPOTHESIS PASSED] -> Record as PASSED, advance        │
      │   └─ [HYPOTHESIS FAILED] -> Formulate Hypothesis 2           │
      │         ├─ Pit against Disproving Agent                      │
      │         ├─ [HYPOTHESIS PASSED] -> Record as PASSED, advance  │
      │         └─ [HYPOTHESIS FAILED] -> Record as FAILED, advance  │
      └──────────────────────────────────────────────────────────────┘
         │
         ▼
[4. Final Synthesis & Mandatory 8-Point Deliverable]
  • Strict Binary Verdict: HYPOTHESIS PASSED or HYPOTHESIS FAILED
  • 8-Point Research Brief: Discovery, Why It Matters, Evidence, Timeline,
    Numbers, Counterargument, Falsification Condition, Evidence Strength
         │
         ▼
[5. Apple Glassmorphic Web Dashboard & Publication-Grade PDF]
  • Pure pitch black with frosted glass blur, squircle cards & glowing pills
  • Instant 2-page research PDF export (ReportLab)
```

---

## 3. Quickstart & Usage

### Step 1: Run via CLI
```bash
# Run investigation on Hindustan Unilever with 2-page PDF export
python main.py --ticker HINDUNILVR --export-pdf

# Run on Nestle India
python main.py --ticker NESTLEIND --export-pdf

# Run fully offline using local Ollama (deepseek-r1:7b)
python main.py --ticker BRITANNIA --offline --export-pdf
```

### Step 2: Run the Web Dashboard
```bash
python run_web.py --port 5000
```
Open **http://127.0.0.1:5000** in your browser.

- **Dashboard:** Real-time completed investigations, binary verdicts (`HYPOTHESIS PASSED` / `HYPOTHESIS FAILED`), and primary discoveries.
- **New Investigation:** Quick-select Track C FMCG stocks or enter any listed ticker symbol.
- **Investigation Detail:** Interactive workspace with:
  - The Discovery banner
  - Plain-English math formulas and calculations
  - Top 5 tested anomalies ranked by severity `/10`
  - Cyclic Agent audit trail with passed vs failed hypotheses
  - Official 8-point research brief deliverable
  - Net sales & operating margin dual-axis trajectory chart
  - Traceable source links & concall excerpts
  - 1-click download of the 2-page research PDF
