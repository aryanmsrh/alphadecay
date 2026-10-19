import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
from agent.state import InvestigationState
from agent.llm_provider import central_provider
from agent.evidence import EvidenceRecord, EvidenceVault, MaterialClaim, CitationValidationResult
from agent.courtroom import (
    ForensicReportSchema, AdjudicationVerdict, Hypothesis, HypothesisType,
    DataSufficiency, migrate_legacy_verdict
)
from engine.forensics import ForensicEngine
from engine.periods import PeriodAligner, ReportingPeriod
from ingestion.web_search import TavilySearchClient
from ingestion.screener import ScreenerScraper
from ingestion.concall_harvester import ConcallHarvester
from config import PEER_MAPPING, MAX_ANOMALIES_TO_INVESTIGATE

search_client = TavilySearchClient()
screener_scraper = ScreenerScraper()
concall_harvester = ConcallHarvester()


def anomaly_triage_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 1: Evaluates prioritized anomalies flagged by deterministic math sandbox.
    Supports a genuine NO_MATERIAL_ANOMALY_DETECTED state without fabricating dummy candidates.
    Selects candidate at state['current_anomaly_index'].
    """
    anomalies = state.get("anomalies", [])
    current_idx = state.get("current_anomaly_index", 0)
    no_anomaly = state.get("no_material_anomaly", False) or len(anomalies) == 0

    if no_anomaly:
        print("\n" + "=" * 70)
        print("[Node 1: Anomaly Triage] Zero Material Anomalies Detected.")
        print("  All financial metrics and credit velocity indicators within normal screening thresholds.")
        print("  Routing to compiler for verified normal baseline synthesis.")
        print("=" * 70)
        log_entry = "[Node 1: Anomaly Triage] Zero material anomalies flagged. Baseline normal state active."
        return {
            "selected_anomaly": None,
            "no_material_anomaly": True,
            "logs": state.get("logs", []) + [log_entry]
        }

    idx = min(current_idx, len(anomalies) - 1)
    selected = anomalies[idx]

    print("\n" + "=" * 70)
    print(f"[Node 1: Anomaly Triage] Candidate #{idx + 1} of {len(anomalies)} Selected:")
    print(f"  • Metric:      {selected.get('metric_name')}")
    print(f"  • Period:      {selected.get('period')}")
    print(f"  • Basis:       {selected.get('comparison_basis', 'YoY')}")
    print(f"  • Delta:       {selected.get('delta')} {selected.get('unit', '')} ({selected.get('direction', 'adverse')})")
    print(f"  • Priority:    {selected.get('severity_score')}")
    print(f"  • Description: {selected.get('description')}")
    print("=" * 70)

    log_entry = (
        f"[Node 1: Anomaly Triage] Candidate #{idx + 1}: "
        f"'{selected.get('metric_name')}' in {selected.get('period')} (Delta: {selected.get('delta')})"
    )

    return {
        "selected_anomaly": selected,
        "no_material_anomaly": False,
        "logs": state.get("logs", []) + [log_entry]
    }


def triage_router(state: InvestigationState) -> str:
    """
    Routes directly to compiler if no material anomaly was detected by the math sandbox,
    bypassing hypothesis generation, external retrieval, and adversarial debate.
    """
    if state.get("no_material_anomaly") or not state.get("selected_anomaly"):
        return "bypass_to_compiler"
    return "proceed_to_hypotheses"


def hypothesis_generator_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 2: Formulates competing, falsifiable hypotheses.
    Considers multiple classes of explanations (operational, pricing/mix, seasonality, timing,
    working capital, input costs, restatements) rather than assuming guilt.
    """
    if state.get("no_material_anomaly") or state.get("selected_anomaly") is None:
        return {
            "competing_hypotheses": [],
            "adverse_hypothesis": None,
            "benign_hypothesis": None,
            "logs": state.get("logs", []) + ["[Node 2: Hypothesis Generator] Bypassed (no material anomaly)."]
        }

    anomaly = state.get("selected_anomaly", {})
    ticker = state.get("ticker", "COMPANY")
    company_name = state.get("company_name", ticker)
    metrics = state.get("computed_metrics", {})

    prompt = f"""
You are an objective institutional forensic financial researcher analyzing {company_name} ({ticker}).
The quantitative math sandbox detected this audited financial divergence:
- Metric Name: {anomaly.get('metric_name')}
- Period: {anomaly.get('period')} ({anomaly.get('comparison_basis', 'YoY')})
- Quantitative Delta: {anomaly.get('delta')} {anomaly.get('unit', '')} ({anomaly.get('direction', 'adverse')})
- Context: {anomaly.get('description')}
- Key Deterministic Ratios: Canonical DSRI: {metrics.get('beneish_dsri', 'N/A')}, Margin Wedge: {metrics.get('margin_wedge_bps', 'N/A')} bps, Expense-to-Sales Shift: {metrics.get('distribution_drag_bps', 'N/A')} bps

Mandate: Formulate balanced, testable competing hypotheses across these explanation classes:
1. Operational / Product-Mix / Seasonal / Working Capital Timing (Benign / Non-adverse)
2. Structural / Channel Pressure / Disclosed Stress / Aggressive Terms (Adverse, if supported by the data)

Requirements:
- Do NOT assume misconduct, fraud, or channel stuffing unless the quantitative divergence specifically indicates it.
- State clear testable predictions that would distinguish the explanations.
- Define an objective falsification condition (e.g. normalization across subsequent reporting cycles).

Format your response strictly as JSON:
{{
  "adverse_hypothesis": "1-2 sentence evidence-focused adverse or operational stress explanation",
  "benign_hypothesis": "1-2 sentence operational, seasonal, supply chain, or channel-mix explanation",
  "discriminating_prediction": "Specific disclosure or metric trajectory that separates the two hypotheses",
  "falsification_condition": "Exact future metric normalization condition that disproves the adverse claim"
}}
Output ONLY valid JSON. Zero preamble.
"""
    system = "You are an impartial forensic financial researcher formulating balanced, falsifiable hypotheses."
    resp = central_provider.generate_text(prompt, system=system, task_name="hypothesis_generation", json_mode=True)
    
    parsed = central_provider.extract_json_block(resp.text) or {}
    adverse = parsed.get("adverse_hypothesis", f"{company_name} experienced working capital expansion across distribution channels.")
    benign = parsed.get("benign_hypothesis", f"{company_name}'s movement reflects operational timing, channel mix adjustments, or seasonal factors.")
    
    print("\n" + "-" * 70)
    print(f"[Node 2: Competing Hypotheses Generated via {resp.provider_used.upper()} ({resp.model_name})]:")
    print(f"  • Adverse / Stress Hypothesis: {adverse}")
    print(f"  • Benign / Operational Hypothesis: {benign}")
    print("-" * 70)

    log_entry = f"[Node 2: Hypothesis Generator] Adverse: {adverse} | Benign: {benign}"

    return {
        "adverse_hypothesis": adverse,
        "benign_hypothesis": benign,
        "competing_hypotheses": [
            {"type": "ADVERSE_STRUCTURAL", "claim": adverse},
            {"type": "OPERATIONAL_CHANGE", "claim": benign}
        ],
        "provider_metadata": {**state.get("provider_metadata", {}), "hypothesis_node": resp.model_dump()},
        "logs": state.get("logs", []) + [log_entry]
    }


