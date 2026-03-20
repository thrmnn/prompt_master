"""Thin wrapper around LLM providers with retry, model selection, and cost tracking.

Supports two providers:
- "openclaw" (default): calls `openclaw agent` CLI — no API key needed if OpenClaw is configured
- "anthropic": direct Anthropic SDK — requires ANTHROPIC_API_KEY
"""

import json
import os
import shutil
import subprocess
import time
from typing import Generator, List, Optional

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError


class NoAPIKeyError(Exception):
    pass


class NoProviderError(Exception):
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
    """Check if openclaw CLI is installed and accessible."""
    return shutil.which("openclaw") is not None


def detect_provider() -> str:
    """Detect the best available provider.

    Priority: openclaw (if installed) > anthropic (if key set) > error
    """
    if _openclaw_available():
        return "openclaw"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise NoProviderError(
        "No LLM provider available. Install OpenClaw (https://github.com/openclaw/openclaw) "
        "or set ANTHROPIC_API_KEY."
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


# ── OpenClaw provider ──────────────────────────────────────────────────────


# Map prompt-master model names to openclaw agent names
OPENCLAW_AGENTS = {
    "haiku": "prompt-master-fast",
    "sonnet": "main",
    "opus": "main",
}


class OpenClawClient:
    """Calls LLMs through the OpenClaw CLI — no API key needed."""

    def __init__(
        self,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        agent: Optional[str] = None,
    ):
        if not _openclaw_available():
            raise NoProviderError("OpenClaw CLI not found. Install from https://github.com/openclaw/openclaw")
        self.model_name = model or DEFAULT_MODEL
        self.default_max_tokens = max_tokens
        # Use model-specific agent if available, otherwise default
        self.agent = agent or OPENCLAW_AGENTS.get(self.model_name, "main")
        self.usage = UsageStats()

    def _call_openclaw(self, message: str, timeout: int = 120) -> dict:
        """Call openclaw agent and return the parsed JSON result."""
        cmd = [
            "openclaw", "agent",
            "--agent", self.agent,
            "--local",
            "--message", message,
            "--json",
            "--thinking", "off",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"OpenClaw error: {stderr}")

        # Parse JSON from stdout (skip any ANSI warning lines)
        stdout = result.stdout
        # Find the JSON object in the output
        json_start = stdout.find("{")
        if json_start == -1:
            raise RuntimeError(f"No JSON in OpenClaw output: {stdout[:200]}")
        data = json.loads(stdout[json_start:])

        # Track usage
        meta = data.get("meta", {})
        agent_meta = meta.get("agentMeta", {})
        usage = agent_meta.get("usage", {})
        self.usage.record(
            self.model_name,
            usage.get("input", 0) + usage.get("cacheRead", 0),
            usage.get("output", 0),
        )

        return data

    def _extract_text(self, data: dict) -> str:
        """Extract the text response from OpenClaw JSON output."""
        payloads = data.get("payloads", [])
        if not payloads:
            return ""
        return payloads[0].get("text", "")

    def _build_message(self, system_prompt: str, user_message: str) -> str:
        """Build a combined message for OpenClaw (system + user in one shot)."""
        return (
            f"[SYSTEM INSTRUCTIONS — follow these exactly]\n\n"
            f"{system_prompt}\n\n"
            f"[END SYSTEM INSTRUCTIONS]\n\n"
            f"[USER MESSAGE]\n\n"
            f"{user_message}"
        )

    def _build_conversation_message(self, system_prompt: str, messages: List[dict]) -> str:
        """Build a conversation history into a single message for OpenClaw."""
        parts = [
            f"[SYSTEM INSTRUCTIONS — follow these exactly]\n\n{system_prompt}\n\n[END SYSTEM INSTRUCTIONS]"
        ]
        for msg in messages:
            role = msg["role"].upper()
            parts.append(f"\n[{role}]\n{msg['content']}")
        return "\n".join(parts)

    def generate(
        self, system_prompt: str, user_message: str, max_tokens: Optional[int] = None
    ) -> str:
        message = self._build_message(system_prompt, user_message)
        data = self._call_openclaw(message)
        return self._extract_text(data)

    def converse(
        self,
        system_prompt: str,
        messages: List[dict],
        max_tokens: Optional[int] = None,
    ) -> str:
        message = self._build_conversation_message(system_prompt, messages)
        data = self._call_openclaw(message)
        return self._extract_text(data)

    def converse_stream(
        self,
        system_prompt: str,
        messages: List[dict],
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """OpenClaw doesn't support streaming, so yield the full response at once."""
        text = self.converse(system_prompt, messages, max_tokens)
        # Yield in chunks to simulate streaming for the UI
        chunk_size = 20
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]


# ── Anthropic provider ─────────────────────────────────────────────────────


class AnthropicClient:
    """Direct Anthropic SDK client — requires ANTHROPIC_API_KEY."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise NoAPIKeyError(
                "No API key found. Set ANTHROPIC_API_KEY or use --no-api for template mode."
            )
        self._client = Anthropic(api_key=self.api_key)
        self.model_name = model or DEFAULT_MODEL
        self.model_id = _get_model_id(self.model_name)
        self.default_max_tokens = max_tokens
        self.usage = UsageStats()

    def _retry(self, fn, *args, **kwargs):
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

    def _track_usage(self, response):
        if hasattr(response, "usage"):
            self.usage.record(
                self.model_name,
                getattr(response.usage, "input_tokens", 0),
                getattr(response.usage, "output_tokens", 0),
            )


# ── Unified ClaudeClient factory ───────────────────────────────────────────


def ClaudeClient(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    provider: Optional[str] = None,
):
    """Create the best available LLM client.

    Provider priority:
    1. Explicit provider parameter ("openclaw" or "anthropic")
    2. OpenClaw if installed
    3. Anthropic if ANTHROPIC_API_KEY is set
    4. Raise NoProviderError

    Returns an OpenClawClient or AnthropicClient — both have the same interface:
    generate(), converse(), converse_stream(), usage
    """
    if provider == "anthropic":
        return AnthropicClient(api_key=api_key, model=model, max_tokens=max_tokens)
    if provider == "openclaw":
        return OpenClawClient(model=model, max_tokens=max_tokens)

    # Auto-detect
    if _openclaw_available():
        return OpenClawClient(model=model, max_tokens=max_tokens)
    if api_key or os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicClient(api_key=api_key, model=model, max_tokens=max_tokens)

    raise NoAPIKeyError(
        "No LLM provider available. Install OpenClaw or set ANTHROPIC_API_KEY."
    )
