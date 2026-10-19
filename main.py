import sys
import os
import argparse
import json
import time
import uuid
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from ingestion.screener import ScreenerScraper
from engine.forensics import ForensicEngine
from agent.graph import investigation_app
from agent.llm_provider import CentralModelProvider
from exporter.pdf_report import export_forensic_pdf
from config import TRACK_C_NIFTY50, INVESTIGATION_CUTOFF_DATE, MAX_ANOMALIES_TO_INVESTIGATE


def run_investigation(
    ticker: str,
    export_pdf_path: Optional[str] = None,
    cutoff_date_str: Optional[str] = None,
    output_dir: Optional[str] = None,
    json_output: Optional[str] = None,
    max_anomalies: Optional[int] = None,
    offline: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    start_time = time.time()
    ticker = ticker.upper().strip()
    now_utc = datetime.now(timezone.utc)
    run_id = f"RUN-{now_utc.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    
    # Configure output directory
    out_path = Path(output_dir).resolve() if output_dir else BASE_DIR / "data"
    out_path.mkdir(parents=True, exist_ok=True)

    # Configure operational modes
    if offline:
        config.USE_OFFLINE_MODE = True
        os.environ["USE_OFFLINE_MODE"] = "true"

    effective_max_anomalies = max_anomalies if max_anomalies is not None else MAX_ANOMALIES_TO_INVESTIGATE

    # Cutoff date validation: strict error raising
    cutoff_d: Optional[date] = None
    cutoff_input = cutoff_date_str or INVESTIGATION_CUTOFF_DATE
    if cutoff_input:
        try:
            cutoff_d = datetime.strptime(cutoff_input.strip(), "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(
                f"Invalid cutoff date '{cutoff_input}'. Expected strict ISO format 'YYYY-MM-DD'."
            ) from e

    print("=" * 70)
    print(f"  ALPHA-DECAY: Autonomous Forensic Investigation Engine v2.0")
    print(f"  Target Stock: {ticker} (Track C: FMCG & Retail)")
    print(f"  Run Identifier: {run_id}")
    print(f"  Execution Mode: {'OFFLINE (Ollama Local)' if config.USE_OFFLINE_MODE else f'ONLINE ({config.GEMINI_MODEL})'}")
    if cutoff_d:
        print(f"  Point-in-Time Cutoff Date: {cutoff_d}")
    print("=" * 70)

    # Step 1: Live Scraping Ingestion
    print(f"\n[Phase 1] Ingesting statutory disclosures for '{ticker}'...")
    scraper = ScreenerScraper(use_cache=True)
    raw_data = scraper.fetch_company_data(ticker)
    company_name = raw_data.get("company_name", ticker)
    print(f"  --> Identified Entity: {company_name}")
    print(f"  --> Quarters Ingested: {len(raw_data.get('quarters', {}).get('periods', []))} periods")

    # Step 2: Deterministic Forensic Math Sandbox (Zero LLM Arithmetic)
    print(f"\n[Phase 2] Executing Deterministic Math Sandbox (Canonical Ratios & Period Alignment)...")
    summary = ForensicEngine.audit_company(raw_data, cutoff_date=cutoff_d)
    print(f"  --> Quarters Analyzed: {summary.quarters_analyzed}")
    print(f"  --> Canonical DSRI: {summary.beneish_dsri} | Debtor Days Proxy: {summary.debtor_days_ratio_proxy}")
    print(f"  --> Anomalies Flagged: {len(summary.anomalies)}")
    for idx, anom in enumerate(summary.anomalies, 1):
        print(f"      {idx}. {anom.metric_name} | Delta: {anom.delta} {anom.unit} | Priority Score: {anom.severity_score:.1f}")

    if summary.no_material_anomaly_detected:
        print("  --> [Forensic Notice] NO MATERIAL ACCOUNTING ANOMALY EXCEEDED SCREENING THRESHOLDS.")

    # Step 3: LangGraph Multi-Agent Orchestration
    print(f"\n[Phase 3] Launching LangGraph Courtroom Orchestration (Central Gemini-First Provider)...")
    initial_state = {
        "run_id": run_id,
        "ticker": ticker,
        "company_name": company_name,
        "raw_financials": raw_data,
        "computed_metrics": {
            "debtor_days": summary.debtor_days,
            "sales_growth_yoy": summary.sales_growth_yoy,
            "expense_adjusted_residual": summary.expense_adjusted_residual,
            "beneish_dsri": summary.beneish_dsri,
            "debtor_days_ratio_proxy": summary.debtor_days_ratio_proxy,
            "beneish_sgi": summary.beneish_sgi,
            "beneish_gmi": summary.beneish_gmi,
            "cfo_to_ebitda": summary.cfo_to_ebitda,
            "margin_wedge_bps": summary.margin_wedge_bps,
            "operating_margin_delta_bps": summary.operating_margin_delta_bps,
            "distribution_drag_bps": summary.distribution_drag_bps,
            "peer_spread_days": summary.peer_spread_days
        },
        "anomalies": [a.model_dump() for a in summary.anomalies],
        "no_material_anomaly": summary.no_material_anomaly_detected,
        "selected_anomaly": None,
        "competing_hypotheses": [],
        "adverse_hypothesis": None,
        "benign_hypothesis": None,
        "prosecution_evidence": [],
        "peer_evidence": [],
        "contradiction_analysis": None,
        "adversarial_arguments": None,
        "adjudication": None,
        "is_falsified": False,
        "falsification_reason": None,
        "evidence_strength": None,
        "data_sufficiency": None,
        "adjudication_verdict": None,
        "iteration_count": 0,
        "current_anomaly_index": 0,
        "max_anomalies": effective_max_anomalies,
        "completed_investigations": [],
        "final_discovery": None,
        "provider_metadata": {},
        "validation_passed": False,
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
    print("  [Audit Complete] No investment recommendations provided. Strictly forensic.")
    print("=" * 70)

    # Step 5: Optional PDF Export
    pdf_path = None
    if export_pdf_path:
        computed_res = final_state.get("computed_metrics", {})
        if "peer_spread_days" in computed_res and computed_res["peer_spread_days"] is not None:
            summary.peer_spread_days = computed_res["peer_spread_days"]

        selected_a = final_state.get("selected_anomaly")
        if selected_a and summary.anomalies:
            surviving_unit = selected_a.get("unit")
            if surviving_unit:
                summary.anomalies[0].unit = surviving_unit

        # Enrich summary with run metadata for institutional PDF header
        summary.model_used = final_state.get("provider_metadata", {}).get("model_name") or config.GEMINI_MODEL
        summary.thinking_level = config.GEMINI_THINKING_LEVEL
        summary.provider_used = final_state.get("provider_metadata", {}).get("provider_used") or ("ollama" if config.USE_OFFLINE_MODE else "gemini")
        summary.as_of_date = str(cutoff_d) if cutoff_d else None

        if export_pdf_path == "default":
            target_pdf = str(out_path / f"{ticker}_forensic_report.pdf")
        else:
            target_pdf = export_pdf_path

        pdf_path = export_forensic_pdf(ticker, company_name, summary, discovery, target_pdf)
        print(f"\n[PDF Exporter] Official research note saved to: {pdf_path}")

    duration_sec = time.time() - start_time

    # Step 6: Emit Secret-Free Run Manifest JSON
    adjudication_obj = final_state.get("adjudication")
    verdict_str = None
    if isinstance(adjudication_obj, dict):
        verdict_str = adjudication_obj.get("verdict")
    elif adjudication_obj is not None:
        verdict_str = getattr(adjudication_obj, "verdict", None)

    manifest = {
        "run_id": run_id,
        "ticker": ticker,
        "company_name": company_name,
        "timestamp_utc": now_utc.isoformat(),
        "cutoff_date": str(cutoff_d) if cutoff_d else None,
        "model_configured": config.GEMINI_MODEL,
        "model_used": final_state.get("provider_metadata", {}).get("model_name", config.GEMINI_MODEL),
        "provider_used": final_state.get("provider_metadata", {}).get("provider_used", "gemini" if not config.USE_OFFLINE_MODE else "ollama"),
        "thinking_level": config.GEMINI_THINKING_LEVEL,
        "offline_mode": config.USE_OFFLINE_MODE,
        "quarters_analyzed": summary.quarters_analyzed,
        "anomalies_detected_count": len(summary.anomalies),
        "no_material_anomaly_detected": summary.no_material_anomaly_detected,
        "adjudication_verdict": verdict_str,
        "validation_passed": final_state.get("validation_passed", False),
        "pdf_report_path": pdf_path,
        "duration_seconds": round(duration_sec, 2)
    }

    manifest_file = out_path / "run_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    if verbose:
        print(f"\n[Manifest] Run audit manifest saved to: {manifest_file}")

    # Step 7: Optional JSON Output & Source Data Snapshot
    if json_output:
        json_file = Path(json_output) if json_output != "default" else out_path / f"investigation_{ticker}.json"
        export_bundle = {
            "manifest": manifest,
            "final_discovery": discovery,
            "computed_metrics": final_state.get("computed_metrics", {}),
            "anomalies": final_state.get("anomalies", []),
            "raw_financials": final_state.get("raw_financials", {}),
            "logs": final_state.get("logs", [])
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(export_bundle, f, indent=2, default=str)
        print(f"[JSON Exporter] Full structured state bundle saved to: {json_file}")

        # Also save standalone raw data snapshot for audit reproducibility
        raw_snapshot_file = out_path / f"source_snapshot_{ticker}.json"
        with open(raw_snapshot_file, "w", encoding="utf-8") as f:
            json.dump(final_state.get("raw_financials", {}), f, indent=2, default=str)
        print(f"[Snapshot Exporter] Raw source financial disclosures saved to: {raw_snapshot_file}")

    # Step 8: Persist CLI execution into Durable Run Store
    try:
        from webapp.run_store import run_store
        run_store.create_run(
            run_id=run_id,
            ticker=ticker,
            company_name=company_name,
            cutoff_date=str(cutoff_d) if cutoff_d else None,
            max_anomalies=effective_max_anomalies,
            offline_mode=config.USE_OFFLINE_MODE,
            model_configured=config.GEMINI_MODEL,
            thinking_level=config.GEMINI_THINKING_LEVEL,
            output_dir=str(out_path)
        )
        run_store.update_run_status(
            run_id=run_id,
            status="SUCCEEDED",
            current_stage="completed",
            duration_seconds=round(duration_sec, 2),
            company_name=company_name,
            model_used=manifest["model_used"],
            provider_used=manifest["provider_used"],
            quarters_analyzed=manifest["quarters_analyzed"],
            anomalies_detected_count=manifest["anomalies_detected_count"],
            no_material_anomaly=manifest["no_material_anomaly_detected"],
            adjudication_verdict=manifest["adjudication_verdict"],
            primary_finding=discovery.get("1_The_Discovery") if discovery else None,
            validation_passed=manifest["validation_passed"],
            pdf_path=pdf_path,
            json_path=str(out_path / f"investigation_{ticker}.json"),
            manifest_path=str(manifest_file),
            snapshot_path=str(raw_snapshot_file)
        )
    except Exception:
        pass

    return final_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlphaDecay Autonomous Forensic Investigator")
    parser.add_argument("--ticker", type=str, default="HINDUNILVR", help="Track C NIFTY 50 Ticker (default: HINDUNILVR)")
    parser.add_argument("--export-pdf", nargs="?", const="default", default=None, 
                        help="Export 8-point schema finding to PDF (e.g. --export-pdf or --export-pdf report.pdf)")
    parser.add_argument("--cutoff-date", type=str, default=None,
                        help="Reproducible investigation cutoff date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory for generated artifacts (PDFs, charts, manifests)")
    parser.add_argument("--json-output", nargs="?", const="default", default=None,
                        help="Export structured audit state bundle to JSON")
    parser.add_argument("--max-anomalies", type=int, default=None,
                        help="Maximum number of anomalies to investigate sequentially")
    parser.add_argument("--offline", action="store_true", default=False,
                        help="Force offline mode using local Ollama model")
    parser.add_argument("--diagnose-llm", action="store_true", default=False,
                        help="Run connectivity diagnostics across configured LLM providers and exit")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Enable verbose progress output")

    args = parser.parse_args()

    if args.diagnose_llm:
        print("Running Central Model Provider Diagnostics...")
        results = CentralModelProvider.diagnose_providers()
        print(json.dumps(results, indent=2))
        sys.exit(0)

    try:
        run_investigation(
            ticker=args.ticker,
            export_pdf_path=args.export_pdf,
            cutoff_date_str=args.cutoff_date,
            output_dir=args.output_dir,
            json_output=args.json_output,
            max_anomalies=args.max_anomalies,
            offline=args.offline,
            verbose=args.verbose
        )
    except Exception as exc:
        print(f"\n[Fatal Error] Investigation terminated: {exc}", file=sys.stderr)
        sys.exit(1)

