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


class Defender(LLM):
    def defend(
        self,
        company_name: str,
        ticker: str,
        anomaly: Dict[str, Any],
        attacker_verdict: str,
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

Goal: Act as a rational corporate strategist and operational defender. Assume the company is acting rationally and defend it using verified operational mechanics, seasonal context, or industry realities.
Mindset: "Before we accuse an established company of distress or accounting tricks, is there a standard operational explanation for this?"

Prosecution Allegation:
The Attacker alleges that management is hiding commercial friction or margin stress behind {metric}.

STRICT ADVOCACY RULE: You are the Corporate Defense Counsel for the company. You are STRICTLY FORBIDDEN from accusing the company of aggressive revenue recognition, channel stuffing, inventory obsolescence, operational stress, or poor management. You must refute the prosecutorial view and explain why the exact numbers reflect rational, deliberate business strategy: (a) deliberate strategic supply buffering or capacity expansion, (b) raw material input price cycles or pricing pass-through delays, (c) working capital adjustments for new distribution channels, or (d) balance sheet preservation.

Anomaly Under Review:
- Metric: {metric}
- Multi-Quarter Trajectory: {multi_quarter_trajectory}
- Severity: {severity}/10

Calculated Audited Numbers:
{numbers_text}

Public Disclosures and Evidence:
{ev_text}

Requirements:
1. Deliver an exhaustive, institutional-grade corporate defense detailing why this divergence reflects standard corporate operational strategy, deliberate strategic supply buffering, capacity expansion, input pricing pass-through delays, distribution channel adjustments, or balance sheet preservation rather than distress.
2. Cross-examine the divergence deeply against sector peer benchmarks, historical cyclicality, and concall explanations.
3. Formulate a hard, measurable falsification condition stating the exact future positive metric turnaround (with concrete numerical thresholds, e.g., metric recovering above X% or normalizing below Y for 2 consecutive quarters) that would definitively disprove the Attacker's claim and vindicate management. Provide full analytical depth—do not artificially truncate, summarize trivially, or shorten your reasoning.
4. Output strictly valid JSON with exact keys: "counterargument", "falsification_condition", "evidence_strength", "confidence".
5. Note: "confidence" MUST be a clean percentage string strictly derived from evidence (e.g. 'XX%'). Place all detailed evidentiary audit rationale inside "evidence_strength".
Do not echo instructions. Write exclusively in fluent English.

JSON format:
{{
  "counterargument": "Exhaustive, rigorous analytical defense explaining corporate operational strategy and commercial mechanics",
  "falsification_condition": "Concrete positive metric recovery condition disproving the attacker thesis",
  "evidence_strength": "e.g. High (8.0/10) - supported by operational cash flows and working capital structure",
  "confidence": "Clean percentage string strictly derived from evidence (e.g. 'XX%')"
}}
"""
        system = "You are the Defender, the Corporate Defense Counsel for the company. You are strictly forbidden from agreeing with accusations of distress or malfeasance. Deliver an exhaustive, rigorous analytical defense explaining how operational mechanics and rational business strategy explain the numbers. Define a concrete positive metric turnaround threshold as the falsification condition. Provide full analytical depth without artificial truncation. Output strictly valid JSON."

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

        counterargument = str(
            parsed.get("counterargument", "")
            or parsed.get("hypothesis", "")
            or parsed.get("alternative_explanation", "")
        ).strip()
        falsification_condition = str(parsed.get("falsification_condition", "")).strip()
        if not counterargument or not falsification_condition:
            raise KeyError(f"Missing required deliverable field from LLM output: {parsed}")
        evidence_strength = str(parsed.get("evidence_strength", "")).strip()
        raw_conf = str(parsed.get("confidence", "") or parsed.get("confidence_rating", "")).strip()
        confidence = extract_clean_percentage(raw_conf)

        return {
            "counterargument": counterargument,
            "falsification_condition": falsification_condition,
            "evidence_strength": evidence_strength,
            "confidence": confidence,
        }, provider
