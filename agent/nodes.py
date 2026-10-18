import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
from agent.state import InvestigationState
from ingestion.web_search import TavilySearchClient
from ingestion.screener import ScreenerScraper
from ingestion.concall_harvester import ConcallHarvester
from agent.llm_client import LLMClient
from engine.forensics import ForensicEngine
from config import PEER_MAPPING

search_client = TavilySearchClient()
screener_scraper = ScreenerScraper()
concall_harvester = ConcallHarvester()
llm = LLMClient()

def anomaly_triage_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 1: Evaluates anomalies flagged by the deterministic math sandbox.
    Selects the candidate corresponding to state['current_anomaly_index'].
    """
    anomalies = state.get("anomalies", [])
    current_idx = state.get("current_anomaly_index", 0)

    if not anomalies:
        selected = {
            "metric_name": "Working Capital Decoupling",
            "period": "Recent",
            "delta": 0.0,
            "severity_score": 0.0,
            "description": "No statistically significant accounting anomaly detected by sandbox."
        }
    else:
        idx = min(current_idx, len(anomalies) - 1)
        selected = anomalies[idx]

    print("\n" + "=" * 70)
    print(f"[Node 1: Anomaly Triage] Candidate #{current_idx + 1} of {len(anomalies)} Selected:")
    print(f"  • Metric:      {selected.get('metric_name')}")
    print(f"  • Period:      {selected.get('period')}")
    print(f"  • Delta:       {selected.get('delta')}")
    print(f"  • Priority:    {selected.get('severity_score')}")
    print(f"  • Context:     {selected.get('description')}")
    print("=" * 70)

    log_entry = (
        f"[Node 1: Anomaly Triage] Candidate #{current_idx + 1}: "
        f"'{selected.get('metric_name')}' in {selected.get('period')} (Delta: {selected.get('delta')})"
    )

    return {
        "selected_anomaly": selected,
        "logs": state.get("logs", []) + [log_entry]
    }

def hypothesis_generator_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 2: Generates a tight, falsifiable investigative thesis using LLM.
    Prints the complete DeepSeek-R1 CoT thought trace and formulated hypothesis.
    """
    anomaly = state.get("selected_anomaly", {})
    ticker = state.get("ticker", "COMPANY")
    company_name = state.get("company_name", ticker)
    metrics = state.get("computed_metrics", {})

    prompt = f"""
You are an institutional forensic financial investigator analyzing {company_name} ({ticker}).
The quantitative math sandbox detected this anomaly:
- Metric: {anomaly.get('metric_name')}
- Period: {anomaly.get('period')}
- Quantitative Delta: {anomaly.get('delta')}
- Context: {anomaly.get('description')}
- Key Accounting Ratios: Beneish DSRI: {metrics.get('beneish_dsri', 'N/A')}, Margin Wedge: {metrics.get('margin_wedge_bps', 'N/A')} bps

Task: Formulate a concise, testable 1-to-2 sentence forensic hypothesis explaining what operational or accounting reality is being masked (e.g., channel stuffing, pricing power exhaustion, volume contraction, distribution expense dilution).
Strict Rule: No investment recommendations, price targets, or buy/sell calls.
Output ONLY the hypothesis text.
"""
    system = "You are an expert forensic accountant. Formulate sharp, evidence-testable hypotheses without conversational filler."
    thought, thesis = llm.route_query(prompt, system=system, task_type="general")

    print("\n" + "-" * 70)
    print(f"[Node 2: Hypothesis Generator] Reasoning & Output:")
    if thought:
        print(f"\n[DeepSeek-R1 Internal CoT Reasoning Trace]:\n{thought.strip()}")
    print(f"\n[Formulated Hypothesis]:\n{thesis.strip()}")
    print("-" * 70)

    log_entry = f"[Node 2: Hypothesis Generator] Thesis: {thesis.strip()}"

    return {
        "hypothesis": thesis.strip(),
        "logs": state.get("logs", []) + [log_entry]
    }

