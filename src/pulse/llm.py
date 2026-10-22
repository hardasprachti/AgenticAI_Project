"""LLM client: Groq chat completions with schema-validated JSON output (architecture section 6).

Every call returns JSON that is parsed and validated against a pydantic model. Transport problems
(rate limits, timeouts, 5xx) and invalid JSON are retried a bounded number of times; auth and
model-not-found errors are fatal immediately. Model ids come from config by task name, and the
API key is read from the environment and never logged or included in error messages.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

import groq
from pydantic import BaseModel, ValidationError

from pulse.config import LlmConfig

T = TypeVar("T", bound=BaseModel)

API_KEY_ENV = "GROQ_API_KEY"
_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_MAX_BACKOFF_S = 30.0
_LIMIT_KIND_RE = re.compile(r"on (requests|tokens) per (minute|hour|day)", re.IGNORECASE)


class LLMError(RuntimeError):
    """An LLM call failed for good: fatal error, or retries exhausted."""


class LLMClient(Protocol):
    def complete_json(self, *, task: str, system: str, user: str, schema: type[T]) -> T:
        """Run `task` (a key of config `models`) and return the reply validated as `schema`."""
        ...


def _extract_json(content: str) -> Any:
    text = content.strip()
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


class GroqLLM:
    def __init__(
        self,
        models: dict[str, str],
        config: LlmConfig,
        *,
        api_key: str | None = None,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._models = models
        self._config = config
        self._sleep = sleep
        if client is None:
            api_key = api_key or os.environ.get(API_KEY_ENV)
            if not api_key:
                raise LLMError(f"{API_KEY_ENV} is not set. Add it to .env (see .env.example).")
            client = groq.Groq(api_key=api_key, timeout=config.timeout_s, max_retries=0)
        self._client = client
        self.usage: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "retries": 0,
                "rate_limited": 0,
                "invalid_replies": 0,
                "waited_s": 0,
            }
        )

    def model_for(self, task: str) -> str:
        try:
            return self._models[task]
        except KeyError:
            raise LLMError(f"No model configured for task '{task}' (config: models)") from None

    def list_models(self) -> list[str]:
        """Model ids available to this key (used by `check-llm`)."""
        return sorted(m.id for m in self._client.models.list().data)

    def complete_json(self, *, task: str, system: str, user: str, schema: type[T]) -> T:
        model = self.model_for(task)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        attempts = self._config.max_retries + 1  # for failures other than rate limits
        rate_limit_waits = 0
        failures = 0
        last_problem = "no attempt made"

        while True:
            try:
                response = self._create(model, messages)
            except groq.RateLimitError as exc:
                # Being rate limited is normal on a per-minute token budget, not a failure: wait
                # out the window on a budget of its own so it cannot eat the retries below.
                self.usage[task]["rate_limited"] += 1
                rate_limit_waits += 1
                if rate_limit_waits > self._config.max_rate_limit_retries:
                    raise LLMError(
                        f"Task '{task}' was still rate limited after {rate_limit_waits - 1} "
                        "waits. Try again later or lower llm.batch_size."
                    ) from exc
                delay = self._backoff(rate_limit_waits - 1, exc)
                if delay > self._config.max_rate_limit_wait_s:
                    # A long wait means a quota (tokens per day), not a busy minute. Sleeping
                    # through it unattended helps nobody: stop and say when to come back.
                    raise LLMError(
                        f"Groq {self._limit_kind(exc)} limit reached for the model of task "
                        f"'{task}'; it frees up in about {self._human(delay)}. Try again then, "
                        "or point that task at another model in config.yaml."
                    ) from exc
                self._wait(task, delay)
                continue
            except (groq.APIConnectionError, groq.InternalServerError) as exc:
                failures += 1
                last_problem = type(exc).__name__
                if failures >= attempts:
                    break
                self._wait(task, self._backoff(failures - 1, exc))
                continue
            except groq.AuthenticationError as exc:
                raise LLMError(f"Groq rejected the API key ({API_KEY_ENV}).") from exc
            except groq.NotFoundError as exc:
                raise LLMError(
                    f"Model '{model}' (task '{task}') was not found. Run `python -m pulse "
                    "check-llm` to list the models your key can use, then update config.yaml."
                ) from exc
            except groq.APIStatusError as exc:
                status = exc.status_code
                raise LLMError(f"Groq request failed ({status}) for task '{task}'.") from exc

            self._record_usage(task, response)
            content = (response.choices[0].message.content or "").strip()
            try:
                return schema.model_validate(_extract_json(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                failures += 1
                last_problem = "invalid JSON" if isinstance(exc, json.JSONDecodeError) else "schema"
                self.usage[task]["invalid_replies"] += 1
                if failures >= attempts:
                    break
                self.usage[task]["retries"] += 1
                problem = self._summarize(exc)
                messages += [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": f"That reply was not valid. Problem: {problem}. "
                        "Reply again with only the corrected JSON object.",
                    },
                ]

        raise LLMError(
            f"Task '{task}' failed after {attempts} attempts (last problem: {last_problem})."
        )

    def _wait(self, task: str, delay: float) -> None:
        self.usage[task]["retries"] += 1
        self.usage[task]["waited_s"] += round(delay)
        self._sleep(delay)

    def _create(self, model: str, messages: list[dict[str, str]]) -> Any:
        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": self._config.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._config.reasoning_effort:
            params["reasoning_effort"] = self._config.reasoning_effort
        return self._client.chat.completions.create(**params)

    def _record_usage(self, task: str, response: Any) -> None:
        usage = getattr(response, "usage", None)
        self.usage[task]["calls"] += 1
        self.usage[task]["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        self.usage[task]["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0

    @staticmethod
    def _backoff(attempt: int, exc: Exception) -> float:
        """Seconds to wait: the server's retry-after if it gave one, else exponential."""
        headers = getattr(getattr(exc, "response", None), "headers", None) or {}
        try:
            return float(headers.get("retry-after"))
        except (TypeError, ValueError):
            return min(2.0 * 2**attempt, _MAX_BACKOFF_S)

    @staticmethod
    def _limit_kind(exc: Exception) -> str:
        """Which limit was hit, e.g. "tokens per day". Never echoes the raw message, which names
        the account."""
        body = getattr(exc, "body", None)
        message = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
        found = _LIMIT_KIND_RE.search(message)
        return f"{found.group(1)}-per-{found.group(2)}".lower() if found else "rate"

    @staticmethod
    def _human(seconds: float) -> str:
        return f"{seconds / 60:.0f} minutes" if seconds >= 120 else f"{seconds:.0f} seconds"

    @staticmethod
    def _summarize(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first["loc"]) or "root"
            return f"{where}: {first['msg']}"
        return "the reply was not parseable JSON"
