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
Before you output your final deliverable, you MUST state your initial investigative thesis.
Our forensic pipeline unconditionally executes ALL 4 INVESTIGATIVE TOOLS simultaneously to stress-test your hypothesis across:
1. 'triangulate_peer_metric' — Scrapes and benchmarks direct sector rival spreads
2. 'search_concall_transcript' — Searches official earnings calls for management explanations
3. 'search_india_filings_news' — Searches live external news, statutory filings, and channel reports
4. 'get_multi_quarter_table' — Pulls trailing multi-quarter P&L and annual balance sheet ratios

Available Forensic Tool Manifest:
{manifest_str}

Instructions for Phase 1:
1. Formulate your preliminary hypothesis detailing what operational or accounting friction you suspect.
2. Provide specific operational focus parameters to calibrate the search tools:
   - 'concall_keywords': 2 to 4 space-separated operational keywords to probe in the concalls (e.g. 'inventory demand modern trade channel' or 'raw material price commodity inflation').
   - 'news_query': Specific query for external corporate filings or industry developments.
3. Output strictly valid JSON conforming to this schema:
{{
  "preliminary_thesis": "Your initial investigative hypothesis and angle of inquiry",
  "concall_keywords": "targeted keywords to probe in concall transcript",
  "news_query": "focused query to search external filings and market reports"
}}
"""
        raw_text, model_name = self.generate(turn1_prompt, system=system)
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

        turn2_prompt = f"""{prompt}

=== PHASE 2: EXHAUSTIVE FORENSIC SYNTHESIS WITH COMPLETE MULTI-TOOL TRIANGULATION ===
Initial Investigative Thesis:
"{preliminary_thesis or 'Cross-examining financial divergence against multi-source evidence.'}"

Verified Forensic Triangulation (ALL 4 Tools Executed):
{combined_tool_findings}

Task:
Integrate ALL verified tool findings above (Peer Benchmarks, Management Concall Commentary, Market Filings & News, and Trailing Multi-Quarter Ratios) alongside audited statements to formulate your complete, in-depth institutional position.
Provide full analytical depth—do not truncate, summarize trivially, or artificially shorten your reasoning.
Output strictly valid JSON conforming to the requested schema.
"""
        return self.generate_json(turn2_prompt, system=system)
