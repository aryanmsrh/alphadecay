# **ALPHA-DECAY: Autonomous Financial Forensic Research Agent**

### **ATMOS 2026 · BITS Pilani, Hyderabad Campus**
* **Track:** **Track C — Consumer, FMCG & Retail (NIFTY 50 Universe)**
* **Participant Brief:** **Finding the Next Signal Hackathon**
* **Repository:** [https://github.com/aryanmsrh/alphadecay](https://github.com/aryanmsrh/alphadecay)
* **Lead Author:** Aryan Mishra (`f20261228@hyderabad.bits-pilani.ac.in`)

---

## **1. Executive Summary & The Problem Brief**

Financial data is abundant, but the critical story is rarely contained within a single quarterly earnings release. A company's statutory filings, quarterly profit & loss accounts, annual balance sheets, cash flow statements, and earnings concall transcripts each reveal only fragments of operational change. Most financial AI tools act as superficial news summarizers or chat wrappers that hallucinate arithmetic and exhibit confirmatory bias.

**ALPHA-DECAY** is an autonomous financial research agent designed for high-conviction accounting forensics and non-obvious story discovery in listed Indian Consumer & Retail entities.

### **Core Capabilities:**
1. **Autonomous Investigation:** Given any NIFTY 50 FMCG ticker symbol, the system independently decides what to investigate and harvests public filings from Screener.in and BSE India exchange disclosures without manual prompt tuning.
2. **Deterministic Calculations Only (*Zero LLM Arithmetic*):** Net sales YoY growth, core operating profit margins (EBITDA ex-Other Income), percentage point margin shifts, operating expense growth, distributor debtor days (DSO), inventory holding days (DIO), days payable (DPO), and operating cash flow (CFO) conversion ratios are computed deterministically in pure Python.
3. **Period-Aligned Statutory Grounding:** Annual cash flows are benchmarked strictly against audited annual operating profits, eliminating quarterly extrapolation traps.
4. **Adversarial Cyclic Falsification Loop:** Every candidate anomaly is pitted against an adversarial **Disproving Agent** representing company management and structural sector dynamics. Hypotheses that break down under defense scrutiny are marked as refuted or refined in a second attempt.
5. **Strict Binary Final Verdict:** Every investigation terminates with an unambiguous adjudication:
   * **`HYPOTHESIS PASSED`**: The hypothesis withstood adversarial scrutiny; an evidence-backed operational anomaly was verified.
   * **`HYPOTHESIS FAILED`**: The hypothesis was broken down by defense cross-examination; observed shifts are fully explained by standard commercial cycles.
6. **Mandatory 8-Point Hackathon Deliverable Brief:** Generates all 8 required deliverables in sequence (*The Discovery, Why It Matters, Evidence, Timeline, Numbers, Counterargument, Falsification Condition, Evidence Strength*).
7. **Institutional Packaging:** Emits both an interactive **Pitch-Black Quant Terminal** web interface and an auditable, publication-grade **strict 2-page dark PDF research report**.

---

## **2. System Architecture & The Multi-Agent Pipeline**

```
[Target Listed Ticker Symbol] (e.g. HINDUNILVR, ITC, NESTLEIND, BRITANNIA, TATACONSUM)
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. DATA INGESTION NODE                                                 │
│   • Statutory Statements: Audited Quarterly P&L + Annual Balance Sheet │
│     and Cash Flows scraped from Screener.in                            │
│   • Concall Harvesting: Official BSE PDF concalls parsed via PyPDF     │
│   • Financial Search: Targeted news and trade reports via Tavily API   │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. DETERMINISTIC FINANCIAL MATH SANDBOX (Zero LLM Arithmetic)          │
│   • Core EBITDA (ex-Other Income) = Net Sales - Operating Expenses     │
│   • CFO Conversion Ratio % = (Audited CFO / Audited EBITDA) * 100      │
│   • Working Capital Trio: DSO (Debtors) + DIO (Inventory) - DPO (Pay)  │
│   • Cash Conversion Cycle (CCC): Detects negative supplier financing   │
│   • Ranks top 5 candidate anomalies strictly descending by severity /10│
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. CYCLIC ADVERSARIAL STRESS-TEST (Investigative vs Disproving Agent)  │
│   Loop through ranked anomalies:                                       │
│     ├─ Attempt #1: Investigative Agent forms causal hypothesis         │
│     ├─ Challenge: Disproving Agent attempts to refute using FMCG cycles│
│     ├─ [PASSED] -> Confirmed anomaly, advances                         │
│     └─ [REFUTED] -> Attempt #2: Formulates refined causal hypothesis   │
│           ├─ Challenge: Secondary adversarial cross-examination        │
│           ├─ [PASSED] -> Confirmed anomaly on Attempt #2               │
│           └─ [FAILED] -> Marked HYPOTHESIS FAILED                      │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. ADJUDICATION NODE & SYNTHESIS                                       │
│   • Evaluates surviving anomalies & issues final binary verdict        │
│   • Compiles the official 8-point hackathon research deliverable brief │
│   • Establishes future empirical falsification conditions              │
└────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5. INSTITUTIONAL PACKAGING & EXPORT                                    │
│   • Pitch-Black Quant Terminal Webapp: Space Grotesk / JetBrains Mono  │
│   • 2-Page Institutional Research Note: ReportLab vector dark canvas   │
│   • Dual-Axis Trajectory Chart: Matplotlib sales vs margin trajectory  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## **3. Beginner-Friendly Quick Start Guide**

Follow these step-by-step instructions to get the project running on your local machine in under 5 minutes.

### **Step 1: Prerequisites & System Requirements**
Ensure you have the following installed on your system:
* **Python 3.10, 3.11, or 3.12** (`python3 --version` or `python --version`)
* **Git** (`git --version`)
* *(Optional)* **Ollama** if you wish to run LLM reasoning locally using `deepseek-r1:7b` without cloud LLM API keys.

---

### **Step 2: Clone the Repository & Enter Workspace**
Open your terminal (Terminal on macOS/Linux or PowerShell on Windows) and run:
```bash
git clone https://github.com/aryanmsrh/alphadecay.git
cd alphadecay
```

---

### **Step 3: Create & Activate a Python Virtual Environment**
Creating an isolated virtual environment ensures clean package management:

* **On Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

* **On Windows (Command Prompt / PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```

Your terminal prompt will now display `(.venv)` at the beginning of the line.

---

### **Step 4: Install Dependencies**
Install all required libraries with a single command:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
*Key packages installed include `flask`, `reportlab`, `matplotlib`, `beautifulsoup4`, `pypdf`, `httpx`, `requests`, and `pymupdf`.*

---

### **Step 5: Configure Environment Variables (`.env`)**
Copy the example environment configuration:
```bash
cp .env.example .env
```
Open `.env` in any text editor (VS Code, Nano, Notepad) and enter your API keys:
```ini
# Google Gemini API Key (Get a free key from https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# Default Gemini model
GEMINI_MODEL=gemini-3.5-flash-lite

# Optional: Tavily Search API key (from https://tavily.com/)
TAVILY_API_KEY=your_tavily_key_here

# Offline LLM toggle (Set to true if routing reasoning locally via Ollama without cloud keys)
USE_OFFLINE_MODE=false
```
> **Note for Beginners:** A free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/) is all that is required to run online investigations. If you do not have a Tavily key, the system automatically falls back to statutory filings.

