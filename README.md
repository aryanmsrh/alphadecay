# AlphaDecay: Autonomous Financial Research Agent

> **ATMOS 2026 · BITS Pilani Hyderabad Campus**  
> **Track C — Consumer, FMCG & Retail (NIFTY 50 Universe)**  
> **Participant Brief: Finding the Next Signal Hackathon**  
> **Author:** Aryan Mishra (`f20261228@hyderabad.bits-pilani.ac.in`)  
> **Repository:** [github.com/aryanmsrh/alphadecay](https://github.com/aryanmsrh/alphadecay)

---

![AlphaDecay Investigation Terminal](assets/investigation_preview.png)

---

## What is AlphaDecay?

**AlphaDecay** is an autonomous quantitative forensic research agent engineered to detect, cross-examine, and substantiate non-obvious operational shifts and accounting divergences across listed Indian FMCG enterprises.

* **Zero Arithmetic Hallucination:** Computes Sales YoY, Core EBITDA (ex-Other Income), Operating Margins, Working Capital Trio (DIO, DSO, DPO), and Cash Conversion Cycles (CCC) deterministically in pure Python before invoking any LLM.
* **Statutory Filings Ingestion:** Autonomously fetches audited quarterly and annual statements from Screener.in and parses official BSE earnings concall transcripts via PyPDF.
* **Adversarial Forensic Arena:** Findings are contested between a cynical **Attacker** (exposing channel friction and accounting risks) and a rational **Defender** (offering operational context and setting a hard empirical falsification condition).
* **Dual Runtime Engine:** Supports both high-speed cloud reasoning via **Google Gemini (`gemini-3.8-flash`)** and 100% offline local reasoning via **Ollama (`deepseek-r1:7b`)**.
* **Publication PDF Export:** Generates an institutional-grade dark-canvas vector PDF research report for every investigation.

---

## Quick Start (Run Locally in 2 Minutes)

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/aryanmsrh/alphadecay.git
cd alphadecay

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
```
Edit `.env` with your keys:
```env
# Primary Cloud Engine (Gemini)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Optional: Local Offline Engine (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:7b

# Optional: Tavily Search Key for live BSE/web triangulation
TAVILY_API_KEY=your_tavily_key_here
```

### 3. Launch the Web Application
```bash
python3 web/app.py
```
Open your browser to: **`http://localhost:5000`**

![AlphaDecay Web Dashboard](assets/dashboard_preview.png)

* **Initiate Investigation (`/new`):** Select a company (e.g. `ITC`, `HINDUNILVR`, `NESTLEIND`), choose your reasoning engine, and launch the audit.
* **Live Dossier (`/investigation/<id>`):** View real-time adversarial logs, multi-quarter balance sheet matrices, peer benchmark cards, and download the vector PDF report.

*(Alternative CLI runner: `python3 script.py --ticker ITC --anomalies 1`)*

---

## Benchmark Sample Run: ITC Investigation (`dbb4b9c4`)

A complete institutional forensic investigation is committed in the repository at [`data/runs/dbb4b9c4/`](data/runs/dbb4b9c4/):

* **Model Used:** **`gemini-4-argon`** — Google's highest tier of intelligence and reasoning.
* **Target Company:** ITC Ltd (`ITC`)
* **Primary Discovery:** Detected a severe **459 bps YoY operating profit margin contraction** (and a **1,189 bps sequential collapse** from the March peak of 39.00%), driven by an 11.08% revenue decline outpacing operating expense reductions.
* **Artifacts:**
  * Complete JSON Telemetry & Adversarial Log: [`data/runs/dbb4b9c4/run.json`](data/runs/dbb4b9c4/run.json)
  * Vector Dark-Canvas Research PDF: [`data/runs/dbb4b9c4/report.pdf`](data/runs/dbb4b9c4/report.pdf)

---

## Inference Cost & Token Economics

Each investigation executes a 5-step adversarial triangulation (Attacker Triangulation & Verdict, Defender Verification & Falsification, and 8-Point Synthesis).

| Model | Runtime Tier | Observed Real-World Cost (INR) | Official Token Rates (Input / Output per 1M) | Reasoning / Thinking Overhead | Est. Runs with ₹500 Balance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Local deepseek-r1:7b`** | Local / Offline | **₹0.00** *(100% Free)* | Free (Local GPU / CPU via Ollama) | Integrated locally | **Unlimited** |
| **`gemini-3.5-flash-lite`**| Cloud Fast-Lite | **~₹0.50 – ₹1.00** | $0.075 / $0.30 | None | **~500 – 1,000 runs** |
| **`gemini-3.8-flash`** *(Default)* | Cloud Fast | **~₹2.00 – ₹4.00** | $0.10 / $0.40 | None | **~125 – 250 runs** |
| **`gemini-4-argon`** | Flagship Reasoning | **~₹8.00 – ₹10.00** | $0.50 / $2.00 | ~16,000+ thinking tokens | **~50 – 60 runs** |

* **Why Argon costs ~₹8/run:** Google's `gemini-4-argon` produces extensive internal reasoning tokens (`"thought": true`). Over the 5-turn adversarial loop, this produces over 16,000 thinking tokens billed at Google's premium output rate ($2.00 / 1M).
* **Recommended Pick:** `gemini-3.8-flash` offers the optimal balance of speed (~14s), high-precision financial schema compliance, and low cost (~₹2 to ₹4 per investigation).

---

## 8-Point Hackathon Deliverables

Every investigation automatically synthesizes the mandatory 8-point institutional research brief:

| # | Deliverable | Field in Schema | Description |
| :---: | :--- | :--- | :--- |
| **1** | **The Discovery** | `discovery` | One crisp sentence stating the core quantitative divergence with audited figures. |
| **2** | **Why It Matters** | `why_it_matters` | 3 to 5 bullet points on commercial impact, capital allocation, and peer spreads. |
| **3** | **Evidence** | `evidence` | Verifiable statutory citations and direct links to BSE filings & concalls. |
| **4** | **Timeline** | `timeline` | Chronological multi-quarter narrative tracing the historical metric evolution. |
| **5** | **Numbers** | `numbers` | Deterministic figures: CFO, EBITDA, conversion %, peer spreads, and momentum. |
| **6** | **Attacker Thesis** | `attacker.verdict` | Prosecution case detailing downplayed operational risks or channel friction. |
| **7** | **Defender Counterargument & Falsification** | `defender.counterargument` & `defender.falsification_condition` | Operational defense accompanied by a measurable future empirical falsification threshold. |
| **8** | **Strength Assessment** | `strength` | Calibrated conviction ratings and audit rationale for prosecution and defense. |

---

## License

MIT License. See [LICENSE](LICENSE) for details.