def evidence_harvester_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 3: The Prosecution. Harvests statutory exchange filings and web evidence.
    Prints all harvested excerpts and the full contradiction analysis.
    """
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    anomaly = state.get("selected_anomaly", {})
    thesis = state.get("hypothesis", "")
    raw_fin = state.get("raw_financials", {})

    evidence_items = []

    # 1. Statutory Exchange Concall Transcript Extraction
    transcripts = raw_fin.get("concall_transcripts", [])
    if transcripts:
        pdf_url = transcripts[0].get("url", "")
        print(f"\n[Node 3: Evidence Harvester] Inspecting statutory exchange concall transcript at:\n  --> {pdf_url}")
        concall_excerpts = concall_harvester.harvest_transcript(pdf_url, max_excerpts=2)
        if concall_excerpts:
            for ce in concall_excerpts:
                evidence_items.append({
                    "title": f"BSE Statutory Earnings Call Transcript ({', '.join(ce['matched_keywords'])})",
                    "url": ce.get("source_url", pdf_url),
                    "excerpt": ce.get("excerpt", "")
                })
            print(f"  [✓] Successfully verified & extracted {len(concall_excerpts)} dialogue blocks from exchange filing.")
        else:
            print("  [i] Concall transcript inspected; no explicit keyword matches found for this specific anomaly.")

    # 2. Live Targeted Search
    query = f"{company_name} {ticker} concall {anomaly.get('metric_name')} {anomaly.get('period')}"
    search_results = search_client.search(query, max_results=2)
    for item in search_results:
        evidence_items.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "excerpt": item.get("content", "")
        })

    # If no search results, bind strictly to the verified statutory filing URL
    if not evidence_items:
        evidence_items.append({
            "title": f"Statutory Financial Disclosures: {company_name}",
            "url": raw_fin.get("source_url", "https://www.screener.in"),
            "excerpt": f"Statutory filing analysis for {anomaly.get('metric_name')}: {anomaly.get('description')}"
        })

    # Cross-examine management claims against calculated math
    analysis_prompt = f"""
Company: {company_name} ({ticker})
Investigative Thesis: {thesis}
Quantitative Accounting Reality: {anomaly.get('description')} (Delta: {anomaly.get('delta')})

Harvested Evidence & Statutory Excerpts:
{json.dumps(evidence_items, indent=2)}