---

### **Step 6: Launch the Pitch-Black Quant Web Terminal**
Start the local web application:
```bash
python run_web.py --port 5000
```
You will see output indicating the server has booted:
```
========================================================================
  ALPHA-DECAY // QUANT FORENSIC WORKSTATION
  Serving on: http://127.0.0.1:5000
  Mode:       Production WSGI / Flask Dev Server
========================================================================
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

#### **What You Can Do in the Web App:**
1. **Home / Dashboard (`/`):** View recent completed investigations, their binary verdicts (`HYPOTHESIS PASSED` / `HYPOTHESIS FAILED`), and their core discoveries.
2. **New Investigation (`/investigations/new`):** Select pre-configured Track C FMCG stocks (`HINDUNILVR`, `ITC`, `NESTLEIND`, `BRITANNIA`, `TATACONSUM`, `DABUR`, `MARICO`) or enter any custom NSE ticker symbol, and click **Launch Autonomous Audit**.
3. **Investigation Detail Workspace (`/investigation/<run_id>`):**
   * **The Discovery Banner:** Clear verdict tag and evidence strength rating.
   * **The 8-Point Hackathon Brief Card:** All 8 required elements numbered in exact order.
   * **Deterministic Financial Math Cards:** Inspect the exact audited formulas and arithmetic substitution steps.
   * **Top 5 Tested Anomalies Table:** Ranked by severity `/10` with math detail.
   * **Cyclic Agent Audit Trail:** Review which hypotheses passed and which were refuted by the defense agent.
   * **Quarterly Sales vs Margin Chart:** Interactive visual trajectory.
   * **1-Click PDF Download:** Download the publication-grade 2-page research PDF.

---

### **Step 7: Run Autonomous Investigations via CLI**
You can also run complete investigations directly from the command line without launching the browser.

```bash
# Run investigation on Hindustan Unilever with 2-page PDF export
python main.py --ticker HINDUNILVR --export-pdf

