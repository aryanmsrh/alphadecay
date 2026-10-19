"""
ALPHA-DECAY LLM Client (Compatibility Wrapper).
Delegates all calls to the CentralModelProvider (Central configured Gemini primary, Ollama fallback).
Maintains backward compatibility while enforcing strict Gemini-first routing.
"""

from typing import Optional, Dict, Any, Tuple
from agent.llm_provider import central_provider, CentralModelProvider

class LLMClient:
    """
    Backwards-compatible wrapper delegating to CentralModelProvider.
    Ensures ALL calls route through Gemini primary with Ollama fallback only.
    """

    def __init__(self):
        self.provider = central_provider
        self.local_model = self.provider.ollama_model
        self.gemini_model = self.provider.gemini_model
        self.offline = self.provider.offline

    def call_gemini(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
        resp = self.provider.generate_text(prompt, system=system, task_name="gemini_legacy_call")
        return resp.text

    def call_ollama(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
        thought, text = self.provider._call_ollama(prompt, system=system)
        return text

    def route_query(self, prompt: str, system: Optional[str] = None, task_type: str = "general") -> Tuple[str, str]:
        """
        Routes all tasks through CentralModelProvider (Gemini-first, Ollama-fallback).
        Zero normal calls to Ollama when Gemini succeeds.
        """
        resp = self.provider.generate_text(prompt, system=system, task_name=task_type)
        return resp.thought, resp.text
