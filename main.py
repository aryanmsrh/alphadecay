import sys
import os
import argparse
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from engine.investigator import investigate_company
from webapp.run_store import run_store


def main():
    parser = argparse.ArgumentParser(description="AlphaDecay: Autonomous Financial Research Agent")
    parser.add_argument("--ticker", type=str, default="HINDUNILVR", help="Listed company ticker symbol (default: HINDUNILVR)")
    parser.add_argument("--hypothesis", type=str, default=None, help="Forensic hypothesis to investigate (optional)")
    parser.add_argument("--export-pdf", action="store_true", default=False, help="Export 2-page investigation PDF report")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for generated artifacts")
    parser.add_argument("--offline", action="store_true", default=False, help="Force offline mode using local Ollama model")

    args = parser.parse_args()

    if args.offline:
        config.USE_OFFLINE_MODE = True
        os.environ["USE_OFFLINE_MODE"] = "true"

    ticker = args.ticker.upper().strip()
    run_id = uuid.uuid4().hex[:8]

    print("=" * 80)
    print("  AlphaDecay // Finding the Next Signal: Autonomous Research Agent")
    print(f"  Target Entity:       {ticker}")
    print(f"  Run Identifier:      {run_id}")
    print(f"  Sector Track:        Track C — Consumer, FMCG & Retail")
    print(f"  Primary Cloud Model: {config.GEMINI_MODEL}")
    print(f"  Fallback Model:      {config.OLLAMA_FALLBACK_MODEL}")
    print(f"  Execution Mode:      {'OFFLINE (Ollama)' if config.USE_OFFLINE_MODE else 'ONLINE (Gemini First)'}")
    print("=" * 80)

    print(f"\n[1/5] Ingesting statutory filings & computing financial indicators...")
    try:
        result = investigate_company(
            ticker=ticker,
            hypothesis=args.hypothesis,
            run_id=run_id,
            output_dir=args.output_dir
        )
    except Exception as e:
        print(f"\n[ERROR] Investigation failed: {e}")
        sys.exit(1)

    result["status"] = "COMPLETED"
    result["adjudication_verdict"] = result.get("verdict")
    result["primary_finding"] = result.get("report", {}).get("1_The_Discovery") or result.get("report", {}).get("verdict_summary")
    result["provider_used"] = result.get("provider")
    run_store.save_run(result)

    print(f"\n[2/5] Verified Financial Indicators & Metric Significations:")
    print("-" * 80)
    for kn in result.get("indicators", {}).get("key_numbers", []):
        print(f"  • {kn.get('name')}: {kn.get('value')}")
        print(f"    Math Formula: {kn.get('formula')}")
        print(f"    Calculation:  {kn.get('calculation_steps')}")
        print(f"    Plain Meaning: {kn.get('plain_english')}")
        print(f"    Significance:  {kn.get('what_it_signifies')}\n")

    anomalies = result.get("indicators", {}).get("anomalies", [])
    print(f"[3/5] Top Tested Financial Anomalies (Ranked by Severity / 10):")
    print("-" * 80)
    for idx, an in enumerate(anomalies[:5], 1):
        print(f"  {idx}. [{an.get('severity')}/10] {an.get('metric')}")
        print(f"     Observation:  {an.get('summary')}")
        print(f"     Math Detail:  {an.get('math_detail')}")
        print(f"     Significance: {an.get('significance')}\n")

    cyclic = result.get("cyclic_results", {})
    passed = cyclic.get("passed_hypotheses", [])
    failed = cyclic.get("failed_hypotheses", [])

    print(f"[4/5] Cyclic Agent Pipeline Audit (Pitted against Adversarial Disproving Agent):")
    print("-" * 80)
    print(f"  >> Hypotheses That Passed Scrutiny ({len(passed)}):")
    if passed:
        for p in passed:
            print(f"     • From Anomaly: [{p.get('anomaly_metric')} - Severity {p.get('severity')}/10 - Attempt #{p.get('attempt_passed', 1)}]")
            print(f"       Hypothesis:   \"{p.get('hypothesis')}\"")
            print(f"       Defense Overcome: {p.get('counterargument_overcome')}\n")
    else:
        print("     • (None) All adverse hypotheses were disproved by benign FMCG operational context.\n")

    print(f"  >> Hypotheses That Failed Scrutiny ({len(failed)}):")
    if failed:
        for f in failed:
            print(f"     • From Anomaly: [{f.get('anomaly_metric')} - Severity {f.get('severity')}/10]")
            print(f"       Refuted By Defense: {f.get('attempt_1_counterargument') or f.get('attempt_2_counterargument')}\n")
    else:
        print("     • None failed.\n")

    verdict = result.get("verdict")
    report = result.get("report", {})

    print("=" * 80)
    print(f"  FINAL ADJUDICATION VERDICT: {verdict}")
    print("=" * 80)
    print(f"\n  [OFFICIAL 8-POINT HACKATHON DELIVERABLE]")
    print(f"  1. The Discovery:           {report.get('1_The_Discovery', report.get('verdict_summary', ''))}")
    
    why_matters = report.get('2_Why_It_Matters', [])
    print(f"  2. Why It Matters:")
    if isinstance(why_matters, list):
        for wm in why_matters:
            print(f"     • {wm}")
    else:
        print(f"     • {why_matters}")

    ev_items = report.get('3_Evidence', [])
    print(f"  3. Evidence Sources:")
    if isinstance(ev_items, list):
        for ev in ev_items[:3]:
            print(f"     • {ev}")
    else:
        print(f"     • {ev_items}")

    print(f"  4. Timeline:                {report.get('4_Timeline', '')}")
    print(f"  5. Numbers:                 {report.get('5_Numbers', '')}")
    print(f"  6. Counterargument:         {report.get('6_Counterargument', '')}")
    print(f"  7. Falsification Condition: {report.get('7_Falsification_Condition', '')}")
    print(f"  8. Evidence Strength:       {report.get('8_Evidence_Strength', '')}")
    print("=" * 80)

    print(f"\n[5/5] Generated Deliverables:")
    print(f"  • Dual-Axis Chart:  {result.get('chart_path')}")
    print(f"  • 2-Page PDF Report: {result.get('pdf_path')}")
    print(f"  • Model Provider:   {result.get('provider')}")
    print(f"  • Verified Sources: {result.get('evidence_count')} cited\n")


if __name__ == "__main__":
    main()
