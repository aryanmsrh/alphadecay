import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.attacker import Attacker
from agent.defender import Defender
from agent.finder import Finder
from agent.llm import LLM
from config import OLLAMA_MODEL
from export.pdf import generate_pdf_report


def build_deterministic_numbers(
    anomaly: Dict[str, Any],
    key_numbers: Optional[List[Dict[str, Any]]] = None,
    peer_benchmarks: Optional[List[str]] = None,
) -> List[str]:
    bullets: List[str] = []
    raw_bullets = anomaly.get("numbers_bullets", [])
    for b in raw_bullets:
        clean_b = str(b).strip()
        if clean_b and clean_b not in bullets:
            bullets.append(clean_b)

    if not bullets and anomaly.get("math_detail"):
        for part in str(anomaly["math_detail"]).split(";"):
            clean_p = part.strip()
            if clean_p and clean_p not in bullets:
                bullets.append(clean_p)

    if key_numbers:
        for kn in key_numbers[:3]:
            name = kn.get("name")
            val = kn.get("value")
            period = kn.get("period")
            line = f"{name}: {val} ({period})"
            if line not in bullets and not any(name in b for b in bullets):
                bullets.append(line)

    if peer_benchmarks:
        for pb in peer_benchmarks:
            line = f"Sector Peer Benchmark: {pb}"
            if line not in bullets and not any(pb in b for b in bullets):
                bullets.append(line)

    return bullets


