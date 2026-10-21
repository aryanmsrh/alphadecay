import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from agent.llm import LLM


def extract_clean_percentage(raw_val: str) -> str:
    s = str(raw_val or "").strip()
    match = re.search(r"\b(\d{1,3}%)\b", s)
    if match:
        return match.group(1)
    match_num = re.search(r"\b(\d{1,3})\b", s)
    if match_num:
        val = int(match_num.group(1))
        if 0 <= val <= 100:
            return f"{val}%"
    raise ValueError(f"Model failed to output a valid confidence percentage: {raw_val}")


class Attacker(LLM):
    def attack(
        self,
        company_name: str,
        ticker: str,
        anomaly: Dict[str, Any],
        key_numbers: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        finder: Optional[Any] = None,
        dossier: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[..., None]] = None,
        **kwargs,
    ) -> Tuple[Dict[str, Any], str]:
        metric = anomaly.get("metric", "Financial Metric")
        severity = anomaly.get("severity", 5.0)
        multi_quarter_trajectory = anomaly.get("multi_quarter_trajectory", "")
        numbers_bullets = anomaly.get("numbers_bullets", [])
        numbers_text = "\n".join([f"- {b}" for b in numbers_bullets])
        ev_text = "\n".join([
            f"- [{e.get('source')} ({e.get('url', '')})]: {e.get('excerpt', '')[:350]}"
            for e in evidence_items[:4]
        ])

        prompt = f"""Target Entity: {company_name} ({ticker})

Goal: Act as a ruthless forensic investigator assuming the worst. Look at the financial divergence calculated below and build an unsparing prosecutorial case exposing what management is hiding.
Mindset: "Companies exist to make their numbers look prettier than reality. What accounting trick, delayed write-down, channel pressure, or margin degradation is this divergence hiding?"

Anomaly Under Investigation:
- Metric: {metric}
- Multi-Quarter Trajectory: {multi_quarter_trajectory}
- Severity: {severity}/10

Calculated Audited Numbers:
{numbers_text}

Public Disclosures and Evidence:
{ev_text}

Requirements:
1. Deliver an exhaustive, institutional-grade prosecutorial forensic verdict exposing what operational pressure, channel friction, cost stickiness, or accounting divergence management is downplaying behind the audited numbers.
2. Cross-examine the divergence deeply against sector peers, earnings concall dialogue, and multi-quarter progression.
3. Articulate the precise accounting and commercial mechanics (e.g. channel stuffing, unabsorbed fixed overheads, inventory obsolescence, delayed price pass-throughs, or cash flow drag). Provide full analytical depth—do not artificially truncate, summarize trivially, or shorten your reasoning.
4. Output strictly valid JSON with exact keys: "verdict", "evidence_strength", "confidence".
5. Note: "confidence" MUST be a clean percentage string strictly derived from evidence (e.g. 'XX%'). Place all detailed evidentiary audit rationale inside "evidence_strength".
Do not echo instructions. Write exclusively in fluent English.

JSON format:
{{
  "verdict": "Exhaustive, rigorous forensic analysis detailing what management is obscuring behind the reported figures",
  "evidence_strength": "e.g. High (8.5/10) - substantiated by audited cash flow and ratio spreads",
  "confidence": "Clean percentage string strictly derived from evidence (e.g. 'XX%')"
}}
"""
        system = "You are the Attacker, a ruthless forensic financial investigator assuming the worst. Deliver an exhaustive, institutional-grade prosecutorial analysis exposing the accounting tricks, channel pressure, or operational stress management is hiding behind the audited numbers. Provide full analytical depth without artificial truncation. Output strictly valid JSON."

        if finder:
            parsed, provider = self.generate_with_tools(
                prompt=prompt,
                finder=finder,
                company_name=company_name,
                ticker=ticker,
                dossier=dossier or {},
                system=system,
                event_callback=event_callback,
                anomaly=anomaly,
            )
        else:
            parsed, provider = self.generate_json(prompt=prompt, system=system)

        if isinstance(parsed, dict) and "json" in parsed and isinstance(parsed["json"], dict):
            parsed = parsed["json"]

        verdict = str(parsed.get("verdict", "") or parsed.get("hypothesis", "")).strip()
        if not verdict:
            raise KeyError(f"Missing required deliverable field from LLM output: {parsed}")
        evidence_strength = str(parsed.get("evidence_strength", "")).strip()
        raw_conf = str(parsed.get("confidence", "") or parsed.get("confidence_rating", "")).strip()
        confidence = extract_clean_percentage(raw_conf)

        return {
            "verdict": verdict,
            "evidence_strength": evidence_strength,
            "confidence": confidence,
        }, provider
