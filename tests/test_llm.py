from types import SimpleNamespace

import groq
import httpx
import pytest
from pydantic import BaseModel

from pulse.config import LlmConfig
from pulse.llm import GroqLLM, LLMError


class Out(BaseModel):
    answer: int


CONFIG = LlmConfig(batch_size=10, max_retries=2, timeout_s=5, max_output_tokens=100)
MODELS = {"compose": "model-c", "theme_assign": "model-t"}


def _response(content: str, prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _http_error(cls, status: int, headers: dict | None = None):
    request = httpx.Request("POST", "https://api.groq.com/x")
    response = httpx.Response(status, request=request, headers=headers or {})
    return cls("boom", response=response, body=None)


class FakeGroq:
    """Plays back a script of replies/exceptions for chat.completions.create."""

    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id="b"), SimpleNamespace(id="a")])
        )

    def _create(self, **params):
        self.requests.append(params)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _llm(script, config=CONFIG):
    client = FakeGroq(script)
    sleeps: list[float] = []
    return GroqLLM(MODELS, config, client=client, sleep=sleeps.append), client, sleeps


def test_returns_validated_object_and_sends_expected_params():
    llm, client, _ = _llm([_response('{"answer": 4}')])
    out = llm.complete_json(task="compose", system="sys", user="usr", schema=Out)
    assert out == Out(answer=4)
    [req] = client.requests
    assert req["model"] == "model-c"
    assert req["temperature"] == 0
    assert req["response_format"] == {"type": "json_object"}
    assert req["max_completion_tokens"] == 100
    assert "reasoning_effort" not in req
    assert [m["role"] for m in req["messages"]] == ["system", "user"]


def test_reasoning_effort_only_sent_when_configured():
    config = LlmConfig(10, 1, 5, 100, reasoning_effort="low")
    llm, client, _ = _llm([_response('{"answer": 1}')], config)
    llm.complete_json(task="compose", system="s", user="u", schema=Out)
    assert client.requests[0]["reasoning_effort"] == "low"


def test_fenced_json_is_accepted():
    llm, _, _ = _llm([_response('```json\n{"answer": 2}\n```')])
    assert llm.complete_json(task="compose", system="s", user="u", schema=Out).answer == 2


def test_invalid_json_is_retried_with_feedback():
    llm, client, _ = _llm([_response("not json"), _response('{"answer": 3}')])
    assert llm.complete_json(task="compose", system="s", user="u", schema=Out).answer == 3
    retry_messages = client.requests[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": "not json"}
    assert "not valid" in retry_messages[-1]["content"]
    assert llm.usage["compose"]["retries"] == 1


def test_schema_mismatch_is_retried_and_names_the_field():
    llm, client, _ = _llm([_response('{"answer": "x"}'), _response('{"answer": 5}')])
    llm.complete_json(task="compose", system="s", user="u", schema=Out)
    assert "answer" in client.requests[1]["messages"][-1]["content"]


def test_gives_up_after_bounded_attempts():
    llm, client, _ = _llm([_response("bad")] * 3)
    with pytest.raises(LLMError, match="after 3 attempts"):
        llm.complete_json(task="compose", system="s", user="u", schema=Out)
    assert len(client.requests) == 3


def test_rate_limit_backs_off_using_retry_after_then_succeeds():
    err = _http_error(groq.RateLimitError, 429, {"retry-after": "7"})
    llm, _, sleeps = _llm([err, _response('{"answer": 1}')])
    assert llm.complete_json(task="compose", system="s", user="u", schema=Out).answer == 1
    assert sleeps == [7.0]


def test_server_error_uses_exponential_backoff():
    errors = [_http_error(groq.InternalServerError, 500) for _ in range(2)]
    llm, _, sleeps = _llm([*errors, _response('{"answer": 1}')])
    llm.complete_json(task="compose", system="s", user="u", schema=Out)
    assert sleeps == [2.0, 4.0]


def test_transport_failures_exhaust_retries():
    errors = [_http_error(groq.RateLimitError, 429) for _ in range(3)]
    llm, _, _ = _llm(errors)
    with pytest.raises(LLMError, match="RateLimitError"):
        llm.complete_json(task="compose", system="s", user="u", schema=Out)


def test_auth_error_is_fatal_and_does_not_retry():
    llm, client, _ = _llm([_http_error(groq.AuthenticationError, 401), _response("{}")])
    with pytest.raises(LLMError, match="API key"):
        llm.complete_json(task="compose", system="s", user="u", schema=Out)
    assert len(client.requests) == 1


def test_unknown_model_points_to_check_llm():
    llm, _, _ = _llm([_http_error(groq.NotFoundError, 404)])
    with pytest.raises(LLMError, match="check-llm"):
        llm.complete_json(task="compose", system="s", user="u", schema=Out)


def test_unconfigured_task_rejected():
    llm, _, _ = _llm([])
    with pytest.raises(LLMError, match="No model configured"):
        llm.complete_json(task="judge", system="s", user="u", schema=Out)


def test_missing_api_key_is_reported_without_a_client(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqLLM(MODELS, CONFIG)


def test_api_key_never_appears_in_errors(monkeypatch):
    secret = "gsk_super_secret_value"
    llm, _, _ = _llm([_http_error(groq.AuthenticationError, 401)])
    with pytest.raises(LLMError) as info:
        llm.complete_json(task="compose", system="s", user=secret, schema=Out)
    assert secret not in str(info.value)


def test_usage_is_accumulated():
    llm, _, _ = _llm([_response('{"answer": 1}', 10, 5), _response('{"answer": 2}', 20, 7)])
    for _ in range(2):
        llm.complete_json(task="compose", system="s", user="u", schema=Out)
    usage = llm.usage["compose"]
    assert (usage["calls"], usage["prompt_tokens"], usage["completion_tokens"]) == (2, 30, 12)
    assert (usage["retries"], usage["rate_limited"], usage["invalid_replies"]) == (0, 0, 0)


def test_list_models_sorted():
    llm, _, _ = _llm([])
    assert llm.list_models() == ["a", "b"]


def test_usage_says_why_retries_happened():
    limited = _http_error(groq.RateLimitError, 429, {"retry-after": "5"})
    llm, _, _ = _llm([limited, _response("bad"), _response('{"answer": 1}')])
    llm.complete_json(task="compose", system="s", user="u", schema=Out)
    usage = llm.usage["compose"]
    assert (usage["retries"], usage["rate_limited"], usage["invalid_replies"]) == (2, 1, 1)
    assert usage["waited_s"] == 5