def evidence_harvester_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 3: Harvests exchange concall transcripts and targeted evidence.
    CRITICAL INVARIANT: Never creates a fabricated statutory fallback from the anomaly description.
    Registers all evidence into the EvidenceVault with strict provenance metadata.
    """
    if state.get("no_material_anomaly") or state.get("selected_anomaly") is None:
        return {
            "prosecution_evidence": [],
            "contradiction_analysis": None,
            "logs": state.get("logs", []) + ["[Node 3: Evidence Harvester] Bypassed (no material anomaly)."]
        }

    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    anomaly = state.get("selected_anomaly", {})
    adverse_thesis = state.get("adverse_hypothesis", "")
    raw_fin = state.get("raw_financials", {})
    cutoff_str = state.get("cutoff_date")
    cutoff_d = date.fromisoformat(cutoff_str) if cutoff_str else None

    vault = EvidenceVault(cutoff_date=cutoff_d)
    evidence_records: List[Dict[str, Any]] = []

    # 1. Statutory Exchange Concall Transcript Extraction
    transcripts = raw_fin.get("concall_transcripts", [])
    if transcripts:
        pdf_url = transcripts[0].get("url", "")
        print(f"\n[Node 3: Evidence Harvester] Inspecting statutory earnings call transcript at:\n  --> {pdf_url}")
        concall_excerpts = concall_harvester.harvest_transcript(
            pdf_url, max_excerpts=2, target_period=anomaly.get("period")
        )
        for idx, ce in enumerate(concall_excerpts, 1):
            rec = EvidenceRecord(
                evidence_id=f"EV-CONCALL-{idx}",
                source_title=f"Exchange Earnings Call Transcript ({', '.join(ce.get('matched_keywords', []))})",
                source_url=ce.get("source_url", pdf_url),
                source_type="concall_transcript",
                publisher="BSE / NSE Statutory Filing",
                relevant_period=anomaly.get("period"),
                source_location=f"Page {ce.get('page_number', 'Q&A')}, Speaker: {ce.get('speaker', 'Unattributed')}",
                supporting_excerpt=ce.get("excerpt", ""),
                extracted_fact=f"Executive / analyst commentary on distribution and terms: {ce.get('matched_keywords')}",
                credibility_tier=2
            )
            if vault.register_evidence(rec):
                evidence_records.append(rec.model_dump())
        if concall_excerpts:
            print(f"  [✓] Verified & extracted {len(concall_excerpts)} dialogue blocks from exchange filing.")

    # 2. Targeted Web Evidence
    metric_name_clean = anomaly.get("metric_name", "").replace("Divergence", "").replace("Residual", "").strip()
    query = f"{company_name} {ticker} {metric_name_clean} {anomaly.get('period')}"
    search_results = search_client.search(query, max_results=2)
    for idx, item in enumerate(search_results, 1):
        rec = EvidenceRecord(
            evidence_id=f"EV-SEARCH-{idx}",
            source_title=item.get("title", "Financial Press Report"),
            source_url=item.get("url", ""),
            source_type="news",
            publisher="Financial Press",
            relevant_period=anomaly.get("period"),
            supporting_excerpt=item.get("content", ""),
            extracted_fact=item.get("title", ""),
            credibility_tier=4
        )
        if vault.register_evidence(rec):
            evidence_records.append(rec.model_dump())

    # ZERO synthetic statutory fallback records: if no external documents found, state so honestly
    if not evidence_records:
        print("  [!] Notice: No qualifying external documents found. Qualitative evidence marked absent.")

    # Cross-examine management commentary against quantitative numbers
    contradiction_analysis = None
    resp_dump = {}
    if evidence_records:
        analysis_prompt = f"""
