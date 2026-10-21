# **AlphaDecay: Autonomous Financial Research Agent**

### **ATMOS 2026 · BITS Pilani, Hyderabad Campus**
* **Track:** **Track C — Consumer, FMCG & Retail (NIFTY 50 Universe)**
* **Participant Brief:** **Finding the Next Signal Hackathon**
* **Repository:** [https://github.com/aryanmsrh/alphadecay](https://github.com/aryanmsrh/alphadecay)
* **Lead Author:** Aryan Mishra (`f20261228@hyderabad.bits-pilani.ac.in`)

---

## **1. Executive Summary & The Problem Brief**

Financial statements rarely reveal critical risks in a single headline figure. A company's quarterly profit & loss disclosures, annual balance sheets, statutory cash flow statements, and earnings call transcripts each present partial fragments of operational truth. Conventional LLM wrappers act as superficial news summarizers and frequently hallucinate basic arithmetic when calculating multi-year ratios.

**AlphaDecay** is an autonomous financial research agent engineered to detect, cross-examine, and substantiate non-obvious operational shifts and accounting divergences across listed Indian FMCG enterprises.

### **Core Capabilities:**
1. **Autonomous Investigation:** Given any NIFTY 50 FMCG ticker symbol, AlphaDecay autonomously downloads audited public filings from Screener.in and BSE India without manual prompting.
2. **Pure Python Math Sandbox (*Zero AI Math Mistakes*):** Revenue growth YoY, core EBITDA (ex-Other Income), operating margins, debtor days (DSO), inventory days (DIO), days payable (DPO), and cash conversion cycles (CCC) are calculated deterministically in pure Python.
3. **Aligned Reporting Periods:** Annual cash flows are benchmarked strictly against audited annual operating profits, eliminating quarterly mismatch errors.
4. **Upstream Peer Triangulation:** Automatically benchmarks target companies against direct sector rivals (e.g., HUL vs. Dabur and Marico) directly from statutory disclosures.
5. **Adversarial Forensic Arena:** Findings are challenged in an adversarial arena between a cynical **Attacker** (Prosecution) exposing downplayed risks and a rational **Defender** (Corporate Defense Counsel) presenting operational mechanics and setting concrete empirical falsification conditions.
6. **Dual Runtime Engine:** Supports both high-speed cloud reasoning via **Google Gemini (`gemini-3.8-flash`)** (~14s execution) and offline local reasoning via **Ollama (`deepseek-r1:7b`)** (~86s execution) with hot-swapping from the web dashboard.
7. **Strict 8-Point Hackathon Deliverables:** Emits the required 8-point research brief (*The Discovery, Why It Matters, Evidence, Timeline, Numbers, Attacker Case, Defender Counterargument & Falsification Condition, Strength Assessment*).
8. **Interactive Quant Terminal & Publication PDF:** Renders a pitch-black web workstation (`web/app.py`) and generates a vector dark-canvas research PDF (`report.pdf`).

---

## **2. System Architecture & The Investigation Pipeline**

```
[Target Listed Ticker Symbol] (e.g. HINDUNILVR, ITC, NESTLEIND, BRITANNIA, TATACONSUM)
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. DATA INGESTION ENGINE (ingest/)                                     │
│   • Statutory Statements: Audited Quarterly P&L, Annual Balance Sheet, │
│     and Cash Flows harvested from Screener.in                          │
│   • Concall Harvesting: Official BSE PDF earnings calls parsed via     │
│     PyPDF to extract verbatim management dialogue                      │
│   • Targeted Web Search: Triangulated disclosure search via Tavily     │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. DETERMINISTIC PYTHON MATH SANDBOX (analytics/analytics.py)          │
│   • Core EBITDA (ex-Other Income) = Net Sales - Operating Expenses     │
│   • CFO Conversion % = (Audited Annual CFO / Audited EBITDA) * 100     │
│   • Working Capital Trio: DSO (Debtors) + DIO (Inventory) - DPO (Pay)  │
│   • Cash Conversion Cycle (CCC): Tracks supplier-funded working capital│
│   • Ranks candidate anomalies descending by severity (/10)             │
│   • Rips out dead legacy courtroom strings for high-throughput memory  │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. UPSTREAM SECTOR PEER TRIANGULATION (agent/finder.py)                │
│   • Resolves peer pairs via PEER_MAPPING (e.g. HUL -> DABUR, MARICO)   │
│   • Deterministically calculates matching conversion & margin ratios   │
│   • Injects audited peer spread benchmarks into anomaly numbers        │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. ADVERSARIAL FORENSICS ARENA (agent/attacker.py & defender.py)       │
│   • Attacker (Prosecution): Cross-examines divergences and peer        │
│     spreads; details aggressive channel pressure or working capital    │
│   • Defender (Corporate Counsel): Refutes malfeasance; explains        │
│     distribution buffering, dark-store stocking, or commodity lags;    │
│     frames a hard future empirical turnaround falsification threshold  │
│   • Mid-run tools: triangulate_peer_metric, search_concall_transcript  │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5. 8-POINT SCHEMA SYNTHESIS & REPORT GENERATION (agent/pipeline.py)    │
│   • Compiles strict 8-point JSON institutional brief                   │
│   • Generates publication-grade dark canvas vector PDF (export/pdf.py) │
│   • Stores atomic run artifact in data/runs/{run_id}/run.json          │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 6. DUAL RUNTIME ENGINE (agent/llm.py)                                  │
│   • Google Gemini Cloud (gemini-3.8-flash) [Default: ~14s]             │
│   • Local Ollama Engine (deepseek-r1:7b) [Offline: ~86s]               │
│   • Dynamic runtime switching via Web UI Dropdown on /new              │
│   • Resilient automatic failover to Ollama on network or API limits    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## **3. Beginner-Friendly Quick Start Guide**

### **Step 1: Prerequisites & System Requirements**
* **Python 3.10, 3.11, or 3.12** (`python3 --version`)
* **Git** (`git --version`)
* *(Optional)* **Ollama** if you wish to run offline reasoning locally with `deepseek-r1:7b`.

---

### **Step 2: Clone the Repository & Enter Workspace**
```bash
git clone https://github.com/aryanmsrh/alphadecay.git
cd alphadecay
```

---

### **Step 3: Create & Activate a Python Virtual Environment**
* **On Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
* **On Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```

---

### **Step 4: Install Dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### **Step 5: Configure Environment Variables**
Copy the example environment configuration:
```bash
cp .env.example .env
```
Edit `.env` to configure your keys:
```env
# Google Gemini Cloud (Recommended for ~14s high-speed inference)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Local Ollama Engine (For 100% offline local inference)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:7b

# Default Provider: 'gemini' or 'ollama'
DEFAULT_PROVIDER=gemini

# Optional: Tavily Search Key for web triangulation
TAVILY_API_KEY=your_tavily_key_here
```

> **Note on Local Ollama Mode:** If using the local engine, ensure Ollama is installed and run:
> ```bash
> ollama pull deepseek-r1:7b
> ```

---

### **Step 6: Launch the Web Dashboard**
Start the web application:
```bash
python3 web/app.py --port 5000
```
Open your browser to:
```
http://localhost:5000
```
* **New Investigation (`/new`):** Select your target FMCG company (e.g. `HINDUNILVR`, `ITC`, `NESTLEIND`, `BRITANNIA`, `TATACONSUM`), pick your **Runtime Engine** (`Google Gemini Cloud` or `Local DeepSeek-R1`), and initiate the analysis.
* **Investigation View (`/investigation/<id>`):** Inspect live progress, multi-quarter tables, peer benchmark cards, Attacker vs. Defender arguments, and download the generated `report.pdf`.

---

### **Step 7: (Alternative) Run via CLI**
To run an investigation directly from your terminal:
```bash
python3 script.py --ticker HINDUNILVR --anomalies 1
```

---

## **4. Inference Cost & Token Economics (Cloud vs. Local)**

Each forensic investigation runs a 5-step adversarial pipeline (Attacker Triangulation & Thesis, Defender Verification & Falsification, and 8-Point Synthesis) injecting financial ratios, statutory concall extracts, and web search evidence. 

Below is the observed real-world cost and token breakdown per complete company investigation:

| Model | Model Tier | Observed Real-World Cost (INR) | Official Token Rates (Input / Output per 1M) | Hidden Reasoning Overhead | Est. Investigations with ₹500 Balance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Local deepseek-r1:7b`** | Local / Offline | **₹0.00** *(100% Free)* | Free (Local GPU / CPU via Ollama) | Integrated locally | **Unlimited** |
| **`gemini-3.5-flash-lite`**| Cloud Fast-Lite | **~₹0.50 – ₹1.00** | $0.075 / $0.30 | None | **~500 – 1,000 runs** |
| **`gemini-3.8-flash`** *(Default)* | Cloud Fast | **~₹2.00 – ₹4.00** | $0.10 / $0.40 | None | **~125 – 250 runs** |
| **`gemini-4-argon`** | Experimental Reasoning | **~₹8.00 – ₹10.00** | $0.50 / $2.00 | ~16,000+ thinking tokens | **~50 – 60 runs** |

### **Why Do the Costs Vary?**
1. **Context Window & Real Dossier Size:**
   * A full investigation loads audited balance sheet ratios, multi-quarter tables, target BSE concall transcript sections, and live Tavily search triangulations. Real-world investigations consume **~25,000 to 45,000 input tokens** across the 5 sequential adversarial turns.
2. **Reasoning / Thinking Tokens (`gemini-4-argon`):**
   * Reasoning models (like `gemini-4-argon` or Gemini Thinking models) produce thousands of invisible reasoning tokens (`"thought": true`) before emitting their JSON payloads. In a multi-turn adversarial loop, thinking overhead can exceed **16,000 to 20,000 tokens**, which Google bills at the premium output rate ($2.00 / 1M). This drives real-world costs to **~₹8.00 per run**.
3. **Recommended Production Balance:**
   * **`gemini-3.8-flash`** strikes the optimal balance for quantitative financial auditability—offering ~14s response times, clean structured outputs, and costing roughly **₹2 to ₹4 per investigation**, giving you 125+ full runs on a ₹500 credit budget.

---

## **5. The Mandatory 8-Point Hackathon Deliverables**

Every investigation synthesizes an 8-point institutional research brief meeting all hackathon requirements:

| # | Deliverable | Field in Schema | Description |
| :---: | :--- | :--- | :--- |
| **1** | **The Discovery** | `discovery` / `the_discovery` | Exactly one crisp sentence stating the core quantitative divergence with audited numbers. |
| **2** | **Why It Matters** | `why_it_matters` | 3 to 5 sharp bullet points detailing the commercial impact, capital allocation consequences, and peer competitive implications. |
| **3** | **Evidence** | `evidence` | Verifiable statutory citations and direct clickable links to official BSE concall filings and statements. |
| **4** | **Timeline** | `timeline` | Chronological multi-quarter narrative tracing the historical evolution of the metric across reporting periods. |
| **5** | **Numbers** | `numbers` | Deterministic calculated figures: CFO, EBITDA, conversion percentages, peer spreads, and quarterly momentum. |
| **6** | **Attacker Thesis** | `attacker.verdict` | The prosecution case detailing what operational or channel friction management is downplaying behind the audited numbers. |
| **7** | **Defender Counterargument & Falsification** | `defender.counterargument` & `defender.falsification_condition` | The operational defense (inventory buffering, seasonal cycles, platform growth) accompanied by an empirical falsification metric threshold. |
| **8** | **Strength Assessment** | `strength` | Calibrated conviction ratings and audit rationale for both the prosecution and defense cases. |

---

## **6. Codebase Directory Structure**

```
alphadecay/
├── agent/
│   ├── attacker.py        # Prosecutorial adversarial forensic agent
│   ├── defender.py        # Corporate defense counsel with falsification criteria
│   ├── finder.py          # Dossier aggregator, concall matcher & mid-run tool manifest
│   ├── llm.py             # Dual-engine transport (Gemini Cloud + Ollama DeepSeek-R1)
│   └── pipeline.py        # End-to-end investigation orchestration & 8-point brief synthesis
├── analytics/
│   ├── analytics.py       # Deterministic math sandbox (Sales YoY, OPM, CFO/EBITDA, DIO, DSO, CCC)
│   └── tools.py           # Parsing utilities, period matchers, and safe floats
├── config.py              # Environment constants, peer mappings, and runtime defaults
├── data/
│   └── runs/              # Investigation output directories ({run_id}/run.json & report.pdf)
├── export/
│   └── pdf.py             # ReportLab high-precision dark-canvas vector PDF generator
├── ingest/
│   ├── concall.py         # BSE earnings call harvester & PyPDF text extractor
│   ├── screener.py        # Screener.in statutory statements scraper & caching layer
│   └── search.py          # Tavily targeted financial search integration
├── web/
│   ├── app.py             # Flask web server & streaming event dispatcher
│   ├── static/            # Pitch-black CSS theme, typography (Space Grotesk, JetBrains Mono)
│   └── templates/         # Clean dark-mode Jinja2 templates (overview, new, history, detail)
├── .env.example           # Fully documented dual-runtime environment configuration
├── requirements.txt       # Clean, pinned Python dependencies
└── script.py              # Command-line investigation runner
```

---

## **7. Verification & Mathematical Integrity**

* **Zero Arithmetic Hallucination:** All financial indicators are computed deterministically in Python before any LLM is invoked.
* **SEBI LODR Auditability:** Findings cite official BSE statutory filings and earnings concall transcripts.
* **Resilient Dual-Engine Design:** If cloud API quotas or network disruptions occur, the pipeline automatically falls back to local Ollama inference without pipeline crashes.
