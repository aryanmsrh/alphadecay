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


def sanitize_json_text(text: str) -> str:
    clean = clean_deepseek_reasoning(text)
    if not clean:
        clean = text
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL)
    if match:
        clean = match.group(1).strip()
    else:
        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            clean = clean[start : end + 1]
        elif "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                clean = text[start : end + 1]
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
    clean = re.sub(r",\s*([}\]])", r"\1", clean)
    clean = re.sub(r"\s*[\u4e00-\u9fff]+\s*", " ", clean)
    return clean.strip()


def unwrap_outer_dict(data: Any) -> Any:
    if isinstance(data, dict) and len(data) == 1:
        k = list(data.keys())[0]
        if k.lower() in ("json", "response", "result", "output", "data", "report", "brief", "schema") and isinstance(data[k], dict):
            return unwrap_outer_dict(data[k])
    return data


def parse_json_strictly(text: str) -> Dict[str, Any]:
    clean = clean_deepseek_reasoning(text)
    if clean:
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return unwrap_outer_dict(parsed)
            return parsed
        except Exception:
            pass
    sanitized = sanitize_json_text(text)
    try:
        parsed = json.loads(sanitized)
        if isinstance(parsed, dict):
            return unwrap_outer_dict(parsed)
        return parsed
    except Exception:
        raise ValueError(f"Failed to parse valid JSON from response: {clean[:200] or text[:200]}")


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

        timeout_config = httpx.Timeout(self.timeout, connect=30.0)
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
            raw_text = parts[0].get("text", "")
            return raw_text

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
        if model_lower.startswith("gemini") and self.gemini_key:
            try:
                raw_text = self._generate_gemini(prompt, system=system)
                return raw_text, self.model
            except Exception:
                raw_text = self._generate_ollama(prompt, system=system)
                return raw_text, self.ollama_model
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
        turn1_prompt = f"""{prompt}

Available Mid-Run Tools:
{manifest_str}

Tool Call Instruction:
You may output a tool request JSON if you require additional verification before delivering your final brief:
{{"action": "call_tool", "tool_name": "...", "tool_args": {{...}}}}
OR output your final schema JSON directly.
"""
        raw_text, model_name = self.generate(turn1_prompt, system=system)
        parsed_turn1 = None
        try:
            parsed_turn1 = parse_json_strictly(raw_text)
        except Exception:
            pass

        tool_call_detected = False
        tool_name = ""
        tool_args: Dict[str, Any] = {}

        if isinstance(parsed_turn1, dict):
            if parsed_turn1.get("action") == "call_tool" or "tool_name" in parsed_turn1:
                tool_name = parsed_turn1.get("tool_name", "")
                tool_args = parsed_turn1.get("tool_args", {})
                if tool_name and finder:
                    tool_call_detected = True

        if tool_call_detected:
            tool_output = finder.execute_tool(
                tool_name=tool_name,
                tool_args=tool_args,
                company_name=company_name,
                ticker=ticker,
                dossier=dossier,
                event_callback=event_callback,
            )
            turn2_prompt = f"""{prompt}

Tool Execution Result for '{tool_name}':
{tool_output}

Now deliver your final forensic analysis. Output strictly valid JSON conforming to the requested schema.
"""
            return self.generate_json(turn2_prompt, system=system)

        has_final_keys = False
        if isinstance(parsed_turn1, dict):
            if "verdict" in parsed_turn1 or "counterargument" in parsed_turn1:
                has_final_keys = True

        if finder:
            metric_id = (anomaly.get("id", "") if anomaly else "") or "signal_margin_cost_dynamics"
            keywords = (anomaly.get("metric", "") if anomaly else "") or "operating margin inventory receivables"
            t1_res = finder.execute_tool("triangulate_peer_metric", {"metric_id": metric_id}, company_name, ticker, dossier, event_callback)
            t2_res = finder.execute_tool("search_concall_transcript", {"keywords": keywords}, company_name, ticker, dossier, event_callback)

            if has_final_keys:
                return parsed_turn1, model_name

            turn2_prompt = f"""{prompt}

Verified Mid-Run Research Findings:
- Peer Metric Triangulation:
{t1_res}

- Earnings Concall Records:
{t2_res}

Now deliver your final forensic analysis. Output strictly valid JSON conforming to the requested schema.
"""
            return self.generate_json(turn2_prompt, system=system)

        if has_final_keys:
            return parsed_turn1, model_name

        return self.generate_json(prompt, system=system)


def call_model(prompt: str, system: Optional[str] = None) -> Tuple[str, str]:
    return LLM().generate(prompt, system=system)


def call_ollama(prompt: str, system: Optional[str] = None) -> str:
    text, _ = LLM().generate(prompt, system=system)
    return text


def extract_json_object(text: str) -> Dict[str, Any]:
    return parse_json_strictly(text)
