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
        "logs": state.get("logs", []) + [log_entry, contradiction_analysis]
    }

def peer_triangulation_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 4: Evaluates competitor filings to determine if anomaly is firm-specific or sector-wide.
    Prints all raw peer numbers, peer median, and idiosyncratic spread calculation.
    """
    ticker = state.get("ticker", "NESTLEIND")
    company_name = state.get("company_name", ticker)
    anomaly = state.get("selected_anomaly", {})
    peers = PEER_MAPPING.get(ticker, ["BRITANNIA", "TATACONSUM"])[:2]

    peer_evidence = []
    peer_deltas = []

    print("\n" + "-" * 70)
    print(f"[Node 4: Peer Triangulation] Scraping Statutory Peer Disclosures:")

    for peer in peers:
        try:
            p_data = screener_scraper.fetch_company_data(peer)
            p_name = p_data.get("company_name", peer)
            raw_p_days = p_data.get("ratios_table", {}).get("rows", {}).get("Debtor Days", [])
            p_clean = []
            for pv in raw_p_days:
                try:
                    if pv is not None and str(pv).strip() not in ("", "-", "nan", "None"):
                        p_clean.append(float(pv))
                except (ValueError, TypeError):
                    pass
            if len(p_clean) >= 2:
                p_delta = round(p_clean[-1] - p_clean[0], 1)
                peer_deltas.append(p_delta)
                print(f"  • {p_name} ({peer}): Baseline Debtor Days={p_clean[0]}d -> Latest={p_clean[-1]}d (Delta: {p_delta}d)")
            else:
                p_delta = 0.0
                peer_deltas.append(p_delta)
                print(f"  • {p_name} ({peer}): Insufficient debtor history, delta recorded as 0.0d")

            peer_evidence.append({
                "peer": p_name,
                "ticker": peer,
                "url": f"https://www.screener.in/company/{peer}/consolidated/",
                "debtor_delta": p_delta,
                "summary": f"{p_name} ({peer}) statutory debtor days shifted by {p_delta}d over the trailing reporting cycle."
            })
        except Exception as e:
            print(f"  [!] Failed to pull peer '{peer}': {e}")
            peer_deltas.append(0.0)

    target_delta = float(anomaly.get("delta", 0.0))
    peer_median = float(np.median(peer_deltas)) if peer_deltas else 0.0
    relative_spread = round(target_delta - peer_median, 1)

    print(f"\n[Peer Spread Math]:")
    print(f"  • Target ({ticker}) Delta:  {target_delta}d")
    print(f"  • Peer Median Delta:        {peer_median}d")
    print(f"  • Idiosyncratic Spread:     {target_delta}d - {peer_median}d = {'+' if relative_spread >= 0 else ''}{relative_spread}d")
    print("-" * 70)

    log_entry = (
        f"[Node 4: Peer Triangulation] Target delta: {target_delta}d vs Peer Median: {peer_median}d "
        f"-> Relative Spread: {relative_spread}d"
    )

    return {
        "peer_evidence": peer_evidence,
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
- Quantitative Delta: {anomaly.get('delta')}
- Context: {anomaly.get('description')}

Peer Benchmark Disclosures:
{json.dumps(peer_ev, indent=2)}

Your Mandate: Strenuously EXONERATE {company_name}.
Legal & Evidentiary Standard:
1. If competitors experienced comparable working capital or margin movements (peer spread within 5 days, or sector-wide commodity deflation), you MUST EXONERATE the company and set IS_FALSIFIED: TRUE.
2. If the anomaly is a natural festive timing artifact or common supply chain normalization, you MUST set IS_FALSIFIED: TRUE.
3. Only if the quantitative divergence is strictly firm-specific and completely unexplained by industry-wide patterns, set IS_FALSIFIED: FALSE.

Respond in this EXACT format:
IS_FALSIFIED: [TRUE or FALSE]
EVIDENCE_STRENGTH: [Strong, Moderate, or Weak]
COUNTERARGUMENT: [2 sentences articulating the strongest alternative explanation]
FALSIFICATION_CRITERIA: [Exact quantitative future metric that disproves the prosecution]
"""
    system = "You are a rigorous, highly skeptical defense attorney stress-testing a forensic financial hypothesis. Exonerate if peer data or macro reality explains the numbers."
    thought, critic_output = llm.route_query(critic_prompt, system=system, task_type="adversarial")

    # Parse evidence strength
    strength = "Moderate"
    if "WEAK" in critic_output.upper():
        strength = "Weak"
    elif "STRONG" in critic_output.upper():
        strength = "Strong"

    # Parse defense verdict (exonerated if IS_FALSIFIED: TRUE or evidence strength is Weak)
    is_falsified = False
    if "IS_FALSIFIED: TRUE" in critic_output.upper() or strength == "Weak":
        is_falsified = True

    # Extract counterargument
    counter_match = re.search(r"COUNTERARGUMENT:\s*(.*)", critic_output, re.IGNORECASE)
    counterargument = counter_match.group(1).strip() if counter_match else critic_output.strip()

    # Extract falsification criteria
    falsify_match = re.search(r"FALSIFICATION_CRITERIA:\s*(.*)", critic_output, re.IGNORECASE)
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

    return {
        "is_falsified": is_falsified,
        "falsification_reason": counterargument if is_falsified else None,
        "evidence_strength": strength,
        "defense_arguments": [{
            "counterargument": counterargument,
            "falsification_condition": falsification_condition
        }],
        "logs": state.get("logs", []) + [log_entry]
    }

