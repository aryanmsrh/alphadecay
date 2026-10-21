import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from agent.llm import LLM


def extract_clean_percentage(raw_val: str, default: str = "85%") -> str:
    s = str(raw_val or "").strip()
    match = re.search(r"\b(\d{1,3}%)\b", s)
    if match:
        return match.group(1)
    match_num = re.search(r"\b(\d{1,3})\b", s)
    if match_num:
        val = int(match_num.group(1))
        if 0 <= val <= 100:
            return f"{val}%"
    return default


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
        summary = anomaly.get("summary", "")
        math_detail = anomaly.get("math_detail", "")
        directional_comparison = anomaly.get("directional_comparison", summary)
        severity = anomaly.get("severity", 5.0)
        multi_quarter_trajectory = anomaly.get("multi_quarter_trajectory", summary)
        numbers_bullets = anomaly.get("numbers_bullets", [])
        peer_data = (dossier.get("peer_data", []) if dossier else [])

        numbers_text = "\n".join([f"- {b}" for b in numbers_bullets]) if numbers_bullets else math_detail
        ev_text = "\n".join([
            f"- [{e.get('source')} ({e.get('url', '')})]: {e.get('excerpt', '')[:350]}"
            for e in evidence_items[:4]
        ])

        prompt = f"""Target Entity: {company_name} ({ticker})

Goal: Act as a ruthless forensic investigator assuming the worst. Look at the financial divergence calculated below and build a prosecutorial case exposing what management is hiding.
Mindset: "Companies exist to make their numbers look prettier than reality. What accounting trick, delayed write-down, channel pressure, or margin degradation is this divergence hiding?"

Anomaly Under Investigation:
- Metric: {metric}
- Directional Fact: {directional_comparison}
- Multi-Quarter Trajectory: {multi_quarter_trajectory}
- Severity: {severity}/10

Calculated Audited Numbers:
{numbers_text}

Public Disclosures and Evidence:
{ev_text}

Requirements:
1. Explain in 4 to 6 rigorous analytical sentences what operational or accounting pressure management is downplaying behind the exact numbers provided.
2. Cross-examine the divergence against sector peers and multi-quarter progression.
3. State specifically whether this indicates channel stuffing, inventory obsolescence, cost stickiness, margin degradation, or cash conversion stress.
4. Output strictly valid JSON with exact keys: "verdict", "evidence_strength", "confidence".
5. Note: "confidence" MUST be a clean percentage string only (e.g. "88%"). Place all explanation inside "evidence_strength".
Do not echo instructions. Write exclusively in fluent English.

JSON format:
{{
  "verdict": "4 to 6 analytical sentences detailing what management is hiding",
  "evidence_strength": "e.g. High (8.5/10) - substantiated by audited cash flow and ratio spreads",
  "confidence": "88%"
}}
"""
        system = "You are the Attacker, a ruthless forensic financial investigator assuming the worst. Explain in 4 to 6 analytical sentences what accounting trick, channel pressure, or operational stress management is hiding behind the audited numbers. Output strictly valid JSON."

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
        evidence_strength = str(parsed.get("evidence_strength", "")).strip()
        raw_conf = str(parsed.get("confidence", "") or parsed.get("confidence_rating", "")).strip()
        confidence = extract_clean_percentage(raw_conf, default="88%")

        return {
            "verdict": verdict,
            "hypothesis": verdict,
            "evidence_strength": evidence_strength,
            "confidence": confidence,
            "confidence_rating": confidence,
        }, provider
