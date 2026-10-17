import sys
import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ingestion.screener import ScreenerScraper
from engine.forensics import ForensicEngine
from agent.graph import investigation_app
from config import TRACK_C_NIFTY50

def run_investigation(ticker: str):
    ticker = ticker.upper().strip()
    print("=" * 70)
    print(f"  ALPHA-DECAY: Autonomous Forensic Investigation Engine")
    print(f"  Target Stock: {ticker} (Track C: FMCG & Retail)")
    print("=" * 70)

    # Step 1: Scrape Ingestion Layer
    print(f"\n[Phase 1] Fetching statutory filings from Screener.in for '{ticker}'...")
    scraper = ScreenerScraper(use_cache=True)
    raw_data = scraper.fetch_company_data(ticker)
    company_name = raw_data.get("company_name", ticker)
    print(f"  --> Identified Entity: {company_name}")
    print(f"  --> Quarters Ingested: {len(raw_data.get('quarters', {}).get('periods', []))} quarters")

    # Step 2: Deterministic Forensic Math Sandbox (0-LLM)
    print(f"\n[Phase 2] Executing Deterministic Math Sandbox (Pure Python/NumPy)...")
    summary = ForensicEngine.audit_company(raw_data)
    print(f"  --> Quarters Analyzed: {summary.quarters_analyzed}")
    print(f"  --> Anomalies Flagged: {len(summary.anomalies)}")
    for idx, anom in enumerate(summary.anomalies, 1):
        print(f"      {idx}. {anom.metric_name} | Delta: {anom.delta} | Severity: {anom.severity_score}")

    # Step 3: LangGraph Multi-Agent Orchestration
    print(f"\n[Phase 3] Launching LangGraph Cyclic State Engine...")
    initial_state = {
        "ticker": ticker,
        "company_name": company_name,
        "raw_financials": raw_data,
        "computed_metrics": {
            "debtor_days": summary.debtor_days,
            "sales_growth_yoy": summary.sales_growth_yoy,
            "cfo_to_ebitda": summary.cfo_to_ebitda
        },
        "anomalies": [a.model_dump() for a in summary.anomalies],
        "selected_anomaly": None,
        "hypothesis": None,
        "prosecution_evidence": [],
        "peer_evidence": [],
        "defense_arguments": [],
        "is_falsified": False,
        "falsification_reason": None,
        "evidence_strength": None,
        "iteration_count": 0,
        "final_discovery": None,
        "logs": []
    }

    final_state = investigation_app.invoke(initial_state)

    # Step 4: Display Deliverable (Mandatory 8-Point Schema)
    print("\n" + "=" * 70)
    print("  FINAL DELIVERABLE: MANDATORY 8-POINT FORENSIC SCHEMA")
    print("=" * 70)
    discovery = final_state.get("final_discovery", {})
    if discovery:
        for k, v in discovery.items():
            key_name = k.replace("_", " ")
            if isinstance(v, list):
                print(f"\n• {key_name}:")
                for item in v:
                    print(f"    - {item}")
            else:
                print(f"\n• {key_name}:\n    {v}")
    else:
        print("No discovery compiled.")
    print("\n" + "=" * 70)
    print("  [Audit Complete] No buy/sell advice provided. Strictly forensic.")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlphaDecay Autonomous Forensic Investigator")
    parser.add_argument("--ticker", type=str, default="HINDUNILVR", help="Track C NIFTY 50 Ticker (default: HINDUNILVR)")
    args = parser.parse_args()
    run_investigation(args.ticker)