def build_deterministic_evidence(evidence_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    clean_list: List[Dict[str, str]] = []
    seen_urls = set()
    for item in evidence_items:
        if isinstance(item, dict):
            src = str(item.get("source", "Public Statutory Filing")).strip()
            url = str(item.get("url", "")).strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                clean_list.append({"source": src, "url": url})
        elif isinstance(item, str):
            clean_item = item.strip()
            if clean_item and clean_item not in seen_urls:
                seen_urls.add(clean_item)
                clean_list.append({"source": "Statutory Filing", "url": clean_item})

    if not clean_list:
        clean_list.append({
            "source": "Statutory Financial Disclosures (Screener / BSE)",
            "url": "https://www.screener.in",
        })
    return clean_list


def synthesize_anomaly_report(
    company_name: str,
    ticker: str,
    anomaly: Dict[str, Any],
    key_numbers: List[Dict[str, Any]],
    evidence_items: List[Dict[str, Any]],
    attacker_result: Dict[str, Any],
    defender_result: Dict[str, Any],
    dossier: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    metric = anomaly.get("metric", "Financial Metric")
    summary = anomaly.get("summary", "")
    math_detail = anomaly.get("math_detail", "")
    directional_comparison = anomaly.get("directional_comparison", summary)
    multi_quarter_trajectory = anomaly.get("multi_quarter_trajectory", summary)
    numbers_bullets = anomaly.get("numbers_bullets", [])
    peer_benchmarks = dossier.get("peer_benchmarks", []) if dossier else []

    numbers_list = build_deterministic_numbers(anomaly, key_numbers, peer_benchmarks)
    evidence_clean = build_deterministic_evidence(evidence_items)

    numbers_text = "\n".join([f"- {n}" for n in numbers_list])
    atk_verdict = str(attacker_result.get("verdict", "") or attacker_result.get("hypothesis", "")).strip()
    def_counter = str(defender_result.get("counterargument", "") or defender_result.get("hypothesis", "")).strip()

    prompt = f"""Target Entity: {company_name} ({ticker})

Anomaly Under Review:
- Metric: {metric}
- Directional Fact: {directional_comparison}
- Multi-Quarter Trajectory: {multi_quarter_trajectory}
- Calculated Numbers:
{numbers_text}

Attacker Case:
"{atk_verdict}"

Defender Case:
"{def_counter}"

Task:
Synthesize the foundational discovery sentence, the commercial why-it-matters bullet points, and the multi-quarter chronological timeline narrative.

Requirements:
1. discovery: Exactly one clear sentence stating the core financial anomaly with exact numbers.
2. why_it_matters: Array of 3 to 5 sharp, specific plain-English bullet strings explaining commercial and financial impact.
3. timeline: A chronological narrative tracing the exact multi-quarter progression from the trajectory provided.
Do not output template text or prompt instructions. Write exclusively in fluent English.

Output strictly valid JSON with this exact schema:
{{
  "discovery": "One clear sentence stating the core financial anomaly with exact numbers.",
  "why_it_matters": [
    "First impact bullet",
    "Second impact bullet",
    "Third impact bullet"
  ],
  "timeline": "Chronological narrative of the multi-quarter progression."
}}
"""
    system = "You are a senior institutional financial editor. Output strictly valid JSON conforming to the requested schema. Write exclusively in fluent English."
    llm = LLM(model=model)
    parsed, provider = llm.generate_json(prompt, system=system)
    if isinstance(parsed, dict) and "json" in parsed and isinstance(parsed["json"], dict):
        parsed = parsed["json"]

    discovery = str(parsed.get("discovery", "") or parsed.get("the_discovery", "")).strip()
    why_matters = parsed.get("why_it_matters", [])
    if isinstance(why_matters, str):
        why_matters = [why_matters]
    elif not isinstance(why_matters, list):
        why_matters = []
    why_matters = [str(b).strip() for b in why_matters if str(b).strip()]

    timeline_str = str(parsed.get("timeline", "")).strip()

    atk_strength = str(attacker_result.get("evidence_strength", "")).strip()
    atk_conf = str(attacker_result.get("confidence", "") or attacker_result.get("confidence_rating", "")).strip()

    def_fals = str(defender_result.get("falsification_condition", "")).strip()
    def_strength = str(defender_result.get("evidence_strength", "")).strip()
    def_conf = str(defender_result.get("confidence", "") or defender_result.get("confidence_rating", "")).strip()

    strength_summary = f"Attacker: {atk_conf} ({atk_strength}) | Defender: {def_conf} ({def_strength})"

    final_report = {
        "discovery": discovery,
        "the_discovery": discovery,
        "why_it_matters": why_matters,
        "evidence": evidence_clean,
        "timeline": timeline_str,
        "numbers": numbers_list,
        "attacker": {
            "verdict": atk_verdict,
            "evidence_strength": atk_strength,
            "confidence": atk_conf,
            "confidence_rating": atk_conf,
        },
        "defender": {
            "counterargument": def_counter,
            "falsification_condition": def_fals,
            "evidence_strength": def_strength,
            "confidence": def_conf,
            "confidence_rating": def_conf,
        },
        "strength": strength_summary,
    }

    return final_report, provider


def run_investigation(
    ticker: str,
    hypothesis: Optional[str] = None,
    run_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    anomaly_count: int = 1,
    event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None):
        if event_callback:
            event_callback({
                "step": step,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(data or {})
            })

    clean_ticker = ticker.upper().strip()
    if not run_id:
        run_id = uuid.uuid4().hex[:8]

    anomaly_count = max(1, min(int(anomaly_count), 5))

    active_provider = (provider or "gemini").lower()
    from config import GEMINI_MODEL, OLLAMA_MODEL
    if "gemini" in active_provider:
        active_model = GEMINI_MODEL
        provider_label = "Gemini Cloud"
    else:
        active_model = OLLAMA_MODEL
        provider_label = "Local Ollama"

    base_dir = Path(output_dir or f"data/runs/{run_id}")
    base_dir.mkdir(parents=True, exist_ok=True)

    emit("INIT", f"Targeting {clean_ticker} via {active_model} ({provider_label})", {"model": active_model, "provider": active_provider})
    emit("INGEST", f"Ingesting statutory filings and financial statements for {clean_ticker}")
    finder = Finder()
    dossier = finder.gather_company_dossier(clean_ticker)
    company_name = dossier["company_name"]
    indicators = dossier["indicators"]
    key_numbers = dossier["key_numbers"]
    evidence_items = dossier["evidence_items"]
    all_anomalies = dossier.get("anomalies", [])

    emit("ANALYTICS", f"Computed financial indicators and identified {len(all_anomalies)} anomalies")

    target_anomalies = all_anomalies[:anomaly_count]
    if not target_anomalies and all_anomalies:
        target_anomalies = [all_anomalies[0]]
    elif not target_anomalies:
        target_anomalies = [{
            "metric": "Operating Trajectory",
            "summary": "Standard operational baseline across reporting periods.",
            "math_detail": "No severe divergence flagged.",
            "severity": 3.0,
            "directional_comparison": "Metric baseline in line with disclosures.",
            "numbers_bullets": ["Operating baseline in line with disclosures."],
            "multi_quarter_trajectory": "Trailing periods consistent.",
        }]

    attacker = Attacker(model=active_model)
    defender = Defender(model=active_model)
    investigated_anomalies: List[Dict[str, Any]] = []
    last_provider = active_model

    for idx, anomaly in enumerate(target_anomalies, start=1):
        metric = anomaly.get("metric", f"Anomaly #{idx}")
        emit("ANOMALY_START", f"Examining Anomaly {idx}/{len(target_anomalies)}: {metric}", {"index": idx, "metric": metric})

        emit("ATTACKER_START", f"Attacker building prosecutorial case on {metric}", {"index": idx})
        attack_ctx = finder.get_attack_context(anomaly, key_numbers, evidence_items)
        atk_res, prov_atk = attacker.attack(
            company_name=company_name,
            ticker=clean_ticker,
            anomaly=anomaly,
            key_numbers=attack_ctx["key_numbers"],
            evidence_items=attack_ctx["evidence"],
            finder=finder,
            dossier=dossier,
            event_callback=emit,
        )
        last_provider = prov_atk

        atk_verdict = atk_res.get("verdict", "")
        emit("ATTACKER", f"Attacker Case Formed: {atk_verdict}", {
            "index": idx,
            "hypothesis": atk_verdict,
            "verdict": atk_verdict,
            "confidence": atk_res.get("confidence", "88%"),
            "evidence_strength": atk_res.get("evidence_strength", "8.5/10"),
        })

        emit("DEFENDER_START", f"Defender formulating operational counter-argument and falsification criteria for Anomaly {idx}", {"index": idx})
        def_ctx = finder.get_defense_context(anomaly, key_numbers, evidence_items)
        def_res, prov_def = defender.defend(
            company_name=company_name,
            ticker=clean_ticker,
            anomaly=anomaly,
            attacker_verdict=atk_verdict,
            key_numbers=def_ctx["key_numbers"],
            evidence_items=def_ctx["evidence"],
            finder=finder,
            dossier=dossier,
            event_callback=emit,
        )
        last_provider = prov_def

        def_counter = def_res.get("counterargument", "")
        emit("DEFENDER", f"Defender Argument Formed: {def_counter}", {
            "index": idx,
            "hypothesis": def_counter,
            "counterargument": def_counter,
            "falsification_condition": def_res.get("falsification_condition", ""),
            "confidence": def_res.get("confidence", "82%"),
            "evidence_strength": def_res.get("evidence_strength", "8.0/10"),
        })

        emit("SYNTHESIS", f"Synthesizing 8-point brief for Anomaly {idx}: {metric}", {"index": idx})
        report_8_point, prov_synth = synthesize_anomaly_report(
            company_name=company_name,
            ticker=clean_ticker,
            anomaly=anomaly,
            key_numbers=key_numbers,
            evidence_items=evidence_items,
            attacker_result=atk_res,
            defender_result=def_res,
            dossier=dossier,
            model=active_model,
        )
        last_provider = prov_synth

        investigated_anomalies.append({
            "index": idx,
            "metric": metric,
            "severity": anomaly.get("severity", 5.0),
            "report": report_8_point,
        })
        emit("ANOMALY_COMPLETE", f"Completed Anomaly {idx}: {metric}", {"index": idx})

    emit("EXPORT", f"Generating PDF report for {clean_ticker}")
    pdf_file = str(base_dir / "report.pdf")
    generate_pdf_report(
        output_path=pdf_file,
        company=company_name,
        ticker=clean_ticker,
        investigated_anomalies=investigated_anomalies,
        indicators=indicators,
    )

    first_discovery = investigated_anomalies[0]["report"]["discovery"] if investigated_anomalies else ""

    result_data = {
        "run_id": run_id,
        "ticker": clean_ticker,
        "company_name": company_name,
        "hypothesis": hypothesis or first_discovery,
        "anomalies_requested": anomaly_count,
        "anomalies_investigated_count": len(investigated_anomalies),
        "investigated_anomalies": investigated_anomalies,
        "primary_discovery": first_discovery,
        "provider": last_provider,
        "provider_used": last_provider,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "indicators": indicators,
        "evidence_items": evidence_items,
        "evidence_count": len(evidence_items),
        "pdf_path": pdf_file,
        "status": "COMPLETED",
    }

    run_file = base_dir / "run.json"
    with open(run_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    emit("DONE", f"Investigation complete for {clean_ticker}", {"run_id": run_id})

    return result_data
