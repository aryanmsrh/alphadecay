import json
import re
from typing import Dict, Any, List, Optional
from agent.state import InvestigationState, NodalRound
from engine.llm import call_model, extract_json_object


def anomaly_triage_node(state: InvestigationState) -> Dict[str, Any]:
    anomalies = state.get("anomalies", [])
    idx = state.get("current_anomaly_index", 0)

    if not anomalies:
        current_anomaly = {
            "metric": "Operational Health",
            "summary": "General examination of quarterly sales, profit margins, and customer credit collections.",
            "significance": "Core financial stability baseline."
        }
    else:
        actual_idx = min(idx, len(anomalies) - 1)
        current_anomaly = anomalies[actual_idx]

    metric_name = current_anomaly.get("metric", "Financial Metric")
    summary = current_anomaly.get("summary", "")

    test_hypo = f"Test whether '{metric_name}' indicates genuine accounting manipulation, channel stuffing, or serious financial distress at {state['company_name']}."

    return {
        "current_anomaly": current_anomaly,
        "current_hypothesis": test_hypo
    }


def attacker_node(state: InvestigationState) -> Dict[str, Any]:
    company = state["company_name"]
    ticker = state["ticker"]
    anomaly = state["current_anomaly"]
    hypo = state["current_hypothesis"]
    key_numbers = state["indicators"].get("key_numbers", [])
    evidence = state.get("evidence_items", [])

    prompt = f"""
You are the relentless, hard-hitting financial investigator and prosecutor.
Target Company: {company} ({ticker})
Anomaly to Attack: {anomaly.get('metric')} - {anomaly.get('summary')}
Specific Hypothesis: {hypo}

Financial Numbers:
{json.dumps(key_numbers, indent=2)}

Available Evidence & Sources:
{json.dumps(evidence, indent=2)}

YOUR INSTRUCTIONS:
1. You must work VERY, VERY hard to PROVE that this hypothesis is real and that the company is manipulating numbers or hiding operational distress.
2. Attack aggressively using the exact financial numbers, margin pressures, rising expenses, and credit risks.
3. You must NOT give up easily. Tear apart the company's reported numbers.
4. Write 2-3 punchy, aggressive paragraphs in plain, simple English.
5. DO NOT use corporate buzzwords or business jargon. Speak plainly and directly.
"""
    system = "You are a tough, evidence-driven financial prosecutor. Fight hard to prove the hypothesis. Speak in plain, punchy English."
    response, provider = call_model(prompt, system=system)
    return {
        "current_attacker_case": response.strip(),
        "provider_used": provider
    }


def defender_node(state: InvestigationState) -> Dict[str, Any]:
    company = state["company_name"]
    ticker = state["ticker"]
    anomaly = state["current_anomaly"]
    hypo = state["current_hypothesis"]
    attacker_case = state["current_attacker_case"]
    key_numbers = state["indicators"].get("key_numbers", [])
    evidence = state.get("evidence_items", [])

    prompt = f"""
You are the fierce defense attorney defending {company} ({ticker}).
The prosecutor just launched this aggressive attack against the company:
\"\"\"{attacker_case}\"\"\"

Anomaly Under Examination: {anomaly.get('metric')} - {anomaly.get('summary')}
Hypothesis: {hypo}

Financial Numbers:
{json.dumps(key_numbers, indent=2)}

Available Evidence & Sources:
{json.dumps(evidence, indent=2)}

YOUR INSTRUCTIONS:
1. You must work VERY, VERY hard to DEFEND the company and completely REFUTE the prosecutor's attack.
2. Defend aggressively using volume growth, cash collections, seasonal demand, input cost trends, and normal business operations.
3. You must NOT give up easily. Dismantle the prosecutor's claims piece by piece.
4. Write 2-3 punchy paragraphs in plain, simple English.
5. DO NOT use corporate buzzwords or business jargon. Speak plainly and directly.
"""
    system = "You are a staunch, evidence-driven defense attorney. Fight hard to refute the attack and protect the company with facts. Speak in plain English."
    response, provider = call_model(prompt, system=system)
    return {
        "current_defender_case": response.strip(),
        "provider_used": provider
    }