Company: {company_name} ({ticker})
Adverse Thesis: {adverse_thesis}
Benign Thesis: {state.get('benign_hypothesis')}
Quantitative Reality: {anomaly.get('description')} (Delta: {anomaly.get('delta')} {anomaly.get('unit', '')})

Harvested Qualitative Evidence & Statutory Excerpts:
{json.dumps(evidence_records, indent=2, default=str)}

Task: In 2 to 3 concise bullet points, evaluate whether management commentary corroborates, explains, or contradicts the quantitative observations.
"""
        system = "You are a forensic analyst identifying relationships between management commentary and statutory accounting figures."
        resp = central_provider.generate_text(analysis_prompt, system=system, task_name="evidence_contradiction_analysis")
        contradiction_analysis = resp.text.strip()
        resp_dump = resp.model_dump()

        print("\n" + "-" * 70)
        print(f"[Node 3: Evidence Harvester] Harvested {len(evidence_records)} Verified Provenance Records:")
        for idx, e in enumerate(evidence_records, 1):
            print(f"  [{idx}] {e.get('source_title')} ({e.get('source_type')})\n      URL: {e.get('source_url')}")
        print(f"\n[Contradiction Analysis via {resp.provider_used.upper()}]:\n{contradiction_analysis}")
        print("-" * 70)

    log_entry = f"[Node 3: Evidence Harvester] Harvested {len(evidence_records)} verified external sources."

    return {
        "prosecution_evidence": evidence_records,
        "contradiction_analysis": contradiction_analysis,
        "provider_metadata": {**state.get("provider_metadata", {}), "evidence_node": resp_dump},
        "logs": state.get("logs", []) + [log_entry]
    }


def peer_triangulation_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 4: Evaluates competitor filings with synchronous period alignment.
    Discloses period mismatches, avoids zero-substitution for failed peers,
    and computes idiosyncratic spread deterministically.
    """
    if state.get("no_material_anomaly") or state.get("selected_anomaly") is None:
        return {
            "peer_evidence": [],
            "logs": state.get("logs", []) + ["[Node 4: Peer Triangulation] Bypassed (no material anomaly)."]
        }

    ticker = state.get("ticker", "COMPANY").upper()
    anomaly = state.get("selected_anomaly", {})
    metric_type = anomaly.get("metric_type", "debtor_days")
    unit = anomaly.get("unit", "d")
    target_delta = float(anomaly.get("delta", 0.0))
    cutoff_str = state.get("cutoff_date")
    cutoff_d = date.fromisoformat(cutoff_str) if cutoff_str else None

    # Retrieve peer universe
    peers = [p for p in PEER_MAPPING.get(ticker, ["BRITANNIA", "TATACONSUM", "DABUR"]) if p != ticker][:2]

    peer_evidence = []
    peer_deltas = []

    print("\n" + "-" * 70)
    print(f"[Node 4: Peer Triangulation with Period Alignment ({anomaly.get('metric_name')}):")

    for peer in peers:
        try:
            p_data = screener_scraper.fetch_company_data(peer)
            p_name = p_data.get("company_name", peer)
            p_summary = ForensicEngine.audit_company(p_data, cutoff_date=cutoff_d)

            p_val = None
            summary_text = ""

            if metric_type == "expense_residual_divergence":
                p_q = p_summary.quarters_analyzed[-1] if p_summary.quarters_analyzed else None
                p_sales_g = p_summary.sales_growth_yoy.get(p_q)
                p_res = p_summary.expense_adjusted_residual.get(p_q)
                if p_sales_g is not None and p_res is not None:
                    p_val = round(p_sales_g - p_res, 2)
                    summary_text = f"{p_name} ({peer}) Sales YoY ({p_sales_g}%) vs Expense Residual ({p_res}%) spread: {p_val}%."
            elif metric_type == "margin_wedge":
                if p_summary.margin_wedge_bps is not None:
                    p_val = float(p_summary.margin_wedge_bps)
                    summary_text = f"{p_name} ({peer}) operating margin wedge: {p_val} bps."
            elif metric_type == "cfo_conversion":
                if p_summary.cfo_to_operating_profit is not None:
                    p_cfo = round(p_summary.cfo_to_operating_profit * 100.0, 1)
                    p_val = round(max(0.0, 70.0 - p_cfo), 1)
                    summary_text = f"{p_name} ({peer}) CFO conversion deficit: {p_val}% (CFO/Operating Profit: {p_cfo}%)."
            else:  # debtor_days / default
                days_list = list(p_summary.debtor_days.values())
                if len(days_list) >= 2:
                    b_idx = -5 if len(days_list) >= 5 else 0
                    p_val = round(days_list[-1] - days_list[b_idx], 1)
                    summary_text = f"{p_name} ({peer}) statutory debtor days delta: {p_val}d over trailing cycle."

            if p_val is not None:
                peer_deltas.append(p_val)
                print(f"  • {p_name} ({peer}): Metric Delta = {p_val}{unit}")
                peer_evidence.append({
                    "peer": p_name,
                    "ticker": peer,
                    "url": f"https://www.screener.in/company/{peer}/consolidated/",
                    "metric_value": p_val,
                    "unit": unit,
                    "summary": summary_text
                })
            else:
                print(f"  • {p_name} ({peer}): Insufficient data to compute comparable metric.")

        except Exception as e:
            # Do NOT append 0.0! A failed fetch must remain missing.
            print(f"  [!] Failed to evaluate peer '{peer}': {e}. Excluded from peer median.")

    relative_spread = None
    peer_median = None
    if peer_deltas:
        peer_median = float(np.median(peer_deltas))
        relative_spread = round(target_delta - peer_median, 2)
        spread_formatted = f"{relative_spread:+.2f}{unit}"
        print(f"\n[Peer Spread Calculation]:")
        print(f"  • Target ({ticker}):    {target_delta}{unit}")
        print(f"  • Peer Median ({len(peer_deltas)} peers): {peer_median}{unit}")
        print(f"  • Idiosyncratic Spread: {spread_formatted}")
    else:
        print("\n[Peer Spread Calculation]: Peer data insufficient to establish reliable sector median.")

    print("-" * 70)

    log_entry = (
        f"[Node 4: Peer Triangulation] Target: {target_delta}{unit} | "
        f"Peer Median: {peer_median if peer_median is not None else 'N/A'}{unit} -> "
        f"Spread: {relative_spread if relative_spread is not None else 'N/A'}{unit}"
    )

    return {
        "peer_evidence": peer_evidence,
        "computed_metrics": {**state.get("computed_metrics", {}), "peer_spread_days": relative_spread},
        "logs": state.get("logs", []) + [log_entry]
    }


