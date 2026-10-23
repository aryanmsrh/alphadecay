#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
import uuid

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import config
from agent.pipeline import run_investigation
from archive import archive


def main():
    parser = argparse.ArgumentParser(description="AlphaDecay CLI")
    parser.add_argument(
        "--ticker",
        type=str,
        default="HINDUNILVR",
        help="Listed company ticker symbol",
    )
    parser.add_argument(
        "--hypothesis",
        type=str,
        default=None,
        help="Specific question or focus area",
    )
    parser.add_argument(
        "--anomalies",
        type=int,
        default=1,
        help="Number of anomalies to evaluate (1 to 5, default 1)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        default=False,
        help="Keep generated run files",
    )

    args = parser.parse_args()
    ticker = args.ticker.upper().strip()
    anomaly_count = max(1, min(args.anomalies, 5))
    run_id = uuid.uuid4().hex[:8]

    print("=" * 80)
    print("  AlphaDecay")
    print(f"  Target:           {ticker}")
    print(f"  Run ID:           {run_id}")
    print(f"  Anomalies:        {anomaly_count}")
    print(f"  Model:            {config.OLLAMA_MODEL}")
    print("=" * 80)

    try:
        result = run_investigation(
            ticker=ticker,
            hypothesis=args.hypothesis,
            run_id=run_id,
            output_dir=args.output_dir,
            anomaly_count=anomaly_count,
        )
    except Exception as e:
        print(f"\n[ERROR] Investigation failed: {e}")
        sys.exit(1)

    result["status"] = "COMPLETED"
    archive.save_report(result)

    anomalies = result.get("investigated_anomalies", [])
    for anom in anomalies:
        idx = anom.get("index", 1)
        metric = anom.get("metric", "")
        rpt = anom.get("report", {})

        print("\n" + "=" * 80)
        print(f"  ANOMALY {idx}: {metric}")
        print("=" * 80)
        print(f"  1. The Discovery:           {rpt.get('discovery') or rpt.get('the_discovery', '')}")

        print("  2. Why It Matters:")
        why = rpt.get("why_it_matters", [])
        if isinstance(why, list):
            for b in why:
                print(f"     • {b}")
        else:
            print(f"     • {why}")

        print("  3. Evidence:")
        ev = rpt.get("evidence", [])
        if isinstance(ev, list):
            for e in ev:
                if isinstance(e, dict):
                    print(f"     • [{e.get('source', '')}] — {e.get('url', '')}")
                else:
                    print(f"     • {e}")
        else:
            print(f"     • {ev}")

        print("  4. Timeline:")
        tl = rpt.get("timeline", "")
        if isinstance(tl, list):
            for t in tl:
                print(f"     • {t}")
        elif isinstance(tl, str):
            lines = [l.strip().lstrip("-•* ") for l in tl.split("\n") if l.strip()]
            if len(lines) > 1:
                for l in lines:
                    print(f"     • {l}")
            else:
                print(f"     {tl}")

        print("  5. Numbers:")
        num_items = rpt.get("numbers", [])
        if isinstance(num_items, list):
            for n in num_items:
                print(f"     • {n}")
        else:
            print(f"     • {num_items}")

        atk = rpt.get("attacker", {})
        if isinstance(atk, dict):
            print(f"  6. Attacker Verdict:        {atk.get('verdict', '')}")
            print(f"     Attacker Strength:       {atk.get('evidence_strength', '')} ({atk.get('confidence', atk.get('confidence_rating', ''))})")
        else:
            print(f"  6. Attacker:                {atk}")

        dfn = rpt.get("defender", {})
        if isinstance(dfn, dict):
            counter = dfn.get("counterargument") or dfn.get("hypothesis") or dfn.get("alternative_explanation", "")
            print(f"  7. Defender Counterarg:     {counter}")
            print(f"     Falsification Condition: {dfn.get('falsification_condition', '')}")
            print(f"     Defender Strength:       {dfn.get('evidence_strength', '')} ({dfn.get('confidence', dfn.get('confidence_rating', ''))})")
        else:
            print(f"  7. Defender:                {dfn}")

        print("  8. Strength:")
        st = rpt.get("strength", "")
        if isinstance(st, list):
            for s in st:
                print(f"     • {s}")
        elif isinstance(st, str) and " | " in st:
            for part in st.split(" | "):
                print(f"     • {part.strip()}")
        else:
            print(f"     • Attacker: {atk.get('evidence_strength', '')} ({atk.get('confidence', '')})")
            print(f"     • Defender: {dfn.get('evidence_strength', '')} ({dfn.get('confidence', '')})")
        print("-" * 80)


    if not args.keep_data:
        archive.delete_report(run_id)


if __name__ == "__main__":
    main()
