import sys
import re
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
    Unified LLM Client coordinating Local DeepSeek-R1-7B (Ollama) and Cloud Gemini 2.0 Flash.
    Features automatic fallback, offline toggle, and <think> tag extraction.
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
        Calls local Ollama endpoint running deepseek-r1:7b.
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

        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    return res.json().get("response", "").strip()
                else:
                    return f"[Ollama Error] Status {res.status_code}: {res.text}"
        except Exception as e:
            return f"[Ollama Connection Failed] {e}"

    def call_gemini(self, prompt: str, system: Optional[str] = None, model: str = "gemini-3.5-flash") -> str:
        """
        Calls Google Gemini Flash API (Free tier via Google AI Studio).
        """
        if self.offline or not self.gemini_key:
            return self.call_ollama(prompt, system=system)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048
            }
        }
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}

        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                    return "[Gemini] Empty candidate response."
                else:
                    print(f"[Gemini API Warning] Status {res.status_code}. Falling back to Ollama.")
                    return self.call_ollama(prompt, system=system)
        except Exception as e:
            print(f"[Gemini Error] {e}. Falling back to Ollama.")
            return self.call_ollama(prompt, system=system)

    def route_query(self, prompt: str, system: Optional[str] = None, task_type: str = "general") -> Tuple[str, str]:
        """
        Routes query according to optimal division of labor:
        - 'adversarial': Local DeepSeek-R1-7B (native chain-of-thought reflection).
        - 'concall_parsing' or 'synthesis': Gemini 2.0 Flash (high-context & prose), fallback to Ollama.
        - 'general': Local DeepSeek-R1-7B.
        Returns: (thought_process, final_response)
        """
        if self.offline:
            raw = self.call_ollama(prompt, system=system)
            return self.parse_think_reasoning(raw)

        if task_type == "adversarial":
            # Local DeepSeek-R1 excels at internal debate and self-falsification
            raw = self.call_ollama(prompt, system=system)
            if "Connection Failed" not in raw and "Error" not in raw:
                return self.parse_think_reasoning(raw)
            # Fallback to Gemini if Ollama offline
            raw_gemini = self.call_gemini(prompt, system=system)
            return "", raw_gemini

        elif task_type in ("concall_parsing", "synthesis"):
            if self.gemini_key:
                raw_gemini = self.call_gemini(prompt, system=system)
                return "", raw_gemini
            raw = self.call_ollama(prompt, system=system)
            return self.parse_think_reasoning(raw)

        raw = self.call_ollama(prompt, system=system)
        return self.parse_think_reasoning(raw)

if __name__ == "__main__":
    client = LLMClient()
    print("Testing LLMClient with unified local model:", client.local_model)
    thought, answer = client.route_query("Explain in 1 sentence what debtor days measures in corporate finance.", task_type="general")
    if thought:
        print(f"[Thought Trace]: {thought[:150]}...")
    print(f"[Final Answer]: {answer}")