# Run investigation on ITC Limited
python main.py --ticker ITC --export-pdf

# Run investigation on Nestle India
python main.py --ticker NESTLEIND --export-pdf

# Run investigation on Britannia Industries
python main.py --ticker BRITANNIA --export-pdf

# Run investigation on Tata Consumer Products
python main.py --ticker TATACONSUM --export-pdf
```
Each run automatically saves all JSON metrics, charts, and the 2-page PDF into the `data/runs/<run_id>/` folder and registers the run on the web dashboard.

---

### **Step 8: Run Local LLM Reasoning Mode (Ollama Fallback)**
If you wish to execute LLM reasoning locally without cloud API keys:

1. Install and start [Ollama](https://ollama.ai/):
   ```bash
   ollama pull deepseek-r1:7b
   ```
2. Run the investigation with the `--offline` flag:
   ```bash
   python main.py --ticker HINDUNILVR --offline --export-pdf
   ```
> **Technical Note on Network Connectivity:** The `--offline` flag routes all LLM reasoning tasks locally to your Ollama model (`deepseek-r1:7b`). Data harvesters (Screener.in statutory statements and BSE exchange filings) still require network access to fetch public corporate disclosures unless cached.

---

## **4. The Official 8-Point Hackathon Brief Deliverables**

Every investigation synthesizes the exact 8 deliverables mandated by the ATMOS 2026 Participant Brief:

1. **The Discovery:** One unambiguous sentence identifying the non-obvious operational or accounting divergence.
2. **Why It Matters:** 3 to 5 analytical bullets explaining the strategic, liquidity, and operational significance.
3. **Evidence:** Multiple independent statutory sources with direct, clickable links to SEBI filings and BSE concall transcripts.
4. **Timeline:** Chronological development of the shift across trailing quarters and fiscal years.
5. **Numbers:** The exact deterministic calculations and metrics required to substantiate the finding.
6. **Counterargument:** The strongest alternative explanation or benign sector justification tested by the Disproving Agent.
7. **Falsification Condition:** The explicit future empirical disclosure that would cause the system to reconsider its conclusion.
8. **Evidence Strength:** A rating of **Strong**, **Moderate**, or **Weak** accompanied by audit justification.

---

## **5. Deterministic Forensic Financial Math Sandbox**

To protect against arithmetic hallucination, all financial metrics are computed in pure Python using audited SEBI LODR disclosures:

| Metric | Exact Formula | Period Alignment | Forensic Diagnostic Insight |
| :--- | :--- | :--- | :--- |
| **CFO-to-EBITDA Conversion** | `(Audited_CFO / Audited_Operating_Profit) * 100` | Audited Annual to Annual | Primary earnings quality test. A drop below 80% indicates profits on paper failing to convert to physical bank cash. |
| **Core EBITDA (ex-Other Inc)**| `Net_Sales - Total_Operating_Expenses` | Quarterly & Annual | Isolates pure operational manufacturing profit, stripping out non-operating treasury gains. |
| **Operating Margin Spread** | `Current_OPM - Prior_YoY_OPM` | Quarterly YoY ($t$ vs $t-4$) | Measures operating cost leverage across identical seasonal cycles in percentage points (pp) and basis points (bps). |
| **Debtor Days (DSO)** | `(Trade_Receivables / Audited_Sales) * 365` | Audited Annual | Measures distributor credit discipline. Rising DSO indicates trade partners delaying payments. |
| **Inventory Days (DIO)** | `(Inventories / Audited_Sales) * 365` | Audited Annual | Average duration finished goods sit in warehouses before being sold. Expansion indicates channel inventory buildup. |
| **Days Payable (DPO)** | `(Trade_Payables / Audited_Sales) * 365` | Audited Annual | Average days taken to pay raw material suppliers. Measures trade credit funding. |
| **Cash Conversion Cycle (CCC)**| `DSO + DIO - DPO` | Audited Annual | Net working capital cycle. A deeply negative cycle (e.g. -89 days) proves vendors are funding operational inventory for free. |

---

## **6. Project Directory Structure**

```
alphadecay/
├── ALPHA_DECAY_PROJECT_OVERVIEW.pdf # 2-Page Technical Architecture Whitepaper PDF
├── generate_overview_pdf.py         # Script to compile the project overview PDF
├── main.py                          # CLI runner for autonomous investigations
├── run_web.py                       # Boots the pitch-black quant terminal web server
├── config.py                        # Centralized configuration, models & thresholds
├── requirements.txt                 # Pinned project dependencies
├── .env.example                     # Template environment configuration
│
├── agent/                           # Multi-Agent Adversarial System
│   ├── cyclic_pipeline.py           # 2-attempt cyclic loop (Investigative vs Disproving)
│   ├── graph.py                     # LangGraph StateGraph pipeline definition
│   ├── nodes.py                     # Agent execution nodes
│   └── state.py                     # State dataclasses and typing definitions
│
├── engine/                          # Deterministic Math & Forensic Analytics
│   ├── analytics.py                 # Pure Python EBITDA, CFO conversion & CCC engine
│   ├── forensics.py                 # Anomaly scoring heuristics & triage ranking
│   ├── investigator.py              # Investigation orchestration wrapper
│   └── llm.py                       # Dual-provider LLM client (Gemini + Ollama)
│
├── ingestion/                       # Statutory Data Harvesters
│   ├── screener.py                  # Scrapes quarterly P&L, balance sheets & cash flows
│   ├── concall_harvester.py         # Downloads BSE concall PDFs & extracts dialogue via PyPDF
│   └── web_search.py                # Targeted financial search via Tavily API
│
├── exporter/                        # Institutional Packaging
│   ├── pdf.py                       # ReportLab strict 2-page dark research report generator
│   └── chart.py                     # Matplotlib dual-axis sales vs margin chart generator
│
├── webapp/                          # Pitch-Black Quant Terminal
│   ├── app.py                       # Flask application routes and API endpoints
│   ├── run_store.py                 # Transactional atomic JSON run store
│   ├── static/css/theme.css         # Modern quant styles (#070709, micro-borders, shadows)
│   ├── static/fonts/                # TrueType fonts (Space Grotesk, Plus Jakarta Sans, JetBrains Mono)
│   └── templates/                   # Clean HTML templates (Dashboard, Detail, Brief card)
│
└── data/                            # Run Artifacts & Storage
    └── runs/                        # Run directories containing report.pdf, chart.png & .json
