"""LLM client with streaming, retry, model selection, and cost tracking.

Key resolution order:
1. Explicit api_key parameter
2. ANTHROPIC_API_KEY environment variable
3. OpenClaw's stored Anthropic key (~/.openclaw/agents/main/agent/auth-profiles.json)
4. Raise NoAPIKeyError

This means: if you have OpenClaw installed and configured, everything
just works — no env var needed. The SDK is used directly for streaming.
"""

import json
import os
import time
from pathlib import Path
from typing import Generator, List, Optional

from anthropic import Anthropic, APIConnectionError, RateLimitError


class NoAPIKeyError(Exception):
    pass


# Model catalog: name → (model_id, input_cost_per_1k, output_cost_per_1k)
MODELS = {
    "sonnet": ("claude-sonnet-4-5-20250929", 0.003, 0.015),
    "haiku": ("claude-haiku-4-5-20251001", 0.001, 0.005),
    "opus": ("claude-opus-4-0-20250514", 0.015, 0.075),
}

DEFAULT_MODEL = "sonnet"

# Retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRYABLE_EXCEPTIONS = (APIConnectionError, RateLimitError)

# OpenClaw auth config paths (checked in order)
_OPENCLAW_AUTH_PATHS = [
    Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json",
    Path.home() / ".openclaw-dev" / "agents" / "main" / "agent" / "auth-profiles.json",
]


def _get_model_id(model_name: Optional[str] = None) -> str:
    name = model_name or DEFAULT_MODEL
    if name in MODELS:
        return MODELS[name][0]
    return name


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given token count."""
    if model_name not in MODELS:
        return 0.0
    _, input_rate, output_rate = MODELS[model_name]
    return (input_tokens * input_rate / 1000) + (output_tokens * output_rate / 1000)


def _openclaw_available() -> bool:
    """Check if openclaw is installed (for backwards compat checks)."""
    import shutil
    return shutil.which("openclaw") is not None


def _read_openclaw_key() -> Optional[str]:
    """Try to read the Anthropic API key from OpenClaw's auth config."""
    for auth_path in _OPENCLAW_AUTH_PATHS:
        if not auth_path.exists():
            continue
        try:
            data = json.loads(auth_path.read_text())
            profiles = data.get("profiles", {})
            for _name, profile in profiles.items():
                if isinstance(profile, dict) and profile.get("provider") == "anthropic":
                    token = profile.get("token", "")
                    if token and token.startswith("sk-"):
                        return token
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return None


def _resolve_api_key(api_key: Optional[str] = None) -> str:
    """Resolve API key from multiple sources.

    Priority: explicit param > env var > OpenClaw config > error
    """
    # 1. Explicit
    if api_key:
        return api_key

    # 2. Environment
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key

    # 3. OpenClaw config
    oc_key = _read_openclaw_key()
    if oc_key:
        return oc_key

    raise NoAPIKeyError(
        "No API key found. Set ANTHROPIC_API_KEY, or install OpenClaw "
        "(https://github.com/openclaw/openclaw) with an Anthropic key configured."
    )


class UsageStats:
    """Tracks cumulative token usage and cost across calls."""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0

    def record(self, model_name: str, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += estimate_cost(model_name, input_tokens, output_tokens)
        self.call_count += 1

    def summary(self) -> str:
        return (
            f"Tokens: {self.total_input_tokens} in / {self.total_output_tokens} out | "
            f"Cost: ${self.total_cost:.4f} | Calls: {self.call_count}"
        )


class ClaudeClient:
    """Unified LLM client with streaming support.

    Resolves the API key automatically — from env, OpenClaw config, or explicit param.
    Always uses the Anthropic SDK directly for real streaming.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        self.api_key = _resolve_api_key(api_key)
        self._client = Anthropic(api_key=self.api_key)
        self.model_name = model or DEFAULT_MODEL
        self.model_id = _get_model_id(self.model_name)
        self.default_max_tokens = max_tokens
        self.usage = UsageStats()

    def _retry(self, fn, *args, **kwargs):
        """Execute fn with exponential backoff retry on transient errors."""
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except RETRYABLE_EXCEPTIONS as e:
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)
        raise last_exc

    def generate(
        self, system_prompt: str, user_message: str, max_tokens: Optional[int] = None
    ) -> str:
        max_tokens = max_tokens or self.default_max_tokens

        def _call():
            return self._client.messages.create(
                model=self.model_id,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

        response = self._retry(_call)
        self._track_usage(response)
        return response.content[0].text

    def converse(
        self,
        system_prompt: str,
        messages: List[dict],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a multi-turn conversation and return the full response."""
        max_tokens = max_tokens or self.default_max_tokens

        def _call():
            return self._client.messages.create(
                model=self.model_id,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )

        response = self._retry(_call)
        self._track_usage(response)
        return response.content[0].text

    def converse_stream(
        self,
        system_prompt: str,
        messages: List[dict],
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """Send a multi-turn conversation and yield streamed text chunks.

        This gives real token-by-token streaming — the prompt appears to
        emerge as the model generates it.
        """
        max_tokens = max_tokens or self.default_max_tokens

        def _call():
            return self._client.messages.stream(
                model=self.model_id,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )

        stream_ctx = self._retry(_call)
        with stream_ctx as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
            if final and hasattr(final, "usage"):
                self.usage.record(
                    self.model_name,
                    getattr(final.usage, "input_tokens", 0),
                    getattr(final.usage, "output_tokens", 0),
                )

    def generate_stream(
        self, system_prompt: str, user_message: str, max_tokens: Optional[int] = None
    ) -> Generator[str, None, None]:
        """Single-turn generation with streaming."""
        return self.converse_stream(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=max_tokens,
        )

    def _track_usage(self, response):
        if hasattr(response, "usage"):
            self.usage.record(
                self.model_name,
                getattr(response.usage, "input_tokens", 0),
                getattr(response.usage, "output_tokens", 0),
            )
