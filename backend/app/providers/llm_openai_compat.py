"""OpenAI-compatible chat completions client (works with GLM's /chat/completions)."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from ..core.models import Message

log = logging.getLogger(__name__)


class OpenAICompatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 60.0, client: httpx.AsyncClient | None = None) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._client = client or httpx.AsyncClient(timeout=timeout_s)

    def _payload(self, messages: list[Message], temperature: float, max_tokens: int, *, stream: bool) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            # GLM "thinking" models may return reasoning by default; ask them not to for latency.
            "thinking": {"type": "disabled"},
        }

    async def complete(self, messages: list[Message], *, temperature: float, max_tokens: int) -> str:
        payload = self._payload(messages, temperature, max_tokens, stream=False)
        resp = await self._client.post(self._url, json=payload, headers=self._headers)
        if resp.status_code >= 400:
            log.error("llm http %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        return content.strip()

    async def stream(self, messages: list[Message], *, temperature: float, max_tokens: int) -> AsyncIterator[str]:
        """Yield content deltas as they arrive, so the first sentence can be spoken
        while the rest is still being written."""
        payload = self._payload(messages, temperature, max_tokens, stream=True)
        async with self._client.stream("POST", self._url, json=payload, headers=self._headers) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread())[:500]
                log.error("llm http %s: %s", resp.status_code, body)
                resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    choices = json.loads(data).get("choices") or []
                except ValueError:
                    continue
                if not choices:
                    continue
                delta = (choices[0].get("delta") or {}).get("content") or ""
                if delta:
                    yield delta

    async def aclose(self) -> None:
        await self._client.aclose()
