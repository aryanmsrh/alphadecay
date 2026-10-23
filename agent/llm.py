import json
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import httpx
from agent.prompts import (
    build_turn1_triangulation_prompt,
    build_turn2_synthesis_prompt,
)
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
    cleaned = re.sub(r"\s*[\u4e00-\u9fff]+\s*", " ", cleaned)
    return cleaned.strip()


def unwrap_outer_dict(data: Any) -> Any:
    if isinstance(data, dict) and len(data) == 1:
        k = list(data.keys())[0]
        if k.lower() in ("json", "response", "result", "output", "data", "report", "brief", "schema") and isinstance(data[k], dict):
            return unwrap_outer_dict(data[k])
    return data


def parse_json_strictly(text: str) -> Dict[str, Any]:
    # 1. Strip think blocks & reasoning tags
    clean = clean_deepseek_reasoning(text)

    # 2. Try direct JSON load
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return unwrap_outer_dict(parsed)
        return parsed
    except Exception:
        pass

    # 3. Extract JSON enclosed inside markdown code fences: ```json ... ``` or ``` ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1).strip())
            if isinstance(parsed, dict):
                return unwrap_outer_dict(parsed)
            return parsed
        except Exception:
            pass

    # 4. Extract outermost JSON object between first '{' and last '}'
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = clean[start : end + 1].strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return unwrap_outer_dict(parsed)
            return parsed
        except Exception:
            # 5. Fix common LLM syntax flaws like trailing commas before closing braces
            fixed = re.sub(r",\s*([\}\]])", r"\1", candidate)
            try:
                parsed = json.loads(fixed)
                if isinstance(parsed, dict):
                    return unwrap_outer_dict(parsed)
                return parsed
            except Exception:
                pass

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

    def _generate_gemini(
        self,
        prompt: str,
        system: Optional[str] = None,
        event_callback: Optional[Callable[..., None]] = None,
        label: str = "Forensic Reasoning",
    ) -> str:
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

        timeout_config = httpx.Timeout(self.timeout, connect=20.0, read=self.timeout)
        backoff_delays = [15.0, 35.0, 65.0, 120.0, 180.0, 240.0]
        max_attempts = len(backoff_delays) + 1  # 7 attempts
        last_err: Optional[Exception] = None

        def _calc_wait(att: int) -> Tuple[float, str]:
            base = backoff_delays[att - 1]
            jitter = random.uniform(1.0, 5.0)
            wt = round(base + jitter, 1)
            total_sec = int(wt)
            if total_sec >= 60:
                fmt = f"{total_sec // 60}m {total_sec % 60}s"
            else:
                fmt = f"{wt}s"
            return wt, fmt

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=timeout_config) as client:
                    response = client.post(url, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            raise RuntimeError("Gemini API returned no candidates")
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text_parts = [p.get("text", "") for p in parts if not p.get("thought")]
                        raw_text = "".join(text_parts).strip()
                        if not raw_text:
                            raise RuntimeError("Gemini API returned empty text content")
                        return raw_text

                    err_body = response.text
                    # Check for transient capacity shed (503), rate limit (429), or gateway errors (502, 504)
                    if response.status_code in (503, 429, 502, 504) and attempt < max_attempts:
                        wait_time, wait_str = _calc_wait(attempt)
                        if event_callback:
                            event_callback({
                                "step": "RETRY",
                                "message": f"Gemini high demand ({response.status_code}). Retrying with backoff in {wait_str} (attempt {attempt}/{max_attempts})...",
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "wait_time": wait_time,
                                "model": self.model,
                            })
                        time.sleep(wait_time)
                        continue

                    raise RuntimeError(f"Gemini API returned {response.status_code}: {err_body}")

            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in ["503", "429", "502", "504", "timed out", "readtimeout", "connecterror"])
                if attempt < max_attempts and is_transient:
                    wait_time, wait_str = _calc_wait(attempt)
                    if event_callback:
                        event_callback({
                            "step": "RETRY",
                            "message": f"Gemini connection latency spike ({type(e).__name__}). Retrying in {wait_str} (attempt {attempt}/{max_attempts})...",
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "wait_time": wait_time,
                            "model": self.model,
                        })
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(f"Gemini Cloud inference failed: {e}")

        raise RuntimeError(f"Gemini Cloud inference failed after {max_attempts} attempts: {last_err}")

    def _generate_ollama(
        self,
        prompt: str,
        system: Optional[str] = None,
        event_callback: Optional[Callable[..., None]] = None,
        label: str = "DeepSeek Reasoning",
    ) -> str:
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
        timeout_config = httpx.Timeout(self.timeout, connect=60.0, read=self.timeout)

        with httpx.Client(timeout=timeout_config) as client:
            response = client.post(endpoint, json=payload)
            if response.status_code != 200:
                err_body = response.text
                raise RuntimeError(f"Ollama returned {response.status_code}: {err_body}")
            data = response.json()
            raw_text = data.get("response", "")

        cleaned = clean_deepseek_reasoning(raw_text)
        return cleaned if cleaned else raw_text

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        event_callback: Optional[Callable[..., None]] = None,
        label: str = "Model Inference",
    ) -> Tuple[str, str]:
        model_lower = str(self.model).lower()
        if model_lower.startswith("gemini"):
            if not self.gemini_key:
                raise ValueError("GEMINI_API_KEY is not configured")
            raw_text = self._generate_gemini(prompt, system=system, event_callback=event_callback, label=label)
            return raw_text, self.model
        else:
            raw_text = self._generate_ollama(prompt, system=system, event_callback=event_callback, label=label)
            return raw_text, self.ollama_model

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        event_callback: Optional[Callable[..., None]] = None,
        label: str = "JSON Extraction",
    ) -> Tuple[Dict[str, Any], str]:
        raw_text, model_name = self.generate(prompt, system=system, event_callback=event_callback, label=label)
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

        if event_callback:
            event_callback({
                "step": "PHASE1_START",
                "message": f"Formulating investigative hypothesis and targeting search parameters for {anomaly_metric}...",
                "metric": anomaly_metric,
            })

        turn1_prompt = build_turn1_triangulation_prompt(
            company_name=company_name,
            ticker=ticker,
            anomaly_metric=anomaly_metric,
            anomaly_id=anomaly_id,
            anomaly_traj=anomaly_traj,
            context_prompt=prompt,
            manifest_str=manifest_str,
        )
        raw_text, model_name = self.generate(
            turn1_prompt,
            system=system,
            event_callback=event_callback,
            label=f"Phase 1: Triangulation ({anomaly_metric})",
        )
        parsed_turn1 = parse_json_strictly(raw_text)

        preliminary_thesis = ""
        concall_keywords = anomaly_metric.lower()
        news_query = f"{company_name} {anomaly_metric} financial disclosures"

        if isinstance(parsed_turn1, dict):
            preliminary_thesis = str(parsed_turn1.get("preliminary_thesis", "") or parsed_turn1.get("hypothesis", "")).strip()
            if parsed_turn1.get("concall_keywords"):
                concall_keywords = str(parsed_turn1["concall_keywords"]).strip()
            elif isinstance(parsed_turn1.get("tool_args"), dict) and parsed_turn1["tool_args"].get("keywords"):
                concall_keywords = str(parsed_turn1["tool_args"]["keywords"]).strip()

            if parsed_turn1.get("news_query"):
                news_query = str(parsed_turn1["news_query"]).strip()
            elif isinstance(parsed_turn1.get("tool_args"), dict) and parsed_turn1["tool_args"].get("query"):
                news_query = str(parsed_turn1["tool_args"]["query"]).strip()

        if preliminary_thesis and event_callback:
            event_callback({
                "step": "TRIANGULATION",
                "message": f"Investigative thesis: {preliminary_thesis}",
                "hypothesis": preliminary_thesis,
            })

        # Unconditionally execute ALL 4 investigative tools
        all_tools = [
            ("triangulate_peer_metric", {"metric_id": anomaly_id or "signal_margin_cost_dynamics"}),
            ("search_concall_transcript", {"keywords": concall_keywords}),
            ("search_india_filings_news", {"query": news_query}),
            ("get_multi_quarter_table", {"metric_id": anomaly_id or "margin"}),
        ]

        tool_outputs = []
        for t_name, t_args in all_tools:
            out = finder.execute_tool(
                tool_name=t_name,
                tool_args=t_args,
                company_name=company_name,
                ticker=ticker,
                dossier=dossier,
                event_callback=event_callback,
            )
            tool_outputs.append((t_name, t_args, out))

        findings_blocks = []
        for t_name, t_args, out in tool_outputs:
            findings_blocks.append(f"### TOOL: {t_name.upper()} (args: {json.dumps(t_args)})\n{out}")
        combined_tool_findings = "\n\n".join(findings_blocks)

        if event_callback:
            event_callback({
                "step": "PHASE2_START",
                "message": f"Synthesizing complete multi-tool triangulation into institutional verdict...",
                "metric": anomaly_metric,
            })

        turn2_prompt = build_turn2_synthesis_prompt(
            context_prompt=prompt,
            preliminary_thesis=preliminary_thesis,
            combined_tool_findings=combined_tool_findings,
        )
        return self.generate_json(
            turn2_prompt,
            system=system,
            event_callback=event_callback,
            label="Phase 2: Complete Forensic Synthesis",
        )