```

---

## **7. Common Troubleshooting & FAQs for Beginners**

#### **Q1: The web server reports `Address already in use` on port 5000.**
* **Fix:** Another process is occupying port 5000. Start the server on a different port:
  ```bash
  python run_web.py --port 5001
  ```
  Then open `http://127.0.0.1:5001` in your browser.

#### **Q2: `GEMINI_API_KEY is not set` error when running main.py.**
* **Fix:** Ensure you have created a `.env` file in the project root directory and added your key:
  ```ini
  GEMINI_API_KEY=AIzaSy...
  ```
  Alternatively, run with the `--offline` flag to use local Ollama without any cloud API key.

#### **Q3: Where can I view the generated 2-page PDF?**
* **Fix:** After running an investigation on `HINDUNILVR`, the PDF is saved to:
  ```
  data/runs/<run_id>/report.pdf
  ```
  You can also download it directly from the web dashboard by clicking the **"Download 2-Page Institutional PDF"** button.

#### **Q4: How do I test the system on other FMCG companies?**
* **Fix:** The system works out-of-the-box for any listed Indian company on Screener.in:
  ```bash
  python main.py --ticker NESTLEIND --export-pdf
  python main.py --ticker BRITANNIA --export-pdf
  python main.py --ticker TATACONSUM --export-pdf
  python main.py --ticker DABUR --export-pdf
  ```

---

## **8. Intellectual Property, Anti-Plagiarism & License**

Developed for the **Finding the Next Signal** Autonomous Financial Research Hackathon at **ATMOS 2026, BITS Pilani Hyderabad Campus** by **Aryan Mishra**.

This project is licensed under the custom **ALPHA-DECAY Source-Available Attribution & Non-Commercial Research License** (see full terms in [`LICENSE`](LICENSE)).

### **Key License Restrictions:**
- **Mandatory Attribution:** Any permitted reference, inspection, educational study, or demonstration must prominently credit **Aryan Mishra** as the original author and architect and link to the upstream repository ([`github.com/aryanmsrh/alphadecay`](https://github.com/aryanmsrh/alphadecay)).
- **Strict Anti-Plagiarism & Competition Ban:** Under no circumstances may this software, its code, its prompts, its mathematical sandbox, or derivative works be copied, modified, rebranded, or submitted to any hackathon, competition, contest, evaluation, or grading by any third party without prior express written consent.
- **Non-Commercial Restriction:** The software may not be monetized, sold, or incorporated into commercial financial advisory or trading tools.