def adversarial_critic_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 5: Adversarial Review & Independent Adjudication.
    Generates Prosecution and Defense cases, then has the Adjudicator evaluate the underlying evidence.
    Allowed verdicts: SUPPORTED, REFUTED, NOT_ESTABLISHED.
    Failure to falsify is NEVER treated as confirmation.
    """
    if state.get("no_material_anomaly") or state.get("selected_anomaly") is None:
        return {
            "is_falsified": False,
            "evidence_strength": "SUPPORTED",
            "logs": state.get("logs", []) + ["[Node 5: Adversarial Critic] Bypassed (no material anomaly)."]
        }

    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    adverse_thesis = state.get("adverse_hypothesis", "")
    benign_thesis = state.get("benign_hypothesis", "")
    anomaly = state.get("selected_anomaly", {})
    peer_ev = state.get("peer_evidence", [])
    prosecution_ev = state.get("prosecution_evidence", [])
    metrics = state.get("computed_metrics", {})

    courtroom_prompt = f"""
You are presiding over an adversarial financial court examining {company_name} ({ticker}).
Quantitative Anomaly Under Review:
- Metric: {anomaly.get('metric_name')}
- Period: {anomaly.get('period')} ({anomaly.get('comparison_basis', 'YoY')})
- Delta: {anomaly.get('delta')} {anomaly.get('unit', '')} ({anomaly.get('direction', 'adverse')})
- Context: {anomaly.get('description')}
- Deterministic Ratios: Canonical DSRI: {metrics.get('beneish_dsri', 'N/A')} | Margin Wedge: {metrics.get('margin_wedge_bps', 'N/A')} bps | Peer Spread: {metrics.get('peer_spread_days', 'N/A')}

