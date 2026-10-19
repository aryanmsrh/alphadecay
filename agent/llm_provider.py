"""
ALPHA-DECAY Centralized Model Provider Abstraction.
Primary Model: Gemini (configurable via GEMINI_MODEL, default: gemini-3.5-flash-lite).
Fallback Model: Local Ollama (configurable via OLLAMA_FALLBACK_MODEL, default: deepseek-r1:7b).

Non-negotiable routing invariants:
1. Gemini is the default and primary for EVERY model-powered operation.
2. Zero normal-workflow calls to Ollama when Gemini succeeds.
3. Bounded exponential backoff with jitter on transient errors (429, 503, timeout).
4. Permanent errors (401, 403, 400, daily quota exhaustion) diagnosed clearly without pointless delays.
5. Structured outputs validated via Pydantic schemas with bounded repair paths and true JSON mode.
6. Explicit, actionable failures if both providers fail. Never fabricate.
7. Secrets (API keys) never exposed in URLs, headers, or exception logs.
"""

import sys
import os
import re
import time
import json
import random
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Type, TypeVar
from pydantic import BaseModel, ValidationError

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    OLLAMA_BASE_URL,
    OLLAMA_FALLBACK_MODEL,
    USE_OFFLINE_MODE
)

logger = logging.getLogger("alphadecay.llm")
T = TypeVar("T", bound=BaseModel)


class ModelExecutionError(RuntimeError):
    """Raised when both primary and fallback model providers fail to produce a validated result."""
    pass


class ModelConfigurationError(ValueError):
    """Raised when API configuration or credentials are fundamentally invalid."""
    pass


class GeminiResponseBlockedError(RuntimeError):
    """Raised when Gemini candidate or prompt is blocked due to safety or finish reason."""
    pass


class ModelResponse(BaseModel):
    """Standardized result envelope for every model execution."""
    text: str
    thought: str = ""
    provider_used: str  # "gemini" or "ollama"
    model_name: str
    fallback_invoked: bool = False
    fallback_reason: Optional[str] = None
    latency_seconds: float = 0.0
    parsed_json: Optional[Dict[str, Any]] = None