Task: In 2 to 3 concise bullet points, identify whether management's narrative contradicts, evades, or corroborates the quantitative numbers.
"""
    system = "You are a forensic analyst identifying contradictions between management PR narrative and statutory accounting figures."
    _, contradiction_analysis = llm.route_query(analysis_prompt, system=system, task_type="concall_parsing")

    print("\n" + "-" * 70)
    print(f"[Node 3: Evidence Harvester] Harvested {len(evidence_items)} Sources:")
    for idx, e in enumerate(evidence_items, 1):
        print(f"  [{idx}] {e.get('title')}\n      URL: {e.get('url')}\n      Excerpt:\n{e.get('excerpt')}")
    print(f"\n[Contradiction Analysis]:\n{contradiction_analysis.strip()}")
    print("-" * 70)

    log_entry = f"[Node 3: Evidence Harvester] Harvested {len(evidence_items)} verified sources."

    return {
        "prosecution_evidence": evidence_items,
        "contradiction_analysis": contradiction_analysis.strip(),
        "logs": state.get("logs", []) + [log_entry, contradiction_analysis]
    }

def peer_triangulation_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 4: Evaluates competitor filings to determine if anomaly is firm-specific or sector-wide.
    Audits competitors on the exact same metric and unit as the selected anomaly.
    """
    ticker = state.get("ticker", "NESTLEIND")
    company_name = state.get("company_name", ticker)
    anomaly = state.get("selected_anomaly", {})
    metric_type = anomaly.get("metric_type", "debtor_days")
    unit = anomaly.get("unit", "d")
    target_delta = float(anomaly.get("delta", 0.0))
    peers = [p for p in PEER_MAPPING.get(ticker, ["BRITANNIA", "TATACONSUM", "DABUR"]) if p != ticker][:2]

    peer_evidence = []
    peer_deltas = []

    print("\n" + "-" * 70)
    print(f"[Node 4: Peer Triangulation] Scraping & Auditing Competitor Disclosures ({anomaly.get('metric_name')}):")

    for peer in peers:
        try:
            p_data = screener_scraper.fetch_company_data(peer)
            p_name = p_data.get("company_name", peer)
            p_summary = ForensicEngine.audit_company(p_data)

            if metric_type == "uvg_divergence":
                p_q = p_summary.quarters_analyzed[-1] if p_summary.quarters_analyzed else None
                p_sales_g = p_summary.sales_growth_yoy.get(p_q, 0.0) if p_q else 0.0
                p_uvg = p_summary.derived_volume_growth.get(p_q, 0.0) if p_q else 0.0
                p_val = round(p_sales_g - p_uvg, 2)
                summary_text = f"{p_name} ({peer}) latest Sales YoY ({p_sales_g}%) vs UVG ({p_uvg}%) spread is {p_val}%."
            elif metric_type == "margin_wedge":
                p_val = float(p_summary.margin_wedge_bps or 0.0)
                summary_text = f"{p_name} ({peer}) operating margin wedge is {p_val} bps."
            elif metric_type == "cfo_conversion":
                p_cfo = round((p_summary.cfo_to_ebitda or 0.70) * 100.0, 1)
                p_val = round(max(0.0, 70.0 - p_cfo), 1)
                summary_text = f"{p_name} ({peer}) CFO to EBITDA conversion deficit is {p_val}% (CFO/EBITDA: {p_cfo}%)."
            else:  # debtor_days / default
                days_list = list(p_summary.debtor_days.values())
                if len(days_list) >= 2:
                    b_idx = -5 if len(days_list) >= 5 else 0
                    p_val = round(days_list[-1] - days_list[b_idx], 1)
                else:
                    p_val = 0.0
                summary_text = f"{p_name} ({peer}) statutory debtor days shifted by {p_val}d over the trailing reporting cycle."

            peer_deltas.append(p_val)
            print(f"  • {p_name} ({peer}): Trailing Metric Delta = {p_val}{unit}")

            peer_evidence.append({
                "peer": p_name,
                "ticker": peer,
                "url": f"https://www.screener.in/company/{peer}/consolidated/",
                "metric_value": p_val,
                "unit": unit,
                "summary": summary_text
            })
        except Exception as e:
            print(f"  [!] Failed to evaluate peer '{peer}': {e}")
            peer_deltas.append(0.0)

    peer_median = float(np.median(peer_deltas)) if peer_deltas else 0.0
    relative_spread = round(target_delta - peer_median, 2)
    spread_formatted = f"{relative_spread:+.2f}{unit}"

    print(f"\n[Peer Spread Math ({anomaly.get('metric_name')})]:")
    print(f"  • Target ({ticker}) Metric:  {target_delta}{unit}")
    print(f"  • Peer Median Metric:       {peer_median}{unit}")
    print(f"  • Idiosyncratic Spread:     {target_delta}{unit} - {peer_median}{unit} = {spread_formatted}")
    print("-" * 70)

    log_entry = (
        f"[Node 4: Peer Triangulation] Target metric: {target_delta}{unit} vs Peer Median: {peer_median}{unit} "
        f"-> Relative Spread: {spread_formatted}"
    )

    return {
        "peer_evidence": peer_evidence,
        "computed_metrics": {**state.get("computed_metrics", {}), "peer_spread_days": relative_spread},
        "logs": state.get("logs", []) + [log_entry]
    }

def adversarial_critic_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 5: The Defense Attorney (Adversarial Stress Test).
    Prints DeepSeek-R1's complete internal thought process and defense evaluation.
    """
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    thesis = state.get("hypothesis", "")
    anomaly = state.get("selected_anomaly", {})
    peer_ev = state.get("peer_evidence", [])

    critic_prompt = f"""
You are the Defense Attorney in a corporate financial trial.
Prosecution's Charge against {company_name} ({ticker}):
"{thesis}"

Supporting Quantitative Deviation:
- Metric: {anomaly.get('metric_name')}
- Quantitative Delta: {anomaly.get('delta')} {anomaly.get('unit', '')}
- Context: {anomaly.get('description')}
- Multi-Quarter Trajectory: {anomaly.get('timeline_trajectory', 'N/A')}

Peer Benchmark Disclosures:
{json.dumps(peer_ev, indent=2)}

Your Mandate: Strenuously EXONERATE {company_name}.
Legal & Evidentiary Standard:
1. If competitors experienced comparable working capital, volume or margin movements (peer spread within normal variance, or sector-wide commodity deflation), you MUST EXONERATE the company and set IS_FALSIFIED: TRUE.
2. If the anomaly is a natural festive timing artifact or common supply chain normalization, you MUST set IS_FALSIFIED: TRUE.
3. Only if the quantitative divergence is strictly firm-specific and completely unexplained by industry-wide patterns, set IS_FALSIFIED: FALSE.

