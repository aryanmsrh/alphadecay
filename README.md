# AlphaDecay: Autonomous Forensic Financial Research Agent

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Orchestrator: LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Track C: Consumer, FMCG & Retail**  
**ATMOS 2026 — "Finding the Next Signal" Autonomous Financial Research Hackathon**  
*Organized by The Wall Street Club × Economics Association (BITS Pilani, Hyderabad Campus) & Signal1*  
**Team:** AlphaDecay  
**Lead:** Aryan Mishra (`f20261228@hyderabad.bits-pilani.ac.in`)

---

## 1. Architectural Philosophy: Autonomous Discovery vs. Summarization

Conventional financial AI systems act as **passive summarizers** (linear RAG). They ingest a single earnings call or filing, extract management's prepared remarks, and parrot consensus marketing narratives. 

True forensic financial discoveries almost never reside in a single disclosure. A company's revenue growth might look robust in its press release, while notes to accounts reveal surging distributor credit terms (channel stuffing) and competitor filings show volume contraction under identical macro conditions.

**AlphaDecay is built as an Autonomous Investigator.** It operates as a stateful, cyclic multi-agent graph (LangGraph) that:
1. Ingests raw statutory filings across trailing 8 quarters via deterministic scrapers (`httpx` + `BeautifulSoup4`).
2. Calculates accounting ratios in a **zero-LLM deterministic math sandbox** (`Python` / `NumPy`).
3. Executes a multi-agent **"Courtroom" debate** where an **Evidence Harvester (The Prosecution)** builds the case and an **Adversarial Critic (The Defense)** actively attempts to disprove the hypothesis using macro/statutory justifications.
4. Adheres strictly to the **no-investment-advice rule**: The deliverable is discrepancy discovery, terminating with an auditable evidence trail and an objective **Falsification Condition**.

---

## 2. System Architecture & Cyclic State Machine

```
                            [User Input Ticker]
                                    │
                                    ▼
       [1. Ingestion Layer] ──► Screener.in + BSE Filings API (httpx + BS4)
                                    │
                                    ▼
       [2. Deterministic Math Sandbox] ──► Debtor Days, UVG, CCC, Margin Wedge
                                    │
                                    ▼
       ┌──────────────────────────────────────────────────────────────┐
       │             3. LANGGRAPH CYCLIC STATE ENGINE                 │
       │                                                              │
       │   • Anomaly Triage Node: Ranks deviations by [Δ Dev × Mat]   │
       │          │                                                   │
       │          ▼                                                   │
       │   • Evidence Harvester (Prosecutor): Concalls & Filings      │
       │          │                                                   │
       │          ▼                                                   │
       │   • Peer Triangulation: Dabur, Marico, Nestlé benchmarks     │
       │          │                                                   │
       │          ▼                                                   │
       │   • Adversarial Critic (The Defense): Self-Falsification     │
       │          │                                                   │
       │          ├──────► [FALSIFIED by Macro] ──► Loops to Triage   │
       │          │                                                   │
       │          ▼ (Survives Scrutiny)                               │
       └──────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
       [4. Deliverable: Mandatory 8-Point Forensic Output Schema]
```

---

## 3. Deterministic Accounting Formulas (0-LLM Math Sandbox)

To prevent LLM mathematical hallucination, all ratios are computed in pure Python/NumPy:

* **Realization Growth (%)**:
  $$\text{Realization \%} \approx \text{Sales Growth \%} - \text{Underlying Volume Growth (UVG \%)}$$
  *Diagnostic:* Sales $>+5\%$ while UVG $\le 0\%$ for $\ge 2$ quarters indicates pricing power exhaustion.

* **Debtor Days (Trade Receivable Days)**:
  $$\text{Debtor Days} = \frac{\text{Trade Receivables}}{\text{Quarterly Net Sales} \times 4} \times 365$$
  $$\Delta \text{Debtor Days} = \text{Debtor Days}_{Q_t} - \text{Debtor Days}_{Q_{t-4}}$$
  *Diagnostic:* $\Delta \text{Debtor Days} \ge +15\text{ days}$ YoY signals distributor channel stuffing.

* **Cash Conversion Quality**:
  $$\text{Cash Ratio} = \frac{\text{Operating Cash Flow (CFO)}}{\text{Operating EBITDA}}$$
  $$\text{Cash Conversion Cycle (CCC)} = \text{Debtor Days} + \text{Inventory Days} - \text{Payable Days}$$
  *Diagnostic:* $\text{CFO}/\text{EBITDA} < 0.65$ or $\Delta \text{CCC} \ge +20\text{ days}$ diagnoses paper accounting profits.

* **Quick Commerce Margin Wedge**:
  $$\text{Margin Wedge (bps)} = \Delta \text{Gross Margin (bps)} - \Delta \text{EBITDA Margin (bps)}$$
  *Diagnostic:* $>+150\text{ bps}$ wedge identifies distribution fees/take-rates (18–22%) eroding operating margins despite input deflation.

---

## 4. Quickstart Guide (Using `uv`)

### Prerequisites
* Linux / WSL2 Ubuntu with Python 3.10+
* `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
* Ollama installed locally (`ollama run qwen2.5-coder:7b`)

### 1. Clone & Setup Environment with `uv`
```bash
git clone https://github.com/aryanmsrh/alphadecay.git
cd alphadecay

# Create clean virtual environment using uv
uv venv

# Activate virtualenv
source .venv/bin/activate

# Install locked dependencies via uv
uv pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
```bash
cp .env.example .env
```
Edit `.env` to configure your API keys (optional for mock/offline testing):
* `TAVILY_API_KEY`: For live concall and web peer triangulation (free tier: 1,000 queries/mo).
* `GEMINI_API_KEY`: For Google Gemini 2.0 Flash high-context parsing (free tier via Google AI Studio).
* `USE_OFFLINE_MODE`: Set to `True` for 100% offline local demo execution.

### 3. Run the Verification Test Suite
```bash
python test_pipeline.py
```

### 4. Run an Autonomous Investigation
```bash
# Analyze Hindustan Unilever
python main.py --ticker HINDUNILVR

# Analyze Britannia Industries
python main.py --ticker BRITANNIA

# Analyze ITC Limited
python main.py --ticker ITC
```

---

## 5. Mandatory 8-Point Output Schema

Every investigation terminates with the exact 8-point schema specified by the competition brief:
1. **The Discovery**: One clear sentence stating the non-obvious forensic reality.
2. **Why It Matters**: 3 to 5 bullet points detailing business & operational implications.
3. **Evidence**: Traceable links across statutory reports, investor decks, and peer filings.
4. **Timeline**: Exact quarters over which the divergence emerged.
5. **Numbers**: Clean arithmetic substantiating the finding.
6. **Counterargument**: Strongest devil's advocate explanation (macro inflation/deflation, category shifts).
7. **Falsification Condition**: Concrete future metrics that would prove the agent wrong.
8. **Evidence Strength**: Rating (`Strong` / `Moderate` / `Weak`) with transparent justification.

---

## 6. Supported Track C Constituents (NIFTY 50 & Peers)

* **NIFTY 50 Track C:** `HINDUNILVR`, `ITC`, `NESTLEIND`, `BRITANNIA`, `TATACONSUM`, `TITAN`, `ASIANPAINT`, `TRENT`
* **Peer Triangulation Benchmarks:** `DABUR`, `MARICO`, `GODREJCP`, `COLPAL`, `DMART`, `VBL`

---

## 7. License

MIT License. Designed for ATMOS 2026.