class CentralModelProvider:
    """
    Central provider orchestrating Gemini primary with local Ollama fallback.
    Maintains a reusable connection pool, explicit timeouts, sanitized logging,
    and strict schema enforcement.
    """

    ALLOWED_THINKING_LEVELS = {"LOW", "MEDIUM", "HIGH"}

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        thinking_level: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        use_offline_mode: Optional[bool] = None,
        max_retries: int = 3,
        gemini_timeout: float = 45.0,
        ollama_timeout: float = 90.0
    ):
        self.gemini_key = gemini_api_key if gemini_api_key is not None else GEMINI_API_KEY
        self.gemini_model = gemini_model or GEMINI_MODEL or "gemini-3.5-flash-lite"
        
        raw_level = (thinking_level or GEMINI_THINKING_LEVEL or "HIGH").upper()
        if raw_level not in self.ALLOWED_THINKING_LEVELS:
            logger.warning(f"Invalid thinking level '{raw_level}'; defaulting to 'HIGH'")
            raw_level = "HIGH"
        self.thinking_level = raw_level

        self.ollama_url = (ollama_base_url or OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        self.ollama_model = ollama_model or OLLAMA_FALLBACK_MODEL or "deepseek-r1:7b"
        self.offline = use_offline_mode if use_offline_mode is not None else USE_OFFLINE_MODE
        self.max_retries = max(1, max_retries)
        self.gemini_timeout = gemini_timeout
        self.ollama_timeout = ollama_timeout

        # Shared client instance with connection pool and explicit timeouts
        self._gemini_client: Optional[httpx.Client] = None
        self._ollama_client: Optional[httpx.Client] = None

    def _get_gemini_client(self) -> httpx.Client:
        if self._gemini_client is None or self._gemini_client.is_closed:
            timeout = httpx.Timeout(
                timeout=self.gemini_timeout,
                connect=10.0,
                read=self.gemini_timeout,
                write=10.0,
                pool=10.0
            )
            self._gemini_client = httpx.Client(timeout=timeout)
        return self._gemini_client

    def _get_ollama_client(self) -> httpx.Client:
        if self._ollama_client is None or self._ollama_client.is_closed:
            timeout = httpx.Timeout(
                timeout=self.ollama_timeout,
                connect=10.0,
                read=self.ollama_timeout,
                write=10.0,
                pool=10.0
            )
            self._ollama_client = httpx.Client(timeout=timeout)
        return self._ollama_client

    def close(self):
        """Cleanly close underlying connection pools."""
        if self._gemini_client and not self._gemini_client.is_closed:
            self._gemini_client.close()
        if self._ollama_client and not self._ollama_client.is_closed:
            self._ollama_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def parse_think_reasoning(text: str) -> Tuple[str, str]:
        """Separates <think>...</think> chain-of-thought blocks from clean output."""
        match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            clean_output = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return reasoning, clean_output
        return "", text.strip()

    @staticmethod
    def extract_json_block(text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses a valid JSON object or array from text."""
        if not text or not isinstance(text, str):
            return None
        clean = text.strip()
        # Direct parse
        try:
            val = json.loads(clean)
            if isinstance(val, (dict, list)):
                return val
        except Exception:
            pass
        # Search for markdown fenced JSON: ```json ... ```
        fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", clean, flags=re.DOTALL)
        if fenced:
            try:
                val = json.loads(fenced.group(1).strip())
                if isinstance(val, (dict, list)):
                    return val
            except Exception:
                pass
        # Search for outermost curly braces
        match = re.search(r"(\{.*\})", clean, flags=re.DOTALL)
        if match:
            try:
                val = json.loads(match.group(1).strip())
                if isinstance(val, (dict, list)):
                    return val
            except Exception:
                pass
        return None

    def _call_gemini_single_attempt(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False
    ) -> Tuple[str, str]:
        """
        Executes a single HTTP request to Gemini via generativelanguage v1beta API.
        Authentication is passed strictly via the x-goog-api-key header (NEVER in the URL).
        """
        if not self.gemini_key:
            raise ModelConfigurationError("GEMINI_API_KEY is not configured in environment or settings.")

        endpoint_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.gemini_key
        }

        gen_config: Dict[str, Any] = {
            "thinkingConfig": {
                "thinkingLevel": self.thinking_level
            }
        }
        if json_mode:
            gen_config["responseMimeType"] = "application/json"

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_config
        }
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}

        print("\n" + "=" * 70)
        print(f"[HTTP REQUEST -> Primary Model: Gemini ({self.gemini_model})]")
        print(f"  • Endpoint:       {endpoint_url}")
        print(f"  • Thinking Level: {self.thinking_level}")
        print(f"  • JSON Mode:      {json_mode}")
        if system:
            print(f"  • System:\n{system[:200].strip()}...")
        print(f"  • Prompt Snippet:\n{prompt[:250].strip()}...")
        print("=" * 70)

        t0 = time.time()
        client = self._get_gemini_client()
        res = client.post(endpoint_url, headers=headers, json=payload)
        elapsed = round(time.time() - t0, 2)

        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if not candidates:
                # Check for prompt blocking
                feedback = data.get("promptFeedback", {})
                block_reason = feedback.get("blockReason", "Unknown")
                raise GeminiResponseBlockedError(f"Gemini prompt blocked by provider: {block_reason}")

            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "")
            if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
                raise GeminiResponseBlockedError(f"Gemini candidate generation blocked: {finish_reason}")

            parts = candidate.get("content", {}).get("parts", [])
            raw_text = ""
            thought_text = ""
            for p in parts:
                if "text" in p:
                    text_content = str(p["text"])
                    # Check if part represents thinking metadata
                    if p.get("thought") is True:
                        thought_text += text_content
                    else:
                        raw_text += text_content
                elif "thought" in p and isinstance(p["thought"], str):
                    thought_text += p["thought"]

            print("\n" + "=" * 70)
            print(f"[HTTP RESPONSE <- Gemini ({self.gemini_model}) ({elapsed}s | Status: 200)]")
            print(f"[RAW VERBATIM RESPONSE]:\n{raw_text[:350].strip()}...")
            print("=" * 70)
            return thought_text.strip(), raw_text.strip()

        # Check for permanent client / auth errors
        if res.status_code in (400, 401, 403, 404):
            err_body = res.text[:300]
            raise httpx.HTTPStatusError(
                f"Gemini Permanent Error ({res.status_code}): {err_body}",
                request=res.request,
                response=res
            )

        # Handle rate limits and quota exhaustion (429)
        if res.status_code == 429:
            err_json = {}
            try:
                err_json = res.json().get("error", {})
            except Exception:
                pass
            status_str = err_json.get("status", "")
            msg = err_json.get("message", res.text[:300])

            # Classify daily quota exhaustion vs temporary RPM rate limit
            is_daily_quota = (
                "quota" in msg.lower() and ("day" in msg.lower() or "daily" in msg.lower())
            ) or status_str == "RESOURCE_EXHAUSTED" and "per day" in msg.lower()

            if is_daily_quota:
                raise httpx.HTTPStatusError(
                    f"Gemini Daily Quota Exhausted (429): {msg}",
                    request=res.request,
                    response=res
                )

        # Other transient errors
        res.raise_for_status()
        return "", ""

    def _call_gemini_with_retry(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False
    ) -> Tuple[str, str]:
        """
        Executes Gemini with bounded retries, exponential backoff with jitter,
        and immediate fallback on permanent errors or exhausted daily quotas.
        """
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._call_gemini_single_attempt(prompt, system=system, json_mode=json_mode)
            except KeyboardInterrupt:
                # Do not catch user interruption as provider error
                raise
            except GeminiResponseBlockedError as e:
                # Safety blocks should not be retried with the identical prompt
                print(f"\n[Gemini Safety Block] {e}")
                raise
            except ModelConfigurationError as e:
                # Configuration / missing key errors should not be retried
                raise
            except httpx.HTTPStatusError as e:
                # Permanent errors: don't burn retries
                if e.response.status_code in (400, 401, 403, 404):
                    print(f"\n[Gemini Request/Auth Error] Status {e.response.status_code}: {e.response.text[:200]}")
                    raise
                if "Daily Quota Exhausted" in str(e):
                    print(f"\n[Gemini Quota Exhausted] Rapid fallback activated: {e}")
                    raise

                # Transient 429 rate limit or 503 service unavailable
                last_error = e
                if attempt == self.max_retries:
                    break

                # Respect Retry-After header if provided by server
                retry_after_hdr = e.response.headers.get("Retry-After")
                if retry_after_hdr and retry_after_hdr.isdigit():
                    backoff = min(float(retry_after_hdr), 30.0)
                else:
                    backoff = (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)

                print(f"\n[Gemini Transient Error (Status {e.response.status_code})] Attempt {attempt}/{self.max_retries}. Retrying in {backoff:.2f}s...")
                time.sleep(backoff)

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt == self.max_retries:
                    break
                backoff = (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                print(f"\n[Gemini Network/Timeout Error] Attempt {attempt}/{self.max_retries} failed ({type(e).__name__}). Retrying in {backoff:.2f}s...")
                time.sleep(backoff)

        raise RuntimeError(f"Gemini transient failure exhausted after {self.max_retries} retries: {last_error}")

    def _call_ollama(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False
    ) -> Tuple[str, str]:
        """
        Calls local Ollama endpoint as fallback provider.
        """
        endpoint = f"{self.ollama_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        if json_mode:
            payload["format"] = "json"
        if system:
            payload["system"] = system

        print("\n" + "=" * 70)
        print(f"[HTTP REQUEST -> Fallback Local Ollama ({self.ollama_model})]")
        print(f"  • Endpoint:  {endpoint}")
        print(f"  • JSON Mode: {json_mode}")
        if system:
            print(f"  • System:\n{system[:200].strip()}...")
        print(f"  • Prompt Snippet:\n{prompt[:250].strip()}...")
        print("=" * 70)

        t0 = time.time()
        try:
            client = self._get_ollama_client()
            res = client.post(endpoint, json=payload)
            elapsed = round(time.time() - t0, 2)
            if res.status_code == 200:
                raw = res.json().get("response", "").strip()
                thought, clean = self.parse_think_reasoning(raw)
                print("\n" + "=" * 70)
                print(f"[HTTP RESPONSE <- Local Ollama ({elapsed}s | Status: 200)]")
                print(f"[RAW VERBATIM RESPONSE]:\n{clean[:350].strip()}...")
                print("=" * 70)
                return thought, clean
            else:
                raise RuntimeError(f"Ollama returned status {res.status_code}: {res.text[:200]}")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            raise RuntimeError(f"Ollama connection failed: {e}")

    def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        task_name: str = "general",
        json_mode: bool = False
    ) -> ModelResponse:
        """
        Generates text enforcing the primary Gemini-first, Ollama-fallback routing policy.
        """
        t0 = time.time()

        # Offline mode bypass
        if self.offline:
            print(f"\n[Model Provider] Offline mode active. Routing task '{task_name}' directly to Ollama fallback.")
            try:
                thought, text = self._call_ollama(prompt, system=system, json_mode=json_mode)
                return ModelResponse(
                    text=text,
                    thought=thought,
                    provider_used="ollama",
                    model_name=self.ollama_model,
                    fallback_invoked=True,
                    fallback_reason="OFFLINE_MODE_ACTIVE",
                    latency_seconds=round(time.time() - t0, 2)
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                raise ModelExecutionError(f"Offline execution failed on Ollama: {e}")

        # 1. Primary Route: Gemini
        gemini_error = None
        if self.gemini_key:
            try:
                thought, text = self._call_gemini_with_retry(prompt, system=system, json_mode=json_mode)
                if text.strip():
                    return ModelResponse(
                        text=text,
                        thought=thought,
                        provider_used="gemini",
                        model_name=self.gemini_model,
                        fallback_invoked=False,
                        latency_seconds=round(time.time() - t0, 2)
                    )
                gemini_error = "Gemini returned empty text response"
            except KeyboardInterrupt:
                raise
            except Exception as e:
                gemini_error = str(e)
                print(f"\n[Model Provider Warning] Gemini primary failed for task '{task_name}': {e}. Activating Ollama fallback.")
        else:
            gemini_error = "GEMINI_API_KEY missing from environment"
            print(f"\n[Model Provider Warning] Missing Gemini API key for task '{task_name}'. Activating Ollama fallback.")

        # 2. Fallback Route: Local Ollama
        try:
            thought, text = self._call_ollama(prompt, system=system, json_mode=json_mode)
            if not text.strip():
                raise RuntimeError("Ollama returned empty response")
            return ModelResponse(
                text=text,
                thought=thought,
                provider_used="ollama",
                model_name=self.ollama_model,
                fallback_invoked=True,
                fallback_reason=gemini_error,
                latency_seconds=round(time.time() - t0, 2)
            )
        except KeyboardInterrupt:
            raise
        except Exception as ollama_err:
            raise ModelExecutionError(
                f"Both providers failed for task '{task_name}'. "
                f"Primary (Gemini): {gemini_error} | Fallback (Ollama): {ollama_err}"
            )

    def generate_structured(
        self,
        prompt: str,
        schema_model: Type[T],
        system: Optional[str] = None,
        task_name: str = "structured_synthesis",
        max_repairs: int = 2
    ) -> Tuple[ModelResponse, T]:
        """
        Generates structured output strictly matching schema_model.
        Enables JSON response mode on both Gemini and Ollama fallback.
        Validates output using Pydantic and executes a bounded repair loop if necessary.
        """
        schema_json = json.dumps(schema_model.model_json_schema(), indent=2)
        augmented_prompt = (
            f"{prompt}\n\n"
            f"CRITICAL REQUIREMENT: Output MUST strictly adhere to this JSON Schema:\n"
            f"{schema_json}\n\n"
            f"Respond with a single valid JSON object. Zero markdown asterisks (**) inside strings. Zero conversational preamble."
        )

        response = self.generate_text(
            augmented_prompt,
            system=system,
            task_name=task_name,
            json_mode=True
        )
        parsed = self.extract_json_block(response.text)

        # Validate against schema
        if parsed is not None:
            try:
                validated_obj = schema_model.model_validate(parsed)
                response.parsed_json = parsed
                return response, validated_obj
            except ValidationError as ve:
                validation_errors = str(ve)
        else:
            validation_errors = "Could not parse valid JSON from model response"

        # Bounded repair loop
        print(f"\n[Model Provider] Schema validation failed for task '{task_name}': {validation_errors}. Attempting bounded repair.")
        curr_text = response.text
        for repair_attempt in range(1, max_repairs + 1):
            repair_prompt = (
                f"Your previous JSON response failed strict Pydantic validation with these errors:\n"
                f"{validation_errors}\n\n"
                f"Previous Response:\n{curr_text}\n\n"
                f"Required Schema:\n{schema_json}\n\n"
                f"Correct all errors and return ONLY the fixed, valid JSON object."
            )
            repair_resp = self.generate_text(
                repair_prompt,
                system="You are an expert JSON repair assistant. Output strictly valid JSON matching the schema.",
                task_name=f"{task_name}_repair_{repair_attempt}",
                json_mode=True
            )
            curr_text = repair_resp.text
            parsed_repair = self.extract_json_block(curr_text)
            if parsed_repair is not None:
                try:
                    validated_obj = schema_model.model_validate(parsed_repair)
                    repair_resp.parsed_json = parsed_repair
                    print(f"  [✓] Schema repair attempt {repair_attempt} succeeded.")
                    return repair_resp, validated_obj
                except ValidationError as ve:
                    validation_errors = str(ve)

        raise ModelExecutionError(
            f"Structured output validation failed after {max_repairs} repair attempts for task '{task_name}': {validation_errors}"
        )

    @classmethod
    def diagnose_providers(cls) -> Dict[str, Any]:
        return cls().diagnose_model_provider()

    def diagnose_model_provider(self) -> Dict[str, Any]:
        """
        Lightweight diagnostic checking configured Gemini and Ollama connectivity.
        """
        status: Dict[str, Any] = {
            "gemini_model_configured": self.gemini_model,
            "gemini_thinking_level": self.thinking_level,
            "ollama_fallback_model": self.ollama_model,
            "offline_mode": self.offline,
            "gemini_key_present": bool(self.gemini_key),
            "gemini_status": "UNTESTED",
            "gemini_latency_s": None,
            "ollama_status": "UNTESTED",
            "ollama_latency_s": None
        }

        # 1. Test Gemini
        if self.gemini_key and not self.offline:
            t0 = time.time()
            try:
                _, text = self._call_gemini_single_attempt("Respond with 'PONG' in one word.", json_mode=False)
                status["gemini_status"] = "OK" if "PONG" in text.upper() else f"UNEXPECTED_RESPONSE: {text[:50]}"
                status["gemini_latency_s"] = round(time.time() - t0, 2)
            except Exception as e:
                status["gemini_status"] = f"FAILED: {e}"

        # 2. Test Ollama
        t0 = time.time()
        try:
            _, text = self._call_ollama("Respond with 'PONG' in one word.", json_mode=False)
            status["ollama_status"] = "OK" if "PONG" in text.upper() else f"UNEXPECTED_RESPONSE: {text[:50]}"
            status["ollama_latency_s"] = round(time.time() - t0, 2)
        except Exception as e:
            status["ollama_status"] = f"UNAVAILABLE: {e}"

        return status


# Global singleton provider instance
central_provider = CentralModelProvider()
