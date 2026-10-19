import pytest
from unittest.mock import MagicMock, patch
import httpx
from pydantic import BaseModel, Field
from agent.llm_provider import CentralModelProvider, ModelExecutionError, ModelResponse, GeminiResponseBlockedError


class SampleSchema(BaseModel):
    finding: str
    confidence: str = Field(description="Must be High, Medium, or Low")
    score: float


def test_gemini_receives_task_and_ollama_not_called_on_success(mocker):
    """
    INVARIANT TEST:
    Verify that Gemini receives the task and Ollama is NEVER called when Gemini succeeds.
    Verifies that API key is sent via x-goog-api-key header and NOT in the URL.
    """
    provider = CentralModelProvider(gemini_api_key="mock_secret_key", use_offline_mode=False)

    # Mock Gemini HTTP response
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.status_code = 200
    mock_gemini_resp.json.return_value = {
        "candidates": [{
            "content": {"parts": [{"text": "Gemini verified response"}]}
        }]
    }
    mock_post = mocker.patch("httpx.Client.post", return_value=mock_gemini_resp)
    ollama_spy = mocker.spy(provider, "_call_ollama")

    resp = provider.generate_text("Test prompt", task_name="test_task")

    assert resp.provider_used == "gemini"
    assert resp.model_name == "gemini-3.5-flash-lite"
    assert resp.text == "Gemini verified response"
    assert resp.fallback_invoked is False
    # CRITICAL INVARIANT: Ollama was NEVER called
    assert ollama_spy.call_count == 0

    # Verify security: API key sent via header, NOT in URL
    call_args = mock_post.call_args
    called_url = call_args[0][0]
    called_headers = call_args[1].get("headers", {})
    assert "key=" not in called_url
    assert "mock_secret_key" not in called_url
    assert called_headers.get("x-goog-api-key") == "mock_secret_key"


def test_transient_gemini_failure_triggers_bounded_retry(mocker):
    """
    Verify that transient 429/503 errors trigger retries and then succeed.
    """
    provider = CentralModelProvider(gemini_api_key="mock_key", max_retries=3, use_offline_mode=False)

    # Mock first call as 429 (transient), second call as 200
    mock_req = MagicMock()
    transient_resp = MagicMock()
    transient_resp.status_code = 429
    transient_resp.headers = {"Retry-After": "1"}
    transient_resp.json.return_value = {"error": {"message": "Rate limit exceeded. Please wait."}}
    transient_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Rate limited", request=mock_req, response=transient_resp)

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Recovered after backoff"}]}}]
    }

    mock_post = mocker.patch("httpx.Client.post", side_effect=[transient_resp, success_resp])
    mocker.patch("time.sleep")  # avoid test delay

    resp = provider.generate_text("Test prompt")
    assert resp.provider_used == "gemini"
    assert resp.text == "Recovered after backoff"
    assert mock_post.call_count == 2


def test_daily_quota_exhaustion_triggers_rapid_fallback_without_useless_retries(mocker):
    """
    Verify that daily quota exhaustion (429 Daily Quota Exhausted) triggers
    immediate fallback to Ollama without useless retries.
    """
    provider = CentralModelProvider(gemini_api_key="mock_key", max_retries=5, use_offline_mode=False)

    quota_resp = MagicMock()
    quota_resp.status_code = 429
    quota_resp.headers = {}
    quota_resp.text = "Quota exceeded for quota metric 'GenerateContent requests' and limit 'GenerateContent requests per day'"
    quota_resp.json.return_value = {
        "error": {
            "code": 429,
            "message": "Resource has been exhausted (e.g. check quota). Daily quota limit exceeded.",
            "status": "RESOURCE_EXHAUSTED"
        }
    }

    mock_post = mocker.patch("httpx.Client.post", return_value=quota_resp)
    mocker.patch.object(provider, "_call_ollama", return_value=("", "Fallback from quota exhaustion"))

    resp = provider.generate_text("Test prompt")
    # Must only call Gemini ONCE: no point in burning retries when daily quota is exhausted
    assert mock_post.call_count == 1
    assert resp.provider_used == "ollama"
    assert resp.fallback_invoked is True
    assert "Daily Quota Exhausted" in str(resp.fallback_reason)
    assert resp.text == "Fallback from quota exhaustion"