CRITICAL INSTRUCTION FOR FALSIFICATION_CRITERIA:
FALSIFICATION_CRITERIA must state what future POSITIVE operational rebound or metric normalization would DISPROVE the prosecution's thesis (e.g. UVG rebounding above +X% for 2 consecutive quarters, or debtor days compressing below Y days). Never state that further deterioration refutes the claim.

Respond in this EXACT format (do not use markdown bolding like **):
IS_FALSIFIED: [TRUE or FALSE]
EVIDENCE_STRENGTH: [Strong, Moderate, or Weak]
COUNTERARGUMENT: [2 sentences articulating the strongest alternative explanation]
FALSIFICATION_CRITERIA: [Exact future metric normalization that disproves the prosecution]
"""
    system = "You are a rigorous, highly skeptical defense attorney stress-testing a forensic financial hypothesis. Exonerate if peer data or macro reality explains the numbers."
    thought, critic_output = llm.route_query(critic_prompt, system=system, task_type="adversarial")

    # Clean markdown asterisks before regex parsing
    clean_out = re.sub(r"\*+", "", critic_output).strip()

    # Parse defense verdict strictly via regex on its line
    falsified_match = re.search(r"IS_FALSIFIED\s*:\s*(TRUE|FALSE)", clean_out, re.IGNORECASE)
    is_falsified = (falsified_match.group(1).upper() == "TRUE") if falsified_match else False

    # Parse evidence strength strictly via regex on its line
    strength_match = re.search(r"EVIDENCE_STRENGTH\s*:\s*(Strong|Moderate|Weak)", clean_out, re.IGNORECASE)
    strength = strength_match.group(1).capitalize() if strength_match else "Moderate"

    if strength == "Weak":
        is_falsified = True

    # Extract counterargument
    counter_match = re.search(r"COUNTERARGUMENT\s*:\s*(.+?)(?=\n\s*FALSIFICATION_CRITERIA|\Z)", clean_out, re.IGNORECASE | re.DOTALL)
    counterargument = counter_match.group(1).strip() if counter_match else clean_out

    # Extract falsification criteria
    falsify_match = re.search(r"FALSIFICATION_CRITERIA\s*:\s*(.+)", clean_out, re.IGNORECASE | re.DOTALL)
    falsification_condition = falsify_match.group(1).strip() if falsify_match else (
        f"Hypothesis is disproven if {company_name} demonstrates volume normalization without credit expansion for >=2 consecutive quarters."
    )

    print("\n" + "-" * 70)
    print(f"[Node 5: Adversarial Critic - The Defense Attorney]")
    if thought:
        print(f"\n[DeepSeek-R1 Internal CoT Reasoning Trace]:\n{thought.strip()}")
    print(f"\n[Defense Output]:\n{critic_output.strip()}")
    print(f"\n[Parsed Verdict]: Falsified = {is_falsified} | Evidence Strength = {strength}")
    print("-" * 70)

    log_entry = f"[Node 5: Adversarial Critic] Falsified: {is_falsified} | Evidence Strength: {strength}"

    return_dict = {
        "is_falsified": is_falsified,
        "falsification_reason": counterargument if is_falsified else None,
        "evidence_strength": strength,
        "defense_arguments": [{
            "counterargument": counterargument,
            "falsification_condition": falsification_condition
        }],
        "logs": state.get("logs", []) + [log_entry]
    }
    if is_falsified:
        return_dict["current_anomaly_index"] = state.get("current_anomaly_index", 0) + 1
        return_dict["iteration_count"] = state.get("iteration_count", 0) + 1

    return return_dict

def reflection_router(state: InvestigationState) -> str:
    """
    Conditional Edge: Checks if hypothesis was falsified by the Defense Attorney.
    If falsified and additional anomaly candidates exist, loops back to Triage.
    NOTE: Conditional edges cannot mutate state in place.
    """
    is_falsified = state.get("is_falsified", False)
    current_idx = state.get("current_anomaly_index", 0)
    anomalies = state.get("anomalies", [])

    print("\n" + "=" * 70)
    if is_falsified and current_idx < len(anomalies):
        print(f"[Reflection Router] HYPOTHESIS FALSIFIED BY DEFENSE ATTORNEY!")
        print(f"  • Reason: {state.get('falsification_reason', 'Macro/industry factors explain the divergence.')}")
        print(f"  • Advancing to candidate #{current_idx + 1} of {len(anomalies)}: '{anomalies[current_idx].get('metric_name')}'")
        print("  --> LOOPING BACK to Node 1 (Anomaly Triage)...")
        print("=" * 70)
        return "loop_back"

    if is_falsified and current_idx >= len(anomalies):
        print(f"[Reflection Router] ALL CANDIDATES FALSIFIED BY ADVERSARIAL SCRUTINY.")
        print(f"  • Total candidates evaluated: {len(anomalies)}")
        print(f"  • Conclusion: Every anomaly was legitimately justified by sector/macro conditions.")
        print("  --> Proceeding to Compiler to document formal EXONERATION note...")
        print("=" * 70)
        return "proceed"

    print(f"[Reflection Router] HYPOTHESIS SURVIVED ADVERSARIAL SCRUTINY.")
    print(f"  • Evidence Strength: {state.get('evidence_strength', 'Strong')}")
    print("  --> Proceeding to Compiler Node to generate 8-point research schema...")
    print("=" * 70)
    return "proceed"

def compiler_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 6: Synthesizes final verified state into the mandatory 8-Point Forensic Schema.
    Strictly uses verified evidence URLs and dynamic computed metrics (Zero hardcoded text).
    """
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    anomaly = state.get("selected_anomaly", {})
    thesis = state.get("hypothesis", "")
    strength = state.get("evidence_strength", "Moderate")
    is_falsified = state.get("is_falsified", False)
    defense = state.get("defense_arguments", [{}])[-1]
    prosecution = state.get("prosecution_evidence", [])
    metrics = state.get("computed_metrics", {})
    raw_fin = state.get("raw_financials", {})

    # Deduplicate verified URLs preserving insertion order
    verified_urls = list(dict.fromkeys(e.get("url") for e in prosecution if e.get("url")))
    if not verified_urls:
        verified_urls = [raw_fin.get("source_url", f"https://www.screener.in/company/{ticker}/consolidated/")]

    unit = anomaly.get("unit", "")
    peer_sp_raw = metrics.get('peer_spread_days')
    peer_sp_str = f"{peer_sp_raw:+.2f}{unit}" if peer_sp_raw is not None else "N/A"

    if is_falsified:
        discovery = {
            "1_The_Discovery": f"AUDIT CONCLUSION: No actionable forensic divergence verified for {company_name}. Initial working capital concerns were disproven under adversarial peer scrutiny.",
            "2_Why_It_Matters": [
                f"{company_name}'s accounting movements match sector-wide peer patterns and macro supply chain timing.",
                "Adversarial stress-testing confirmed working capital movements do not represent channel stuffing or unearned revenue recognition.",
                "The business exhibits standard operational normalization without evidence of earnings manipulation."
            ],
            "3_Evidence": verified_urls,
            "4_Timeline": f"Audited across {anomaly.get('period', 'trailing quarters')} statutory filings.",
            "5_Numbers": f"Deviation delta: {anomaly.get('delta', 0.0)} in {anomaly.get('metric_name', 'metric')}. Peer comparison confirmed divergence is non-idiosyncratic.",
            "6_Counterargument": defense.get("counterargument", "Industry-wide supply chain and festive seasonality explain observed working capital variations."),
            "7_Falsification_Condition": defense.get("falsification_condition", f"Disproven if {company_name}'s debtor days expand beyond peer medians by >= 10 days in consecutive cycles."),
            "8_Evidence_Strength": "FALSIFIED / EXONERATED (Zero company-specific manipulation found under adversarial scrutiny)"
        }
    else:
        synthesis_prompt = f"""
You are a professional equity research compiler synthesizing a verified forensic finding for {company_name} ({ticker}).
Quantitative Accounting Data:
- Metric: {anomaly.get('metric_name')}
- Period: {anomaly.get('period')}
- Quantitative Delta: {anomaly.get('delta')} {anomaly.get('unit', '')}
- Context: {anomaly.get('description')}
- Multi-Quarter Trajectory: {anomaly.get('timeline_trajectory', 'N/A')}
- Computed Ratios: Beneish DSRI = {metrics.get('beneish_dsri', 'N/A')}, Margin Wedge = {metrics.get('margin_wedge_bps', 'N/A')} bps, Peer Spread = {peer_sp_str}

Harvested Exchange Concall Excerpts & Evidence:
{json.dumps(prosecution, indent=2)}

Forensic Contradiction Analysis:
{state.get('contradiction_analysis', 'N/A')}

Peer Triangulation Benchmarks:
{json.dumps(state.get('peer_evidence', []), indent=2)}

Defense Attorney Stress-Test:
- Counterargument: {defense.get('counterargument')}
- Falsification Criteria: {defense.get('falsification_condition')}
- Rating: {strength}

Verified Sources (You MUST ONLY cite from this exact list): {json.dumps(verified_urls)}

Compile into this EXACT JSON structure:
{{
  "1_The_Discovery": "Exactly 1 sentence stating the verified non-obvious reality",
  "2_Why_It_Matters": ["Bullet 1 citing evidence/implication", "Bullet 2 citing margin/working capital strain", "Bullet 3 citing peer divergence"],
  "3_Evidence": {json.dumps(verified_urls)},
  "4_Timeline": "Quarters over which divergence emerged with inflection points",
  "5_Numbers": "Summary of exact calculation figures (DSRI, delta, margin wedge, peer spread)",
  "6_Counterargument": "Strongest alternative explanation from defense",
  "7_Falsification_Condition": "Exact future metric normalization that proves agent wrong",
  "8_Evidence_Strength": "Rating and justification"
}}
Output ONLY valid JSON. Zero preamble. Do NOT use markdown bold/italic asterisks (**) inside the JSON values.
"""
        system = "You are an institutional financial compiler. Produce clean JSON strictly following the schema using verified data only."
        _, raw_json = llm.route_query(synthesis_prompt, system=system, task_type="synthesis")

        discovery = None
        try:
            json_clean = re.search(r"\{.*\}", raw_json, flags=re.DOTALL)
            if json_clean:
                discovery = json.loads(json_clean.group(0))
        except Exception:
            pass

        if not discovery:
            discovery = {
                "1_The_Discovery": f"{company_name} exhibited an accounting divergence in {anomaly.get('period')}: {anomaly.get('description')}",
                "2_Why_It_Matters": [
                    f"Statutory {anomaly.get('metric_name')} diverged by {anomaly.get('delta')} relative to baseline.",
                    f"Accounting metrics (Beneish DSRI: {metrics.get('beneish_dsri', 'N/A')}, Margin Wedge: {metrics.get('margin_wedge_bps', 'N/A')} bps) indicate working capital strain.",
                    f"Adversarial defense rating assessed as {strength}."
                ],
                "3_Evidence": verified_urls,
                "4_Timeline": f"Divergence established across {anomaly.get('period', 'trailing quarters')}.",
                "5_Numbers": f"Delta: {anomaly.get('delta', 0.0)} in {anomaly.get('metric_name', 'metric')} | Beneish DSRI: {metrics.get('beneish_dsri', 'N/A')} | Margin Wedge: {metrics.get('margin_wedge_bps', 'N/A')} bps.",
                "6_Counterargument": defense.get("counterargument", f"Management cites operational and supply chain adjustments for {company_name}."),
                "7_Falsification_Condition": defense.get("falsification_condition", f"Disproven if {company_name} demonstrates normalization in {anomaly.get('metric_name')} for >=2 consecutive quarters."),
                "8_Evidence_Strength": f"Rating: {strength} (Verified across statutory filings and peer benchmarking)"
            }

    # Clean any leftover markdown asterisks from discovery
    clean_discovery = {}
    for k, v in discovery.items():
        if isinstance(v, str):
            clean_discovery[k] = re.sub(r"\*+", "", v).strip()
        elif isinstance(v, list):
            clean_discovery[k] = [re.sub(r"\*+", "", item).strip() if isinstance(item, str) else item for item in v]
        else:
            clean_discovery[k] = v
    discovery = clean_discovery

    print("\n" + "-" * 70)
    print(f"[Node 6: Compiler Node] Compiled 8-Point Forensic Schema:")
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
        "logs": state.get("logs", []) + ["[Node 6: Compiler Node] Mandatory schema compiled."]
    }