Competing Hypotheses:
1. ADVERSE CASE: {adverse_thesis}
2. BENIGN / ALTERNATIVE CASE: {benign_thesis}

Harvested Evidence & Transcripts:
{json.dumps(prosecution_ev, indent=2, default=str)}

Peer Triangulation Benchmarks:
{json.dumps(peer_ev, indent=2)}

Adjudication Mandate:
1. Prosecution: Construct strongest evidence-based argument for adverse structural stress.
2. Defense: Construct strongest plausible alternative explanation (macro, operational, festive, mix, peer parity).
3. Adjudicator: Evaluate BOTH arguments against the raw evidence and calculations.
   - Set VERDICT: "REFUTED" if sufficient, relevant evidence contradicts the hypothesis or a predefined falsification condition is met.
   - Set VERDICT: "SUPPORTED" if available evidence affirmatively corroborates the company-specific causal mechanism meeting evidentiary standard.
   - Set VERDICT: "NOT_ESTABLISHED" if the available evidence does not justify either affirmative conclusion (materially conflicting evidence, untested hypothesis, or speculative explanation).
   - Set DATA_SUFFICIENCY: "SUFFICIENT" (critical disclosures present) | "LIMITED" (partial disclosures) | "INSUFFICIENT" (essential data missing).
   - EPISTEMIC RULE: Failure to disprove the adverse hypothesis is NOT confirmation. Never use obsolete "INCONCLUSIVE".

