# AlphaDecay: Production-Grade Forensic Financial Intelligence Engine

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask%203.1-000000.svg)](https://flask.palletsprojects.com/)
[![Orchestrator: LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Primary LLM: Gemini](https://img.shields.io/badge/Primary%20LLM-Gemini%20Flash-4285F4.svg)](https://ai.google.dev/)
[![Fallback LLM: Ollama DeepSeek R1](https://img.shields.io/badge/Fallback%20LLM-Ollama%20DeepSeek--R1--7B-black.svg)](https://ollama.com/)
[![Tests: Pytest](https://img.shields.io/badge/Tests-70%20Passing-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Track C: Consumer, FMCG & Retail**  
**Autonomous Forensic Financial Research Engine & Interactive Terminal**  
**Lead:** Aryan Mishra (`f20261228@hyderabad.bits-pilani.ac.in`)

---

## 1. Overview & Web Application

**AlphaDecay** transforms financial analysis from passive summarization into an active, evidence-driven forensic courtroom.

The application features:
- **Interactive Financial Forensics Dashboard:** A modern dark-theme terminal interface (`#05070A`, `#0D1117`, `#121922`) built on Flask, Jinja2, Chart.js, and SQLite.
- **Zero LLM Arithmetic:** Accounting identities, growth metrics, period alignments, and canonical Beneish ratios are calculated deterministically in audited Python code.
- **Centralized Model Provider:** Gemini First with thinking level `HIGH`. Resilient, automatic fallback to local Ollama (`deepseek-r1:7b`) on transient or permanent failures.
- **Observable Execution Pipeline:** 9 distinct canonical execution phases monitored in real-time via Server-Sent Events (SSE) and polling fallback.
- **Durable Run Storage:** SQLite persistence for all runs, events, metrics, and structured evidence.
- **Artifact Isolation:** Each run generates an isolated directory (`data/runs/<run_id>/`) with publication-grade PDF notes, structured state JSON bundles, source snapshots, and forensic charts.

---

## 2. High-Level Architecture & Separation of Concerns

```
                                [User Browser / CLI]
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
            [Flask Web UI]                            [CLI Entry Point]
         `GET /`, `POST /api/...`                       `python main.py`
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         ▼
                        [Investigation Execution Service]
                          `webapp/services.py` (Worker)
                                         │
       ┌──────────────────┬──────────────┴────────────────┬──────────────────┐
       ▼                  ▼                               ▼                  ▼
[1. Ingestion]   [2. Math Sandbox]              [3. LangGraph App]   [4. Run Store]
 Screener / BSE    Canonical DSRI,                Courtroom Cycle,      SQLite DB,
 Concall Scraper   Residual, Wedge               Adversarial Review    Events & Runs
       │                  │                               │                  │
       └──────────────────┴──────────────┬────────────────┴──────────────────┘
                                         ▼
                    [5. Artifact & Report Generators]
                     2-Page Dark PDF, High-Res Chart,
                     Run Manifest & State JSON Bundle
```

---

## 3. Quickstart & Launching the Web Application

### Prerequisites
- Linux / WSL2 Ubuntu with Python 3.10+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Local Ollama running with `deepseek-r1:7b` (for offline/fallback testing)

### Step 1: Clone and Set Up Environment
```bash
git clone https://github.com/aryanmsrh/alphadecay.git
cd alphadecay

# Create clean virtual environment using uv
uv venv

# Activate virtualenv
source .venv/bin/activate

# Install dependencies (Flask, ReportLab, LangGraph, etc.)
uv pip install -r requirements.txt
```

### Step 2: Configure Credentials (`.env`)
```bash
cp .env.example .env
```
Key configuration settings in `.env`:
```ini
# Google Gemini (Primary Model)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_THINKING_LEVEL=HIGH

# Local Ollama (Fallback Model)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_FALLBACK_MODEL=deepseek-r1:7b

# Tavily AI Search (Web Provenance)
TAVILY_API_KEY=your_tavily_api_key_here

# Operational Toggles
USE_OFFLINE_MODE=False
INVESTIGATION_CUTOFF_DATE=
```

### Step 3: Start the Web Dashboard
```bash
python run_web.py
```
By default, the server binds to `127.0.0.1:5000`:
```text
========================================================================
  ALPHA-DECAY // FINANCIAL FORENSIC INTELLIGENCE TERMINAL v2.0
========================================================================
  • Web Dashboard URL:     http://127.0.0.1:5000/
  • Primary Model:         gemini-3.5-flash-lite (Configured)
  • Local Fallback Model:  deepseek-r1:7b (http://localhost:11434)
  • Execution Mode:        ONLINE (Gemini First)
  • Security Boundary:     Binding strictly to 127.0.0.1
  • Persistent DB:         /path/to/alphadecay/data/alphadecay.db
========================================================================
  Press Ctrl+C to terminate the local server.
```
Open **`http://127.0.0.1:5000`** in your browser to explore the dashboard.

---

## 4. Running Investigations

### Option A: Via the Web Terminal
1. Navigate to `http://127.0.0.1:5000/investigations/new`.
2. Select a pre-configured Track C company (e.g. `HINDUNILVR`, `ITC`, `NESTLEIND`, `BRITANNIA`, `TATACONSUM`) or enter any listed ticker.
3. (Optional) Set a point-in-time cutoff date (`YYYY-MM-DD`) to simulate historical knowledge.
4. Click **Launch Autonomous Audit**.
5. Watch the 9-stage pipeline execute in real-time, inspect interactive charts, review hypotheses, and download artifacts.

### Option B: Via Command Line Interface (CLI)
```bash
# Investigate Nestle India (with publication-grade 2-page PDF export)
python main.py --ticker NESTLEIND --export-pdf

# Investigate Hindustan Unilever with reproducible cutoff date
python main.py --ticker HINDUNILVR --export-pdf --cutoff-date 2025-03-31

# Force local offline mode using Ollama
python main.py --ticker ITC --offline
```
*Note: Investigations run via the CLI automatically persist into the SQLite database and appear on the web dashboard.*

---

## 5. Web Application Features & Tabbed Workspace

The investigation detail workspace (`/investigations/<run_id>`) provides six dedicated analysis tabs:

- **Tab A: Overview & Verdict:** Displays the primary quantitative finding, adjudication verdict (`SUPPORTED`, `REFUTED`, `NOT_ESTABLISHED`), data sufficiency assessment, the mandatory 8-Point Forensic Schema, and epistemic limitations.
- **Tab B: Interactive Analytics:** Chart.js dual-metric visualization (Reported Sales YoY vs Expense Residual Heuristic, and Debtor Days velocity). Features hover tooltips, period toggles, and a compact data-table view with zero false zeros.
- **Tab C: Courtroom Adjudication:** Adversarial debate cards (Prosecution vs Defense), testable predictions, falsification criteria, and follow-up investigation recommendations.
- **Tab D: Evidence Explorer:** Filterable registry of statutory disclosures and earnings call transcripts with an interactive detail modal containing verbatim excerpts and direct BSE/NSE links.
- **Tab E: Normalized Data & Provenance:** Full observation table from `ForensicEngine` with formula inspection for derived metrics.
- **Tab F: Artifacts & Export:** Download verified artifacts directly:
  - Official Institutional PDF Research Note (`<ticker>_forensic_report.pdf`)
  - Structured Audit State Bundle (`investigation_<ticker>.json`)
  - Run Audit Manifest (`run_manifest.json`)
  - Source Disclosures Snapshot (`source_snapshot_<ticker>.json`)
  - High-Res Forensic Chart (`forensic_chart_<ticker>.png`)

---

## 6. Real-Time Pipeline Stages

Investigations follow nine canonical execution phases:
1. `data_ingestion`: Ingesting statutory financial disclosures from Screener and exchange filings.
2. `financial_analytics`: Running deterministic math sandbox (canonical DSRI, margin wedge, expense residual).
3. `anomaly_triage`: Prioritizing divergences by severity score (or routing to normal baseline compiler).
4. `hypothesis_generation`: Formulating competing adverse and benign explanations via Gemini.
5. `evidence_retrieval`: Harvesting concall dialogue blocks and verified press reports.
6. `peer_analysis`: Triangulating with peer filings and calculating idiosyncratic spread.
7. `adversarial_assessment`: Prosecution vs Defense debate evaluated by independent adjudicator.
8. `report_validation`: Applying deterministic citation, direction, and schema validation gates.
9. `pdf_generation`: Compiling the dark-theme PDF report and high-resolution chart.

---

## 7. Storage, Persistence & Artifacts

- **SQLite Database:** `data/alphadecay.db` stores all runs, real-time stage events, computed metrics, observations, and structured adjudications.
- **Run-Scoped Artifact Directories:** Generated files are placed in isolated directories:
  `data/runs/<run_id>/`
  - Prevents race conditions or concurrent runs from overwriting each other's outputs.
  - Download endpoints verify path containment to prevent path traversal vulnerabilities.

---

## 8. Provider Diagnostics & Health

Access the settings and diagnostics page at `/settings` or via API:
- `GET /api/health`: Instant health check of model configuration.
- `GET /api/diagnostics`: Detailed diagnostics without remote calls.
- `GET /api/diagnostics?live=true`: Active ping verifying live latency and reachability of Gemini and Ollama.

---

## 9. Security Posture

AlphaDecay is designed as an institutional research workstation with strict security boundaries:
- **Localhost Only:** Development server binds to `127.0.0.1` by default.
- **Debug Mode Off:** Flask runs with `debug=False` by default.
- **Zero Secret Leakage:** API keys are never exposed in DOM attributes, HTML templates, JSON responses, or logs.
- **CSRF Protection:** State-changing API endpoints require a valid session CSRF token via `X-CSRF-Token` header or form field.
- **Path Traversal Defense:** Artifact serving verifies that filenames conform to strict regex patterns and reside inside the canonical run folder.
- **Jinja2 Autoescaping:** All untrusted evidence text is HTML-escaped.

---

## 10. Automated Tests

AlphaDecay includes a comprehensive test suite covering analytics, courtroom logic, model provider routing, PDF rendering, Flask routes, integration workflows, and security:

```bash
# Run all 70 automated tests
pytest -v
```

### Test Breakdown
- `tests/test_analytics.py`: Hand-calculated canonical DSRI, growth formulas, edge cases.
- `tests/test_courtroom.py`: 8-point schema, legacy verdict migration, reflection router.
- `tests/test_evidence.py`: Provenance vault, citation validator, cutoff date filtering.
- `tests/test_llm_provider.py`: Gemini-first routing, Ollama fallback, bounded backoff, structured repair.
- `tests/test_pdf_export.py`: ReportLab two-page dark canvas rendering and charts.
- `tests/test_periods.py`: YoY period alignment, March 2025 vs March 2024 regression fix.
- `tests/test_regressions.py`: Domain regressions across FMCG companies and margin signs.
- `tests/test_theme_rendering.py`: Color token contrast and dark PDF pixel verification.
- `tests/test_webapp_routes.py`: Flask dashboard, submission validation, 404 handling, pagination.
- `tests/test_webapp_integration.py`: End-to-end background execution, DB durability, cancellation.
- `tests/test_webapp_security.py`: CSRF enforcement, path traversal defense, secret sanitization.

---

## 11. License

MIT License. Developed for Production-Grade Forensic Financial Intelligence.
