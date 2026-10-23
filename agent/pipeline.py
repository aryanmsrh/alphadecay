import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.attacker import Attacker
from agent.defender import Defender
from agent.finder import Finder
from agent.llm import LLM
from agent.prompts import (
    SYNTHESIS_SYSTEM_PROMPT,
    build_synthesis_prompt,
    format_numbers_bullets,
)
from config import OLLAMA_MODEL


def build_deterministic_numbers(
    anomaly: Dict[str, Any],
    peer_benchmarks: Optional[List[str]] = None,
) -> List[str]:
    raw_bullets = anomaly.get("numbers_bullets", [])
    if not raw_bullets or not isinstance(raw_bullets, list):
        raise ValueError(f"Anomaly '{anomaly.get('metric')}' is missing required 'numbers_bullets'")

    bullets: List[str] = []
    for b in raw_bullets:
        clean_b = str(b).strip()
        if clean_b and clean_b not in bullets:
            bullets.append(clean_b)

    if not bullets:
        raise ValueError(f"Anomaly '{anomaly.get('metric')}' is missing required 'numbers_bullets'")

    if peer_benchmarks:
        for pb in peer_benchmarks:
            line = f"Sector Peer Benchmark: {pb}"
            if line not in bullets and not any(pb in b for b in bullets):
                bullets.append(line)

    return bullets


