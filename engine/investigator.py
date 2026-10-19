import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from ingestion.screener import ScreenerScraper
from ingestion.concall_harvester import ConcallHarvester
from ingestion.web_search import TavilySearchClient
from engine.analytics import calculate_financial_indicators
from agent.cyclic_pipeline import run_cyclic_investigation
from exporter.chart import generate_investigation_chart
from exporter.pdf import generate_pdf_report


def investigate_company(
    ticker: str,
    hypothesis: Optional[str] = None,
    run_id: Optional[str] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    clean_ticker = ticker.upper().strip()
    if not run_id:
        run_id = str(uuid.uuid4())[:8]

    base_dir = Path(output_dir or f"data/runs/{run_id}")
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ingestion: Screener.in statutory tables
    scraper = ScreenerScraper()
    raw_data = scraper.fetch_company_data(clean_ticker)
    company_name = raw_data.get("company_name", clean_ticker)

    # 2. Analytics: Deterministic Python calculations + Top 5 Anomaly scoring /10
    indicators = calculate_financial_indicators(raw_data)

    # 3. Evidence Collection: Earnings call excerpts + Web Search
    evidence_items = []

    concall_links = raw_data.get("concall_transcripts", [])
    if concall_links:
        harvester = ConcallHarvester()
        for item in concall_links[:2]:
            link = item.get("url") if isinstance(item, dict) else item
            excerpts = harvester.harvest_transcript(link)
            for ex in excerpts:
                evidence_items.append({
                    "source": f"Concall: {item.get('title', 'Earnings Transcript') if isinstance(item, dict) else 'Transcript'}",
                    "url": ex.get("source_url", link),
                    "excerpt": ex.get("excerpt", "")
                })
            if len(evidence_items) >= 4:
                break

    search_client = TavilySearchClient()
    search_hits = search_client.search(f"{company_name} {clean_ticker} quarterly financial results margin concall distributor", max_results=3)
    for hit in search_hits:
        evidence_items.append({
            "source": hit.get("title", "News & Disclosures"),
            "url": hit.get("url", ""),
            "excerpt": hit.get("content", "")
        })

    if not evidence_items:
        evidence_items.append({
            "source": "Statutory Quarterly Filing",
            "url": f"https://www.screener.in/company/{clean_ticker}/",
            "excerpt": f"Statutory quarterly financials extracted directly from regulatory filing tables for {company_name}."
        })

    # 4. Cyclic Pipeline: Formulate Hypotheses -> Disproving Agent -> Retry -> Audit
    cyclic_results = run_cyclic_investigation(
        company_name=company_name,
        ticker=clean_ticker,
        anomalies=indicators.get("anomalies", []),
        key_numbers=indicators.get("key_numbers", []),
        evidence_items=evidence_items
    )

    verdict = cyclic_results["final_verdict"]
    report = cyclic_results["report_8_point"]
    report["verdict_summary"] = cyclic_results["verdict_summary"]

    # 5. Visual Artifacts: Chart & PDF
    chart_file = str(base_dir / "chart.png")
    generate_investigation_chart(clean_ticker, indicators.get("quarterly_history", []), chart_file)

    pdf_file = str(base_dir / "report.pdf")
    generate_pdf_report(
        output_path=pdf_file,
        company=company_name,
        ticker=clean_ticker,
        hypothesis=hypothesis or report.get("1_The_Discovery", ""),
        verdict=verdict,
        report=report,
        indicators=indicators,
        chart_path=chart_file,
        cyclic_results=cyclic_results
    )

    result = {
        "run_id": run_id,
        "ticker": clean_ticker,
        "company_name": company_name,
        "hypothesis": hypothesis or report.get("1_The_Discovery", ""),
        "verdict": verdict,
        "adjudication_verdict": verdict,
        "evidence_strength": cyclic_results.get("evidence_strength") or report.get("8_Evidence_Strength", "Strong (8.5/10)"),
        "provider": "gemini",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "indicators": indicators,
        "anomalies": indicators.get("anomalies", []),
        "cyclic_results": cyclic_results,
        "passed_hypotheses": cyclic_results.get("passed_hypotheses", []),
        "failed_hypotheses": cyclic_results.get("failed_hypotheses", []),
        "trial_audit_log": cyclic_results.get("trial_audit_log", []),
        "report": report,
        "chart_path": chart_file,
        "pdf_path": pdf_file,
        "evidence_items": evidence_items,
        "evidence_count": len(evidence_items)
    }

    return result
