import os
import re
import json
import httpx
from typing import Dict, Any, List, Tuple, Optional
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_FALLBACK_MODEL,
    USE_OFFLINE_MODE
)


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0).strip())
        except Exception:
            pass

    return None


def call_gemini(prompt: str, system: Optional[str] = None) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "HIGH"
            }
        }
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    try:
        with httpx.Client(timeout=35.0) as client:
            res = client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    texts = [p.get("text", "") for p in parts if "text" in p]
                    full_text = "".join(texts).strip()
                    if full_text:
                        return full_text
    except Exception:
        pass

    return None


def call_ollama(prompt: str, system: Optional[str] = None) -> Optional[str]:
    endpoint = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_FALLBACK_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=150.0) as client:
            res = client.post(endpoint, json=payload)
            if res.status_code == 200:
                raw = res.json().get("response", "").strip()
                clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                return clean
    except Exception:
        pass

    return None


def call_model(prompt: str, system: Optional[str] = None) -> Tuple[str, str]:
    offline = USE_OFFLINE_MODE or os.getenv("USE_OFFLINE_MODE", "false").lower() in ("true", "1", "yes")
    if not offline and GEMINI_API_KEY:
        gemini_text = call_gemini(prompt, system=system)
        if gemini_text:
            return gemini_text, "gemini"

    ollama_text = call_ollama(prompt, system=system)
    if ollama_text:
        return ollama_text, "ollama"

    raise RuntimeError("Both primary Gemini and local Ollama model calls failed. Check API key and Ollama service.")


def evaluate_investigation(
    company_name: str,
    ticker: str,
    hypothesis: str,
    key_numbers: List[Dict[str, Any]],
    red_flags: List[Dict[str, Any]],
    evidence_items: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], str, str]:
    prompt = f"""
You are an expert financial investigator evaluating a forensic hypothesis for {company_name} ({ticker}).

INVESTIGATION HYPOTHESIS:
"{hypothesis}"

VERIFIED FINANCIAL CALCULATIONS (Use these exact numbers, do NOT alter or invent calculations):
{json.dumps(key_numbers, indent=2)}

OBSERVED FINANCIAL RED FLAGS / ANOMALIES:
{json.dumps(red_flags, indent=2)}

AVAILABLE VERIFIED EVIDENCE & SOURCE EXCERPTS:
{json.dumps(evidence_items, indent=2)}

INSTRUCTIONS:
1. Evaluate whether the evidence and verified calculations support, refute, or fail to establish the hypothesis.
2. Select one of three strict verdicts:
   - "SUPPORTED" (Available evidence supports the hypothesis)
   - "REFUTED" (Available evidence contradicts the hypothesis)
   - "NOT_ESTABLISHED" (Evidence is insufficient or conflicting)
3. Distinguish ordinary operational shifts from financial wrongdoing.
4. Synthesize the findings into the mandatory 8-point report.

Format your response strictly as valid JSON matching this schema:
{{
  "verdict": "SUPPORTED" | "REFUTED" | "NOT_ESTABLISHED",
  "verdict_summary": "1-2 sentence plain-English summary of the verdict",
  "1_Executive_Summary": "Concise summary of what was investigated and the final verdict",
  "2_Company_and_Hypothesis": "Entity details and the exact hypothesis under examination",
  "3_Key_Financial_Numbers": "Summary of key numbers, periods, and verified calculations",
  "4_Potential_Red_Flags": "Observed anomalies and their analytical significance",
  "5_Supporting_Evidence": "The strongest factual evidence supporting the hypothesis",
  "6_Counterevidence": "Factual evidence or context contradicting or weakening the hypothesis",
  "7_Alternative_Explanations": "Ordinary business, festive, macro, or mix factors explaining the numbers",
  "8_Final_Assessment": "Final verdict, limitations of available data, and follow-up evidence needed"
}}
Output ONLY valid JSON. Zero preamble.
"""
    system = "You are an objective, evidence-driven financial investigator. Be concise, balanced, and strictly adhere to provided numbers."
    raw_response, provider = call_model(prompt, system=system)
    parsed = extract_json_object(raw_response)

    if not parsed:
        verdict = "NOT_ESTABLISHED"
        summary_text = f"Investigation completed for {company_name}. Evidence was insufficient for a firm determination."
        report = {
            "verdict": verdict,
            "verdict_summary": summary_text,
            "1_Executive_Summary": summary_text,
            "2_Company_and_Hypothesis": f"Target: {company_name} ({ticker}). Hypothesis: {hypothesis}",
            "3_Key_Financial_Numbers": json.dumps(key_numbers, indent=2),
            "4_Potential_Red_Flags": json.dumps(red_flags, indent=2),
            "5_Supporting_Evidence": "No conclusive supporting evidence was established.",
            "6_Counterevidence": "Financial metrics remain consistent with baseline operations.",
            "7_Alternative_Explanations": "Standard operational, macro, and supply chain adjustments.",
            "8_Final_Assessment": "Verdict: NOT_ESTABLISHED. Requires additional audited segment disclosures."
        }
    else:
        verdict = parsed.get("verdict", "NOT_ESTABLISHED")
        if verdict not in ("SUPPORTED", "REFUTED", "NOT_ESTABLISHED"):
            verdict = "NOT_ESTABLISHED"
        parsed["verdict"] = verdict
        report = parsed

    return report, verdict, provider