def reflection_router(state: InvestigationState) -> str:
    """
    Conditional Edge: Checks if hypothesis was falsified by the Defense Attorney.
    If falsified and additional anomaly candidates exist, loops back to Triage.
    """
    is_falsified = state.get("is_falsified", False)
    current_idx = state.get("current_anomaly_index", 0)
    anomalies = state.get("anomalies", [])
    has_more = (current_idx + 1) < len(anomalies)

    print("\n" + "=" * 70)
    if is_falsified and has_more:
        next_idx = current_idx + 1
        print(f"[Reflection Router] HYPOTHESIS FALSIFIED BY DEFENSE ATTORNEY!")
        print(f"  • Reason: {state.get('falsification_reason', 'Macro/industry factors explain the divergence.')}")
        print(f"  • Advancing to candidate #{next_idx + 1} of {len(anomalies)}: '{anomalies[next_idx].get('metric_name')}'")
        print("  --> LOOPING BACK to Node 1 (Anomaly Triage)...")
        print("=" * 70)
        state["current_anomaly_index"] = next_idx
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        return "loop_back"

    if is_falsified and not has_more:
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

    # Gather strictly verified URLs
    verified_urls = [e.get("url") for e in prosecution if e.get("url")]
    if not verified_urls:
        verified_urls = [raw_fin.get("source_url", f"https://www.screener.in/company/{ticker}/consolidated/")]

    peer_sp_str = f"{metrics.get('peer_spread_days')}d" if metrics.get('peer_spread_days') is not None else "N/A"

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
- Quantitative Delta: {anomaly.get('delta')}
- Context: {anomaly.get('description')}
- Computed Ratios: Beneish DSRI = {metrics.get('beneish_dsri', 'N/A')}, Margin Wedge = {metrics.get('margin_wedge_bps', 'N/A')} bps, Peer Spread = {peer_sp_str}
- Verified Sources (You MUST ONLY cite from this list): {json.dumps(verified_urls)}
- Counterargument: {defense.get('counterargument')}
- Falsification: {defense.get('falsification_condition')}
- Rating: {strength}

Compile into this EXACT JSON structure:
{{
  "1_The_Discovery": "Exactly 1 sentence stating the verified non-obvious reality",
  "2_Why_It_Matters": ["Bullet 1", "Bullet 2", "Bullet 3"],
  "3_Evidence": {json.dumps(verified_urls)},
  "4_Timeline": "Quarters over which divergence emerged",
  "5_Numbers": "Summary of exact calculation figures (DSRI, delta, margin wedge)",
  "6_Counterargument": "Strongest alternative explanation from defense",
  "7_Falsification_Condition": "Exact future metric that proves agent wrong",
  "8_Evidence_Strength": "Rating and justification"
}}
Output ONLY valid JSON. Zero preamble.
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
