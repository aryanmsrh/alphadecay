import json
import os
import re
import time
from typing import Any, Callable, Dict, Optional, Tuple
import httpx
from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_TIMEOUT,
    GEMINI_TIMEOUT,
)


def clean_deepseek_reasoning(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in cleaned and "</think>" not in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1].strip()
        else:
            cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL).strip()
    if not cleaned and "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1].strip()
    cleaned = re.sub(r"\s*[\u4e00-\u9fff]+\s*", " ", cleaned)
    return cleaned.strip()


def unwrap_outer_dict(data: Any) -> Any:
    if isinstance(data, dict) and len(data) == 1:
        k = list(data.keys())[0]
        if k.lower() in ("json", "response", "result", "output", "data", "report", "brief", "schema") and isinstance(data[k], dict):
            return unwrap_outer_dict(data[k])
    return data


def parse_json_strictly(text: str) -> Dict[str, Any]:
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return unwrap_outer_dict(parsed)
        return parsed
    except Exception:
        raise ValueError("Model returned invalid JSON syntax: " + text)


class LLM:
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: str = OLLAMA_BASE_URL,
        timeout: Optional[float] = None,
        gemini_key: Optional[str] = None,
        ollama_model: str = OLLAMA_MODEL,
    ):
        self.model = model or GEMINI_MODEL
        self.base_url = base_url.rstrip("/")
        self.ollama_model = ollama_model
        self.gemini_key = gemini_key or GEMINI_API_KEY
        if "gemini" in str(self.model).lower():
            self.timeout = timeout or GEMINI_TIMEOUT
        else:
            self.timeout = timeout or OLLAMA_TIMEOUT

    def _generate_gemini(self, prompt: str, system: Optional[str] = None) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.gemini_key}"
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }
        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}],
            }

        timeout_config = httpx.Timeout(self.timeout, connect=15.0, read=self.timeout)
        max_attempts = 3
        last_err: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=timeout_config) as client:
                    res = client.post(url, json=payload)
                    if res.status_code != 200:
                        raise RuntimeError(f"Gemini API returned {res.status_code}: {res.text}")
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError(f"Gemini API returned no candidates: {data}")
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if not parts:
                        raise RuntimeError(f"Gemini API returned empty parts: {data}")

                    clean_parts = [
                        p.get("text", "") for p in parts if not p.get("thought")
                    ]
                    raw_text = clean_parts[-1] if clean_parts else parts[0].get("text", "")
                    return raw_text
            except Exception as e:
                last_err = e
                err_str = str(e)
                if attempt < max_attempts and ("503" in err_str or "429" in err_str or "timed out" in err_str.lower()):
                    time.sleep(2.0 * attempt)
                    continue
                raise RuntimeError(f"Gemini Cloud inference failed: {e}")

        raise RuntimeError(f"Gemini Cloud inference failed: {last_err}")

    def _generate_ollama(self, prompt: str, system: Optional[str] = None) -> str:
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "60m",
            "options": {
                "temperature": 0.2,
                "top_p": 0.95,
                "repeat_penalty": 1.0,
                "num_ctx": 8192,
                "num_predict": 2048,
            },
        }
        if system:
            payload["system"] = system
        timeout_config = httpx.Timeout(self.timeout, connect=60.0)
        with httpx.Client(timeout=timeout_config) as client:
            res = client.post(endpoint, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Ollama returned {res.status_code}: {res.text}")
            res_json = res.json()
            raw_text = res_json.get("response", "")
            if not raw_text.strip():
                raise RuntimeError(f"Ollama returned empty response: {res_json}")
            cleaned = clean_deepseek_reasoning(raw_text)
            return cleaned if cleaned else raw_text

    def generate(self, prompt: str, system: Optional[str] = None) -> Tuple[str, str]:
        model_lower = str(self.model).lower()
        if model_lower.startswith("gemini"):
            if not self.gemini_key:
                raise ValueError("GEMINI_API_KEY is not configured")
            raw_text = self._generate_gemini(prompt, system=system)
            return raw_text, self.model
        else:
            raw_text = self._generate_ollama(prompt, system=system)
            return raw_text, self.ollama_model

    def generate_json(self, prompt: str, system: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
        raw_text, model_name = self.generate(prompt, system=system)
        parsed = parse_json_strictly(raw_text)
        return parsed, model_name

    def generate_with_tools(
        self,
        prompt: str,
        finder: Any,
        company_name: str,
        ticker: str,
        dossier: Dict[str, Any],
        system: Optional[str] = None,
        event_callback: Optional[Callable[..., None]] = None,
        max_tool_turns: int = 2,
        anomaly: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        manifest_str = finder.get_tool_manifest() if (finder and hasattr(finder, "get_tool_manifest")) else ""
        anomaly_metric = (anomaly.get("metric", "Financial Metric") if anomaly else "Financial Metric")
        anomaly_id = (anomaly.get("id", "") if anomaly else "")
        anomaly_traj = (anomaly.get("multi_quarter_trajectory", "") if anomaly else "")

        turn1_prompt = f"""Target Entity: {company_name} ({ticker})
Active Financial Anomaly: {anomaly_metric} (ID: {anomaly_id})
Trajectory: {anomaly_traj}

Context:
{prompt}

=== PHASE 1: MANDATORY INVESTIGATIVE TRIANGULATION ===
Before you output your final deliverable, you MUST select an investigative tool from the manifest to triangulate and stress-test your hypothesis against sector peers, concall disclosures, or historical filings.

Available Investigative Tools:
{manifest_str}

Instructions for Phase 1:
1. Formulate your preliminary hypothesis on what you suspect management is hiding or how the operational mechanics work.
2. Select the most relevant tool from the manifest to cross-examine and verify (e.g. 'triangulate_peer_metric' to check sector peers, 'search_concall_transcript' to find management commentary, or 'search_india_filings_news' for external corporate actions).
3. Output strictly valid JSON with this exact schema:
{{
  "preliminary_thesis": "Your 1-2 sentence initial investigative hypothesis",
  "action": "call_tool",
  "tool_name": "triangulate_peer_metric" | "search_concall_transcript" | "search_india_filings_news" | "get_multi_quarter_table",
  "tool_args": {{ ... }}
}}
"""
        raw_text, model_name = self.generate(turn1_prompt, system=system)
        parsed_turn1 = parse_json_strictly(raw_text)

        tool_name = ""
        tool_args: Dict[str, Any] = {}
        preliminary_thesis = ""

        if isinstance(parsed_turn1, dict):
            preliminary_thesis = str(parsed_turn1.get("preliminary_thesis", "")).strip()
            tool_name = str(parsed_turn1.get("tool_name", "")).strip().lower()
            if isinstance(parsed_turn1.get("tool_args"), dict):
                tool_args = parsed_turn1["tool_args"]

        valid_tools = ("triangulate_peer_metric", "search_concall_transcript", "search_india_filings_news", "get_multi_quarter_table")
        if tool_name not in valid_tools:
            tool_name = "triangulate_peer_metric"
            tool_args = {"metric_id": anomaly_id or "signal_margin_cost_dynamics"}

        if tool_name == "triangulate_peer_metric" and not tool_args.get("metric_id"):
            tool_args["metric_id"] = anomaly_id or "signal_margin_cost_dynamics"
        elif tool_name == "search_concall_transcript" and not tool_args.get("keywords"):
            tool_args["keywords"] = anomaly_metric.lower()
        elif tool_name == "search_india_filings_news" and not tool_args.get("query"):
            tool_args["query"] = f"{anomaly_metric} financial disclosures"
        elif tool_name == "get_multi_quarter_table" and not tool_args.get("metric_id"):
            tool_args["metric_id"] = anomaly_id or "margin"

        if preliminary_thesis and event_callback:
            event_callback({
                "step": "TRIANGULATION",
                "message": f"Investigative thesis: {preliminary_thesis}",
                "hypothesis": preliminary_thesis,
            })

        tool_output = finder.execute_tool(
            tool_name=tool_name,
            tool_args=tool_args,
            company_name=company_name,
            ticker=ticker,
            dossier=dossier,
            event_callback=event_callback,
        )

        turn2_prompt = f"""{prompt}

=== PHASE 2: FINAL FORENSIC DELIVERABLE WITH VERIFIED TRIANGULATION ===
Initial Investigative Thesis:
"{preliminary_thesis or 'Cross-examining financial divergence against external disclosures.'}"

Verified Tool Findings from '{tool_name}' with args {json.dumps(tool_args)}:
{tool_output}

Task:
Integrate the verified tool findings above alongside the audited statements to formulate your final position.
Output strictly valid JSON conforming to the requested schema.
"""
        return self.generate_json(turn2_prompt, system=system)
