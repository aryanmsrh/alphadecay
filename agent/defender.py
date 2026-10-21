import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from agent.llm import LLM


def extract_clean_percentage(raw_val: str, default: str = "82%") -> str:
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
        summary = anomaly.get("summary", "")
        math_detail = anomaly.get("math_detail", "")
        directional_comparison = anomaly.get("directional_comparison", summary)
        severity = anomaly.get("severity", 5.0)
        multi_quarter_trajectory = anomaly.get("multi_quarter_trajectory", summary)
        numbers_bullets = anomaly.get("numbers_bullets", [])

        numbers_text = "\n".join([f"- {b}" for b in numbers_bullets]) if numbers_bullets else math_detail
        ev_text = "\n".join([
            f"- [{e.get('source')} ({e.get('url', '')})]: {e.get('excerpt', '')[:350]}"
            for e in evidence_items[:4]
        ])

        prompt = f"""Target Entity: {company_name} ({ticker})

Goal: Act as a rational corporate strategist and operational defender. Assume the company is acting rationally and defend it using verified operational mechanics, seasonal context, or industry realities.
Mindset: "Before we accuse an established company of distress or accounting tricks, is there a standard operational explanation for this?"

Prosecution Allegation:
The Attacker alleges that management is hiding commercial friction or margin stress behind {metric}.

STRICT ADVOCACY RULE: You are the Corporate Defense Counsel for the company. You are STRICTLY FORBIDDEN from accusing the company of aggressive revenue recognition, channel stuffing, inventory obsolescence, operational stress, or poor management. You must refute the prosecutorial view and explain why the exact numbers reflect rational, deliberate business strategy: (a) counter-cyclical brand and distribution investments, (b) agricultural/raw material biological aging cycles or input commodity pass-through, (c) deliberate inventory buffering for modern trade and quick-commerce dark stores, or (d) fortress balance sheet resilience.

Anomaly Under Review:
- Metric: {metric}
- Directional Fact: {directional_comparison}
- Multi-Quarter Trajectory: {multi_quarter_trajectory}
- Severity: {severity}/10

Calculated Audited Numbers:
{numbers_text}

Public Disclosures and Evidence:
{ev_text}

Requirements:
1. Explain in 4 to 6 rigorous analytical sentences why this divergence reflects standard operational strategy, seasonal inventory buffering, commodity cycle adjustments, distribution expansion (e.g. quick commerce dark store stocking), or deliberate capital allocation rather than distress.
2. Formulate a hard falsification condition stating the exact future positive metric turnaround (with concrete numbers, e.g., metric recovering above X% or normalizing below Y for 2 consecutive quarters) that would disprove the Attacker's claim and vindicate management.
3. Output strictly valid JSON with exact keys: "counterargument", "falsification_condition", "evidence_strength", "confidence".
4. Note: "confidence" MUST be a clean percentage string only (e.g. "82%"). Place all explanation inside "evidence_strength".
Do not echo instructions. Write exclusively in fluent English.

JSON format:
{{
  "counterargument": "4 to 6 analytical sentences defending management and operational strategy",
  "falsification_condition": "Concrete positive metric recovery condition disproving the attacker thesis",
  "evidence_strength": "e.g. High (8.0/10) - supported by operational cash flows and working capital structure",
  "confidence": "82%"
}}
"""
        system = "You are the Defender, the Corporate Defense Counsel for the company. You are strictly forbidden from agreeing with accusations of distress or malfeasance. Explain in 4 to 6 analytical sentences how operational mechanics and rational business strategy explain the numbers. Define a concrete positive metric turnaround threshold as the falsification condition. Output strictly valid JSON."

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
        evidence_strength = str(parsed.get("evidence_strength", "")).strip()
        raw_conf = str(parsed.get("confidence", "") or parsed.get("confidence_rating", "")).strip()
        confidence = extract_clean_percentage(raw_conf, default="82%")

        return {
            "counterargument": counterargument,
            "hypothesis": counterargument,
            "alternative_explanation": counterargument,
            "falsification_condition": falsification_condition,
            "evidence_strength": evidence_strength,
            "confidence": confidence,
            "confidence_rating": confidence,
        }, provider
