import sys
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from config import (
    OLLAMA_BASE_URL,
    LOCAL_MODEL_NAME,
    LOCAL_REASONING_MODEL,
    GEMINI_API_KEY,
    USE_OFFLINE_MODE
)

class LLMClient:
    """
    Unified LLM Client coordinating Local Ollama models and Cloud Gemini 2.0 Flash.
    Features automatic fallback, offline toggle, and specialized routing.
    """

    def __init__(self):
        self.ollama_url = OLLAMA_BASE_URL.rstrip("/")
        self.gemini_key = GEMINI_API_KEY
        self.local_model = LOCAL_MODEL_NAME
        self.reasoning_model = LOCAL_REASONING_MODEL
        self.offline = USE_OFFLINE_MODE

    def call_ollama(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
        """
        Calls local Ollama endpoint (e.g. qwen2.5-coder:7b or deepseek-r1:14b).
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
            with httpx.Client(timeout=45.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    return res.json().get("response", "").strip()
                else:
                    return f"[Ollama Error] Status {res.status_code}: {res.text}"
        except Exception as e:
            return f"[Ollama Connection Failed] {e}"

    def call_gemini(self, prompt: str, system: Optional[str] = None, model: str = "gemini-2.0-flash") -> str:
        """
        Calls Google Gemini 2.0 Flash API (Free tier via Google AI Studio).
        """
        if self.offline or not self.gemini_key:
            return self.call_ollama(prompt, system=system)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2}
        }

        try:
            with httpx.Client(timeout=30.0) as client:
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

    def route_query(self, prompt: str, system: Optional[str] = None, task_type: str = "general") -> str:
        """
        Routes query according to optimal division of labor:
        - 'adversarial': Routes to Local DeepSeek-R1 (excels at internal reasoning/think tags)
        - 'concall_parsing' or 'synthesis': Routes to Gemini 2.0 Flash (high-context & prose)
        - 'general': Defaults to local Qwen2.5-Coder-7B
        """
        if self.offline:
            return self.call_ollama(prompt, system=system, model=self.local_model)

        if task_type == "adversarial":
            # Test local reasoning model first
            response = self.call_ollama(prompt, system=system, model=self.reasoning_model)
            if "Connection Failed" not in response:
                return response
            return self.call_gemini(prompt, system=system)

        elif task_type in ("concall_parsing", "synthesis"):
            if self.gemini_key:
                return self.call_gemini(prompt, system=system)
            return self.call_ollama(prompt, system=system, model=self.local_model)

        return self.call_ollama(prompt, system=system, model=self.local_model)

if __name__ == "__main__":
    client = LLMClient()
    print("Testing LLMClient...")
    print(f"Local model configured: {client.local_model}")
    print(f"Reasoning model configured: {client.reasoning_model}")
    print(f"Testing local Ollama connection with model '{client.local_model}'...")
    test_res = client.call_ollama("Respond with 'Ollama is alive and ready for AlphaDecay!' in exactly one line.")
    print(f"Ollama Response:\n{test_res}")