def test_persistent_gemini_failure_triggers_ollama_fallback(mocker):
    """
    Verify that when Gemini persistently fails all retries, Ollama fallback is activated
    and technical metadata records the fallback reason.
    """
    provider = CentralModelProvider(gemini_api_key="mock_key", max_retries=2, use_offline_mode=False)

    # Mock Gemini always throwing NetworkError
    mocker.patch("httpx.Client.post", side_effect=httpx.NetworkError("Gemini down"))
    mocker.patch("time.sleep")

    # Mock Ollama fallback
    mocker.patch.object(provider, "_call_ollama", return_value=("Reasoning", "Ollama fallback output"))

    resp = provider.generate_text("Test prompt", task_name="investigation_step")
    assert resp.provider_used == "ollama"
    assert resp.fallback_invoked is True
    assert "Gemini down" in str(resp.fallback_reason)
    assert resp.text == "Ollama fallback output"


def test_permanent_auth_error_diagnosed_and_falls_back_without_infinite_retry(mocker):
    """
    Verify that 401 Unauthorized errors fail immediately without burning retries.
    """
    provider = CentralModelProvider(gemini_api_key="invalid_key", max_retries=5, use_offline_mode=False)

    auth_resp = MagicMock()
    auth_resp.status_code = 401
    auth_resp.text = "API_KEY_INVALID"

    mock_post = mocker.patch("httpx.Client.post", return_value=auth_resp)
    mocker.patch.object(provider, "_call_ollama", return_value=("", "Fallback due to auth error"))

    resp = provider.generate_text("Test prompt")
    # Must only call Gemini once (no retry loop on 401)
    assert mock_post.call_count == 1
    assert resp.provider_used == "ollama"
    assert "401" in str(resp.fallback_reason)


def test_both_providers_fail_raises_explicit_error(mocker):
    """
    Verify that if both Gemini and Ollama fail, an explicit ModelExecutionError is raised.
    Never fabricates a response.
    """
    provider = CentralModelProvider(gemini_api_key="mock_key", max_retries=1, use_offline_mode=False)

    mocker.patch("httpx.Client.post", side_effect=httpx.ConnectError("Gemini unreachable"))
    mocker.patch.object(provider, "_call_ollama", side_effect=RuntimeError("Ollama daemon stopped"))

    with pytest.raises(ModelExecutionError) as exc_info:
        provider.generate_text("Test prompt")

    assert "Both providers failed" in str(exc_info.value)
    assert "Gemini unreachable" in str(exc_info.value)
    assert "Ollama daemon stopped" in str(exc_info.value)


def test_structured_output_validation_and_repair(mocker):
    """
    Tests structured generation with schema validation and repair.
    Verifies that json_mode=True is passed to the generation call.
    """
    provider = CentralModelProvider(gemini_api_key="mock_key", use_offline_mode=False)

    # 1st response: malformed (missing score and invalid confidence)
    bad_resp = '{"finding": "Something unusual", "confidence": "Unknown"}'
    # 2nd response: corrected
    good_resp = '{"finding": "Valid anomaly", "confidence": "High", "score": 85.5}'

    mock_gen = mocker.patch.object(provider, "generate_text", side_effect=[
        ModelResponse(text=bad_resp, provider_used="gemini", model_name="gemini-3.5-flash-lite"),
        ModelResponse(text=good_resp, provider_used="gemini", model_name="gemini-3.5-flash-lite")
    ])

    resp, validated = provider.generate_structured(
        prompt="Analyze data",
        schema_model=SampleSchema,
        task_name="test_schema"
    )

    assert isinstance(validated, SampleSchema)
    assert validated.finding == "Valid anomaly"
    assert validated.confidence == "High"
    assert validated.score == 85.5
    # Verify json_mode was enabled
    assert mock_gen.call_args_list[0].kwargs.get("json_mode") is True


def test_model_diagnostics():
    """Tests the lightweight diagnostic command independently."""
    provider = CentralModelProvider(gemini_api_key="test_key", use_offline_mode=False)
    with patch.object(provider, "_call_gemini_single_attempt", return_value=("", "PONG")):
        with patch.object(provider, "_call_ollama", return_value=("", "PONG")):
            diag = provider.diagnose_model_provider()
            assert diag["gemini_status"] == "OK"
            assert diag["ollama_status"] == "OK"
            assert diag["gemini_model_configured"] == "gemini-3.5-flash-lite"
