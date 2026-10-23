import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from agent.llm import LLM
from agent.prompts import (
    ATTACKER_SYSTEM_PROMPT,
    build_attacker_prompt,
    format_evidence_bullets,
    format_numbers_bullets,
)


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


def clean_markdown_formatting(text: str) -> str:
    """Strip markdown headers (###) and formatting to produce clean prose."""
    if not text:
        return ""
    lines = []
    for line in str(text).split("\n"):
        clean_line = re.sub(r"^\s*#{1,6}\s*", "", line)
        lines.append(clean_line)
    return "\n".join(lines).strip()


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
        numbers_text = format_numbers_bullets(numbers_bullets)
        ev_text = format_evidence_bullets(evidence_items, max_items=4, max_len=350)

        prompt = build_attacker_prompt(
            company_name=company_name,
            ticker=ticker,
            metric=metric,
            multi_quarter_trajectory=multi_quarter_trajectory,
            severity=severity,
            numbers_text=numbers_text,
            ev_text=ev_text,
        )
        system = ATTACKER_SYSTEM_PROMPT

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
            parsed, provider = self.generate_json(
                prompt=prompt,
                system=system,
                event_callback=event_callback,
                label=f"Attacker Prosecution ({metric})",
            )

        if isinstance(parsed, dict) and "json" in parsed and isinstance(parsed["json"], dict):
            parsed = parsed["json"]

        verdict = clean_markdown_formatting(str(parsed.get("verdict", "") or parsed.get("hypothesis", "")))
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