Format strictly as JSON:
{{
  "prosecution_case": "Strongest adverse argument",
  "defense_case": "Strongest benign alternative",
  "verdict": "SUPPORTED | REFUTED | NOT_ESTABLISHED",
  "data_sufficiency": "SUFFICIENT | LIMITED | INSUFFICIENT",
  "evidence_strength": "High | Moderate | Low",
  "adjudication_rationale": "2-3 sentences explaining the exact evidence driving the verdict",
  "falsification_condition": "Exact future metric normalization condition that disproves adverse claim",
  "next_investigation_step": "Specific follow-up observation or document needed to resolve remaining uncertainty"
}}
Output ONLY valid JSON. Zero preamble.
"""
    system = "You are an impartial, highly rigorous financial court adjudicator. Never assume guilt without evidence. Never use obsolete 'INCONCLUSIVE'."
    resp = central_provider.generate_text(courtroom_prompt, system=system, task_name="adversarial_adjudication", json_mode=True)
    
    parsed = central_provider.extract_json_block(resp.text) or {}
    raw_verdict = parsed.get("verdict", "NOT_ESTABLISHED").upper()
    verdict = migrate_legacy_verdict(raw_verdict)
    data_suff = parsed.get("data_sufficiency", "SUFFICIENT").upper()
    if data_suff not in ("SUFFICIENT", "LIMITED", "INSUFFICIENT"):
        data_suff = "LIMITED" if verdict == "NOT_ESTABLISHED" else "SUFFICIENT"

    strength = parsed.get("evidence_strength", "Moderate")
    prosecution_case = parsed.get("prosecution_case", adverse_thesis)
    defense_case = parsed.get("defense_case", benign_thesis)
    rationale = parsed.get("adjudication_rationale", "Evidence does not justify an affirmative conclusion.")
    falsification_condition = parsed.get("falsification_condition", f"Disproven if {company_name} normalizes credit velocity across >=2 consecutive reporting cycles.")
    next_step = parsed.get("next_investigation_step", "Inspect subsequent quarterly disclosures for metric normalization.")

    is_falsified = (verdict == "REFUTED")

    print("\n" + "-" * 70)
    print(f"[Node 5: Adversarial Review & Adjudication via {resp.provider_used.upper()} ({resp.model_name})]:")
    print(f"  • Prosecution Case: {prosecution_case[:180]}...")
    print(f"  • Defense Case:     {defense_case[:180]}...")
    print(f"  • Adjudication Verdict: [{verdict}] | Rating: {strength}")
    print(f"  • Rationale: {rationale}")
    print("-" * 70)

    log_entry = f"[Node 5: Adjudication] Verdict: {verdict} | Evidence Strength: {strength} | Rationale: {rationale}"

    # Record completed candidate evaluation
    completed_candidate = {
        "candidate": anomaly,
        "adverse_hypothesis": adverse_thesis,
        "benign_hypothesis": benign_thesis,
        "verdict": verdict,
        "rationale": rationale,
        "falsification_condition": falsification_condition
    }
    completed_list = state.get("completed_investigations", []) + [completed_candidate]

    return {
        "is_falsified": is_falsified,
        "falsification_reason": defense_case if is_falsified else None,
        "evidence_strength": verdict,
        "data_sufficiency": data_suff,
        "adjudication_verdict": verdict,
        "adversarial_arguments": {
            "prosecution_case": prosecution_case,
            "defense_case": defense_case,
            "falsification_condition": falsification_condition,
            "next_investigation_step": next_step
        },
        "adjudication": {
            "verdict": verdict,
            "data_sufficiency": data_suff,
            "rationale": rationale,
            "falsification_condition": falsification_condition,
            "next_investigation_step": next_step
        },
        "completed_investigations": completed_list,
        "provider_metadata": {**state.get("provider_metadata", {}), "adjudication_node": resp.model_dump()},
        "logs": state.get("logs", []) + [log_entry]
    }


def reflection_router(state: InvestigationState) -> str:
    """
    Conditional Edge: Checks if additional candidates should be examined.
    Enforces candidate budget (MAX_ANOMALIES_TO_INVESTIGATE) and loop termination.
    """
    if state.get("no_material_anomaly"):
        return "proceed"

    is_falsified = state.get("is_falsified", False)
    current_idx = state.get("current_anomaly_index", 0)
    iter_count = state.get("iteration_count", 0)
    max_budget = state.get("max_anomalies_to_investigate", MAX_ANOMALIES_TO_INVESTIGATE)
    anomalies = state.get("anomalies", [])

    next_idx = current_idx + 1

    print("\n" + "=" * 70)
    if is_falsified and next_idx < len(anomalies) and iter_count + 1 < max_budget:
        print(f"[Reflection Router] HYPOTHESIS REFUTED BY ADJUDICATION!")
        print(f"  • Advancing to candidate #{next_idx + 1} of {len(anomalies)}: '{anomalies[next_idx].get('metric_name')}'")
        print("  --> LOOPING BACK to Node 1 (Anomaly Triage)...")
        print("=" * 70)
        # Advance state
        state["current_anomaly_index"] = next_idx
        state["iteration_count"] = iter_count + 1
        return "loop_back"

    curr_verdict = state.get("adjudication_verdict") or state.get("evidence_strength") or "NOT_ESTABLISHED"
    print(f"[Reflection Router] ADJUDICATION COMPLETE (Verdict: {curr_verdict}). Proceeding to Compiler.")
    print("=" * 70)
    return "proceed"


def compiler_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 6: Synthesizes final verified state into the mandatory 8-Point Forensic Schema.
    Strictly applies the DETERMINISTIC VALIDATION GATE before setting validation_passed = True.
    """
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    raw_fin = state.get("raw_financials", {})
    metrics = state.get("computed_metrics", {})
    no_anomaly = state.get("no_material_anomaly", False)

    # 1. Genuine No-Anomaly State Output
    if no_anomaly:
        quarters = state.get("computed_metrics", {}).get("debtor_days", {})
        latest_period = list(quarters.keys())[-1] if quarters else "Recent Trailing Quarters"
        discovery = {
            "finding_heading": "Zero Material Anomaly Detected",
            "1_The_Discovery": f"All audited financial metrics, working capital velocity, and credit indicators for {company_name} ({ticker}) are within normal operational variance.",
            "2_Why_It_Matters": [
                f"Statutory debtor days and working capital velocity remained stable across analyzed reporting periods.",
                f"Operating margins and cost ratios showed no material decoupling from top-line revenue growth.",
                f"Cash flow from operations is aligned with reported operating profitability without significant working capital absorption."
            ],
            "3_Evidence": [raw_fin.get("source_url", f"https://www.screener.in/company/{ticker}/consolidated/")],
            "4_Timeline": f"Trailing reporting periods ending {latest_period}.",
            "5_Numbers": f"Debtor days within variance | Margin wedge: None | Cash flow quality benchmark satisfied.",
            "6_Counterargument": "Operational variance and input-cost movements were absorbed within regular business operations.",
            "7_Falsification_Condition": f"Continuous monitoring across subsequent quarterly filings for emerging working capital divergence.",
            "8_Evidence_Strength": "SUPPORTED: Consistent with statutory disclosures across all analyzed reporting periods."
        }
        return {
            "final_discovery": discovery,
            "validation_passed": True,
            "validation_report": {"status": "PASS", "details": "No material anomaly state verified."},
            "logs": state.get("logs", []) + ["[Node 6: Compiler Node] Zero material anomaly finding validated."]
        }

    # 2. Anomaly Synthesis
    anomaly = state.get("selected_anomaly", {})
    adverse = state.get("adverse_hypothesis", "")
    defense_info = state.get("adversarial_arguments", {})
    adjudication = state.get("adjudication", {})
    prosecution = state.get("prosecution_evidence", [])

    verified_urls = list(dict.fromkeys(e.get("source_url") or e.get("url") for e in prosecution if (e.get("source_url") or e.get("url"))))
    if not verified_urls:
        verified_urls = [raw_fin.get("source_url", f"https://www.screener.in/company/{ticker}/consolidated/")]

    unit = anomaly.get("unit", "")
    peer_sp_raw = metrics.get('peer_spread_days')
    peer_sp_str = f"{peer_sp_raw:+.2f}{unit}" if peer_sp_raw is not None else "N/A"
    verdict = adjudication.get("verdict", state.get("adjudication_verdict", state.get("evidence_strength", "NOT_ESTABLISHED")))
    data_suff = adjudication.get("data_sufficiency", state.get("data_sufficiency", "SUFFICIENT"))
    rationale = adjudication.get("rationale", "")
    next_step = adjudication.get("next_investigation_step", "Monitor subsequent quarterly filings.")

    # Dynamic heading selection based on verdict and metric type
    finding_heading = "Verified Finding"
    if anomaly.get("is_heuristic"):
        finding_heading = "Quantitative Screening Signal"
    elif verdict == "SUPPORTED":
        finding_heading = "Verified Finding"
    elif verdict == "REFUTED":
        finding_heading = "Refuted Hypothesis"
    elif verdict == "NOT_ESTABLISHED":
        finding_heading = "Observed Fact (Causal Explanation Not Established)"

    synthesis_prompt = f"""
You are an institutional financial compiler synthesizing a calibrated forensic research note for {company_name} ({ticker}).
Quantitative Accounting Data:
- Metric: {anomaly.get('metric_name')}
- Period: {anomaly.get('period')} ({anomaly.get('comparison_basis', 'YoY')})
- Quantitative Delta: {anomaly.get('delta')} {anomaly.get('unit', '')} ({anomaly.get('direction', 'adverse')})
- Context: {anomaly.get('description')}
- Computed Ratios: Canonical DSRI = {metrics.get('beneish_dsri', 'N/A')}, Margin Wedge = {metrics.get('margin_wedge_bps', 'N/A')} bps, OPM Delta = {metrics.get('operating_margin_delta_bps', 'N/A')} bps, Peer Spread = {peer_sp_str}

Adjudication Outcome:
- Verdict: {verdict}
- Data Sufficiency: {data_suff}
- Adjudication Rationale: {rationale}
- Prosecution Argument: {defense_info.get('prosecution_case')}
- Defense Counterargument: {defense_info.get('defense_case')}
- Falsification Criteria: {defense_info.get('falsification_condition')}
- Next Investigation: {next_step}

Verified Sources (Cite ONLY from this list): {json.dumps(verified_urls)}

Epistemic Mandate:
- In "1_The_Discovery", state exactly 1 sentence stating the verified quantitative reality and calibrated verdict.
- NEVER use the word 'inconclusive' anywhere in the output.
- If the verdict is NOT_ESTABLISHED, explicitly distinguish the observed numerical reality from the unproven or refuted causal explanation.

Compile strictly into this JSON structure:
{{
  "finding_heading": "{finding_heading}",
  "1_The_Discovery": "Exactly 1 sentence stating the verified quantitative reality and calibrated verdict without using 'inconclusive'",
  "2_Why_It_Matters": [
    "Bullet 1 on business/channel implication",
    "Bullet 2 on cash conversion/working capital",
    "Bullet 3 on peer comparison"
  ],
  "3_Evidence": {json.dumps(verified_urls)},
  "4_Timeline": "Quarters over which divergence emerged",
  "5_Numbers": "Summary of exact calculation figures (Canonical DSRI, delta, margin wedge, peer spread)",
  "6_Counterargument": "Strongest alternative explanation from defense",
  "7_Falsification_Condition": "Exact future metric normalization that proves adverse claim wrong",
  "8_Evidence_Strength": "{verdict} (Data Sufficiency: {data_suff}): {rationale} Next Step: {next_step}"
}}
Output ONLY valid JSON. Zero preamble.
"""
    system = "You are an institutional financial compiler. Produce clean JSON strictly following the schema using verified data only. Never use the obsolete word 'inconclusive'."
    
    resp, report_obj = central_provider.generate_structured(
        prompt=synthesis_prompt,
        schema_model=ForensicReportSchema,
        system=system,
        task_name="report_synthesis"
    )

    discovery = report_obj.model_dump(by_alias=True)

    # 3. DETERMINISTIC VALIDATION GATE
    val_errors = []
    # Gate 1: Check evidence URLs
    cited_evidence = discovery.get("3_Evidence", [])
    for u in cited_evidence:
        if u not in verified_urls and u != raw_fin.get("source_url"):
            val_errors.append(f"Unregistered source cited in report: '{u}'")

    # Gate 2: Check for false volume growth claim if heuristic residual
    if anomaly.get("is_heuristic"):
        d_text = str(discovery.get("1_The_Discovery", "")).lower()
        if "volume growth" in d_text and "residual" not in d_text and "heuristic" not in d_text:
            val_errors.append("Heuristic expense residual improperly asserted as reported unit volume growth.")

    # Gate 3: Check debtor days direction (16 to 19 days is widening/worsening, never improvement)
    if anomaly.get("metric_type") == "debtor_days" and anomaly.get("delta", 0) > 0:
        d_text = str(discovery.get("1_The_Discovery", "")).lower()
        if "improved" in d_text or "acceleration" in d_text:
            val_errors.append("Debtor days elongation (positive delta) mischaracterized as an improvement.")

    # Gate 4: Zero tolerance for obsolete 'INCONCLUSIVE'
    raw_discovery_str = json.dumps(discovery).upper()
    if "INCONCLUSIVE" in raw_discovery_str:
        val_errors.append("Obsolete verdict 'INCONCLUSIVE' found in compiled discovery schema.")

    # Gate 5: Check operating margin delta sign agreement
    opm_delta = metrics.get("operating_margin_delta_bps")
    if opm_delta is not None and opm_delta < 0:
        d_str = str(discovery.get("1_The_Discovery", "")).lower()
        if "margin expansion" in d_str or "expanded by" in d_str:
            val_errors.append("Operating margin contraction mischaracterized as margin expansion.")

    validation_passed = len(val_errors) == 0
    val_report = {
        "status": "PASS" if validation_passed else "FAIL",
        "errors": val_errors,
        "verified_urls_count": len(verified_urls),
        "verdict": verdict,
        "data_sufficiency": data_suff
    }

    if not validation_passed:
        print(f"\n[Validation Gate Warning] Compiler validation failed with errors: {val_errors}")
    else:
        print("\n[Validation Gate Pass] All deterministic citation, direction, and consistency checks passed.")

    print("\n" + "-" * 70)
    print(f"[Node 6: Compiler Node] Mandatory 8-Point Forensic Schema Compiled via {resp.provider_used.upper()}:")
    for k, v in discovery.items():
        if isinstance(v, list):
            print(f"  • {k}:")
            for item in v:
                print(f"      - {item}")
        else:
            print(f"  • {k}: {v}")
    print("-" * 70)

    return {
        "final_discovery": discovery,
        "validation_passed": validation_passed,
        "validation_report": val_report,
        "provider_metadata": {**state.get("provider_metadata", {}), "compiler_node": resp.model_dump()},
        "logs": state.get("logs", []) + [f"[Node 6: Compiler Node] Compiled. Validation status: {val_report['status']}."]
    }
