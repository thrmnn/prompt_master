"""Thin wrapper around the Anthropic SDK."""

import os
from typing import Optional

from anthropic import Anthropic


class NoAPIKeyError(Exception):
    pass


class ClaudeClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise NoAPIKeyError(
                "No API key found. Set ANTHROPIC_API_KEY or use --no-api for template mode."
            )
        self._client = Anthropic(api_key=self.api_key)

    def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 4096
    ) -> str:
        response = self._client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