def build_deterministic_evidence(evidence_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    if not evidence_items:
        raise RuntimeError("Zero evidence items provided to build_deterministic_evidence")

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
        raise RuntimeError("Zero valid evidence URLs extracted from evidence items")

    return clean_list


def synthesize_anomaly_report(
    company_name: str,
    ticker: str,
    anomaly: Dict[str, Any],
    evidence_items: List[Dict[str, Any]],
    attacker_result: Dict[str, Any],
    defender_result: Dict[str, Any],
    key_numbers: Optional[List[Dict[str, Any]]] = None,
    dossier: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    event_callback: Optional[Callable[..., None]] = None,
) -> Tuple[Dict[str, Any], str]:
    metric = anomaly.get("metric", "Financial Metric")
    multi_quarter_trajectory = anomaly.get("multi_quarter_trajectory", "")
    peer_benchmarks = dossier.get("peer_benchmarks", []) if dossier else []

    numbers_list = build_deterministic_numbers(anomaly, peer_benchmarks)
    evidence_clean = build_deterministic_evidence(evidence_items)

    numbers_text = format_numbers_bullets(numbers_list)
    atk_verdict = str(attacker_result.get("verdict", "") or attacker_result.get("hypothesis", "")).strip()
    def_counter = str(defender_result.get("counterargument", "") or defender_result.get("hypothesis", "")).strip()

    prompt = build_synthesis_prompt(
        company_name=company_name,
        ticker=ticker,
        metric=metric,
        multi_quarter_trajectory=multi_quarter_trajectory,
        numbers_text=numbers_text,
        attacker_verdict=atk_verdict,
        defender_counterargument=def_counter,
    )
    system = SYNTHESIS_SYSTEM_PROMPT
    llm = LLM(model=model)
    parsed, provider = llm.generate_json(
        prompt,
        system=system,
        event_callback=event_callback,
        label=f"Editorial Synthesis ({metric})",
    )
    if isinstance(parsed, dict) and "json" in parsed and isinstance(parsed["json"], dict):
        parsed = parsed["json"]

    discovery = str(parsed.get("discovery", "") or parsed.get("the_discovery", "")).strip()
    why_matters = parsed.get("why_it_matters", [])
    if isinstance(why_matters, str):
        why_matters = [why_matters]
    elif not isinstance(why_matters, list):
        why_matters = []
    why_matters = [str(b).strip() for b in why_matters if str(b).strip()]

    timeline_raw = parsed.get("timeline", [])
    if isinstance(timeline_raw, list):
        timeline_list = [str(b).strip().lstrip("-•* ").strip() for b in timeline_raw if str(b).strip()]
    elif isinstance(timeline_raw, str):
        lines = [line.strip().lstrip("-•* ").strip() for line in timeline_raw.split("\n") if line.strip()]
        timeline_list = lines if lines else [timeline_raw.strip()]
    else:
        timeline_list = []

    if not discovery or not why_matters or not timeline_list:
        raise KeyError(f"LLM synthesis missing required field: {parsed}")

    atk_strength = str(attacker_result.get("evidence_strength", "")).strip()
    atk_conf = str(attacker_result.get("confidence", "")).strip()

    def_fals = str(defender_result.get("falsification_condition", "")).strip()
    def_strength = str(defender_result.get("evidence_strength", "")).strip()
    def_conf = str(defender_result.get("confidence", "")).strip()

    strength_bullets = [
        f"Attacker ({atk_conf}): {atk_strength}",
        f"Defender ({def_conf}): {def_strength}",
    ]

    final_report = {
        "discovery": discovery,
        "why_it_matters": why_matters,
        "evidence": evidence_clean,
        "timeline": timeline_list,
        "numbers": numbers_list,
        "attacker": {
            "verdict": atk_verdict,
            "evidence_strength": atk_strength,
            "confidence": atk_conf,
        },
        "defender": {
            "counterargument": def_counter,
            "falsification_condition": def_fals,
            "evidence_strength": def_strength,
            "confidence": def_conf,
        },
        "strength": strength_bullets,
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
    execution_events: List[Dict[str, Any]] = []

    def emit(
        step_or_dict: Any,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        if isinstance(step_or_dict, dict):
            evt = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **step_or_dict,
            }
        else:
            evt = {
                "step": str(step_or_dict),
                "message": str(message or ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(data or {}),
            }
        execution_events.append(evt)
        if event_callback:
            event_callback(evt)

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

    emit("INIT", f"Targeting {clean_ticker} via {active_model} ({provider_label})", {
        "model": active_model,
        "provider": active_provider,
        "provider_label": provider_label,
        "ticker": clean_ticker,
    })
    emit("INGEST", f"Ingesting statutory filings, annual balance sheets, and concall transcripts for {clean_ticker}", {
        "ticker": clean_ticker,
    })
    finder = Finder()
    dossier = finder.gather_company_dossier(clean_ticker)
    company_name = dossier["company_name"]
    indicators = dossier["indicators"]
    key_numbers = dossier["key_numbers"]
    evidence_items = dossier["evidence_items"]
    all_anomalies = dossier.get("anomalies", [])
    if not all_anomalies:
        raise RuntimeError(f"No statistical anomalies detected in financial statements for {clean_ticker}")

    target_anomalies = all_anomalies[:anomaly_count]

    emit("ANALYTICS", f"Financial analysis complete: identified {len(all_anomalies)} statistical anomalies across filings", {
        "company_name": company_name,
        "ticker": clean_ticker,
        "indicators": indicators,
        "anomalies": target_anomalies,
        "total_anomalies": len(all_anomalies),
    })

    attacker = Attacker(model=active_model)
    defender = Defender(model=active_model)
    investigated_anomalies: List[Dict[str, Any]] = []
    last_provider = active_model

    for idx, anomaly in enumerate(target_anomalies, start=1):
        metric = anomaly.get("metric", f"Anomaly #{idx}")
        emit("ANOMALY_START", f"Examining Anomaly {idx}/{len(target_anomalies)}: {metric}", {
            "index": idx,
            "metric": metric,
            "severity": anomaly.get("severity", 5.0),
            "multi_quarter_trajectory": anomaly.get("multi_quarter_trajectory", ""),
            "numbers_bullets": anomaly.get("numbers_bullets", []),
        })

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
            "confidence": atk_res.get("confidence", ""),
            "evidence_strength": atk_res.get("evidence_strength", ""),
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
            "confidence": def_res.get("confidence", ""),
            "evidence_strength": def_res.get("evidence_strength", ""),
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
            event_callback=emit,
        )
        last_provider = prov_synth

        investigated_anomalies.append({
            "index": idx,
            "metric": metric,
            "severity": anomaly.get("severity", 5.0),
            "report": report_8_point,
        })
        emit("ANOMALY_COMPLETE", f"Completed Anomaly {idx}: {metric}", {"index": idx})

    first_discovery = investigated_anomalies[0]["report"]["discovery"] if investigated_anomalies else ""

    emit("DONE", f"Investigation complete for {clean_ticker}", {"run_id": run_id})

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
        "events": execution_events,
        "status": "COMPLETED",
    }

    run_file = base_dir / "run.json"
    with open(run_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    return result_data
