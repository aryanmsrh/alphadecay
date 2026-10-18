import sys
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from config import (
    OLLAMA_BASE_URL,
    LOCAL_MODEL,
    GEMINI_API_KEY,
    USE_OFFLINE_MODE
)

class LLMClient:
    """
    Unified, 100% Verbose LLM Client coordinating Local DeepSeek-R1-7B (Ollama) and Cloud Gemini 3.5 Flash.
    Displays every API request, latency, raw token stream, internal thoughts, and completion verbatim.
    """

    def __init__(self):
        self.ollama_url = OLLAMA_BASE_URL.rstrip("/")
        self.gemini_key = GEMINI_API_KEY
        self.local_model = LOCAL_MODEL
        self.offline = USE_OFFLINE_MODE

    @staticmethod
    def parse_think_reasoning(text: str) -> Tuple[str, str]:
        """
        Separates DeepSeek-R1's internal reasoning (<think>...</think>) from the final output.
        Returns: (internal_reasoning, clean_output)
        """
        match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            clean_output = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return reasoning, clean_output
        return "", text.strip()

    def call_ollama(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
        """
        Calls local Ollama endpoint running deepseek-r1:7b with complete request/response verbosity.
        """
        target_model = model or self.local_model
        endpoint = f"{self.ollama_url}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        if system:
            payload["system"] = system

        print("\n" + "=" * 70)
        print(f"[HTTP API REQUEST -> Local Ollama LLM]")
        print(f"  • Endpoint: {endpoint}")
        print(f"  • Model:    {target_model}")
        if system:
            print(f"  • System Prompt:\n{system.strip()}")
        print(f"  • User Prompt:\n{prompt.strip()}")
        print("=" * 70)

        t0 = time.time()
        try:
            with httpx.Client(timeout=90.0) as client:
                res = client.post(endpoint, json=payload)
                elapsed = round(time.time() - t0, 2)
                if res.status_code == 200:
                    raw_resp = res.json().get("response", "").strip()
                    print("\n" + "=" * 70)
                    print(f"[HTTP API RESPONSE <- Local Ollama LLM ({elapsed}s | Status: {res.status_code})]")
                    print(f"[RAW VERBATIM LLM RESPONSE]:\n{raw_resp}")
                    print("=" * 70)
                    return raw_resp
                else:
                    err_msg = f"[Ollama Error] Status {res.status_code}: {res.text}"
                    print(f"\n{err_msg}")
                    return err_msg
        except Exception as e:
            err_msg = f"[Ollama Connection Failed after {round(time.time() - t0, 2)}s] {e}"
            print(f"\n{err_msg}")
            return err_msg

    def call_gemini(self, prompt: str, system: Optional[str] = None, model: str = "gemini-2.5-flash") -> str:
        """
        Calls Google Gemini API with complete request/response verbosity and automatic local fallback.
        """
        if self.offline or not self.gemini_key:
            print("\n[LLM Client] Offline mode enabled or no Gemini key found. Directing to Ollama.")
            return self.call_ollama(prompt, system=system)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        masked_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=***"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048
            }
        }
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}

        print("\n" + "=" * 70)
        print(f"[HTTP API REQUEST -> Google Gemini Cloud API]")
        print(f"  • Endpoint: {masked_url}")
        print(f"  • Model:    {model}")
        if system:
            print(f"  • System Instruction:\n{system.strip()}")
        print(f"  • User Prompt:\n{prompt.strip()}")
        print("=" * 70)

        t0 = time.time()
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(url, json=payload)
                elapsed = round(time.time() - t0, 2)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    raw_text = ""
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                    print("\n" + "=" * 70)
                    print(f"[HTTP API RESPONSE <- Google Gemini Cloud API ({elapsed}s | Status: {res.status_code})]")
                    print(f"[RAW VERBATIM GEMINI RESPONSE]:\n{raw_text}")
                    print("=" * 70)
                    return raw_text
                else:
                    print(f"\n[Gemini API Warning] Status {res.status_code}: {res.text}. Failing over to Ollama.")
                    return self.call_ollama(prompt, system=system)
        except Exception as e:
            print(f"\n[Gemini API Exception after {round(time.time() - t0, 2)}s] {e}. Failing over to Ollama.")
            return self.call_ollama(prompt, system=system)

    def route_query(self, prompt: str, system: Optional[str] = None, task_type: str = "general") -> Tuple[str, str]:
        """
        Routes query according to optimal division of labor:
        - 'adversarial': Local DeepSeek-R1-7B (native chain-of-thought reflection).
        - 'concall_parsing' or 'synthesis': Gemini 2.5 Flash (high speed & prose), failover to Ollama.
        - 'general': Local DeepSeek-R1-7B.
        Returns: (thought_process, final_response)
        """
        print(f"\n>>> [LLM Router] Routing task '{task_type}' (Local Model: '{self.local_model}', Cloud: 'gemini-2.5-flash')")

        if self.offline:
            raw = self.call_ollama(prompt, system=system)
            return self.parse_think_reasoning(raw)

        if task_type == "adversarial":
            raw = self.call_ollama(prompt, system=system)
            if "Connection Failed" not in raw and "Error" not in raw:
                return self.parse_think_reasoning(raw)
            print("\n[Failover Triggered] Local Ollama unavailable. Diverting to Gemini Cloud API...")
            raw_gemini = self.call_gemini(prompt, system=system)
            return self.parse_think_reasoning(raw_gemini)

        elif task_type in ("concall_parsing", "synthesis"):
            if self.gemini_key:
                raw_gemini = self.call_gemini(prompt, system=system)
                if raw_gemini and "[Ollama Error]" not in raw_gemini and "[Ollama Connection Failed]" not in raw_gemini:
                    return self.parse_think_reasoning(raw_gemini)
            raw = self.call_ollama(prompt, system=system)
            return self.parse_think_reasoning(raw)

        raw = self.call_ollama(prompt, system=system)
        return self.parse_think_reasoning(raw)