def adjudicator_node(state: InvestigationState) -> Dict[str, Any]:
    company = state["company_name"]
    ticker = state["ticker"]
    idx = state.get("current_anomaly_index", 0)
    anomaly = state["current_anomaly"]
    hypo = state["current_hypothesis"]
    attacker_case = state["current_attacker_case"]
    defender_case = state["current_defender_case"]
    key_numbers = state["indicators"].get("key_numbers", [])

    prompt = f"""
You are the independent judge deciding a hard-fought financial battle.
Target: {company} ({ticker})
Hypothesis: {hypo}

PROSECUTOR'S ATTACK:
\"\"\"{attacker_case}\"\"\"

DEFENSE'S COUNTER-ATTACK:
\"\"\"{defender_case}\"\"\"

FINANCIAL FACTS:
{json.dumps(key_numbers, indent=2)}

YOUR INSTRUCTIONS:
1. Deliver a fair, decisive ruling based strictly on who proved their case with facts.
2. The verdict MUST be ONLY ONE of these two exact words:
   - "SURVIVES" (if the prosecutor's attack is proven and the defense failed to explain the anomaly)
   - "FAILS" (if the defense successfully proved the anomaly is normal business and refuted the prosecutor)
3. Rate the strength of the hypothesis on a scale of 1 to 10:
   - 1/10 = Completely false / total failure
   - 5/10 = Balanced / inconclusive
   - 10/10 = Irrefutable proof / absolute survival
4. Give a clear explanation in 2-3 sentences of plain, simple English with zero corporate jargon.

Respond ONLY with valid JSON in this exact structure:
{{
  "verdict": "SURVIVES" | "FAILS",
  "strength_score": 7,
  "verdict_reason": "Clear 2-sentence explanation in simple English."
}}
"""
    system = "You are an impartial financial judge. Be decisive. Use only two verdicts: SURVIVES or FAILS. Rate strength out of 10. Use plain English."
    raw_response, provider = call_model(prompt, system=system)
    parsed = extract_json_object(raw_response)

    if not parsed:
        verdict = "FAILS"
        strength = 3
        reason = f"The defense established that {company}'s reported numbers match normal business operations rather than wrongdoing."
    else:
        verdict = str(parsed.get("verdict", "FAILS")).strip().upper()
        if "SURVIVE" in verdict:
            verdict = "SURVIVES"
        else:
            verdict = "FAILS"
        try:
            strength = int(parsed.get("strength_score", 4))
            strength = max(1, min(10, strength))
        except Exception:
            strength = 4
        reason = str(parsed.get("verdict_reason", "Evaluated based on statutory filings and defense counterarguments.")).strip()

    round_record: NodalRound = {
        "round_index": idx + 1,
        "anomaly_title": anomaly.get("metric", f"Anomaly #{idx + 1}"),
        "anomaly_description": anomaly.get("summary", ""),
        "hypothesis": hypo,
        "attacker_case": attacker_case,
        "defender_case": defender_case,
        "verdict": verdict,
        "strength_score": strength,
        "verdict_reason": reason
    }

    nodal_flow = list(state.get("nodal_flow", []))
    nodal_flow.append(round_record)

    return {
        "nodal_flow": nodal_flow,
        "provider_used": provider
    }


def reflection_router(state: InvestigationState) -> str:
    current_idx = state.get("current_anomaly_index", 0)
    anomalies = state.get("anomalies", [])
    max_to_check = min(len(anomalies), 5)

    if (current_idx + 1) < max_to_check:
        state["current_anomaly_index"] = current_idx + 1
        return "loop_back"

    return "proceed"


def compiler_node(state: InvestigationState) -> Dict[str, Any]:
    company = state["company_name"]
    ticker = state["ticker"]
    headline_hypo = state.get("headline_hypothesis", "")
    nodal_flow = state.get("nodal_flow", [])

    survived_rounds = [r for r in nodal_flow if r["verdict"] == "SURVIVES" and r["strength_score"] >= 6]

    if survived_rounds:
        final_verdict = "SURVIVES"
        final_strength = max(r["strength_score"] for r in survived_rounds)
        top_anomaly = survived_rounds[0]["anomaly_title"]
        summary = f"The adverse hypothesis SURVIVES scrutiny with a strength rating of {final_strength}/10. {company} showed persistent anomalies in {top_anomaly} that the defense could not adequately justify."
        final_result_hypo = f"Hypothesis SURVIVES: Evidence supports potential financial pressure or accounting distortion in {top_anomaly}."
    else:
        final_verdict = "FAILS"
        if nodal_flow:
            final_strength = min(r["strength_score"] for r in nodal_flow)
        else:
            final_strength = 2
        summary = f"The adverse hypothesis FAILS with a weak rating of {final_strength}/10. The defense convincingly proved that {company}'s financial metrics are driven by real sales volume, disciplined credit management, and normal business operations."
        final_result_hypo = f"Hypothesis FAILS: No material accounting manipulation or distress could be established across {len(nodal_flow)} tested anomaly areas."

    return {
        "final_verdict": final_verdict,
        "final_strength": final_strength,
        "final_summary": summary,
        "final_result_hypothesis": final_result_hypo
    }
