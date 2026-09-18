"""OpenAI-compatible chat completions client (works with GLM's /chat/completions)."""
from __future__ import annotations

import logging

import httpx

from ..core.models import Message

log = logging.getLogger(__name__)


class OpenAICompatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 60.0, client: httpx.AsyncClient | None = None) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._client = client or httpx.AsyncClient(timeout=timeout_s)

    async def complete(self, messages: list[Message], *, temperature: float, max_tokens: int) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        # GLM "thinking" models may return reasoning by default; ask them not to for latency.
        payload["thinking"] = {"type": "disabled"}
        resp = await self._client.post(self._url, json=payload, headers=self._headers)
        if resp.status_code >= 400:
            log.error("llm http %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        return content.strip()

    async def aclose(self) -> None:
        await self._client.aclose()
