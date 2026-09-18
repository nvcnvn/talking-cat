"""Microsoft Edge neural TTS via the edge-tts package. Returns MP3.

The service is fast (~1s) when it works but randomly fails ("no audio", ~2.5s) or
stalls for 10s+. Measured from a container: sequential retries with no chunking gave
p50 1.3s; concurrent sockets (chunks or early hedges) made stalls more likely. So by
default we retry serially on failure and only hedge (second concurrent attempt) after
`hedge_s`. Chunking is available via `chunk_chars` but off by default. Pair this
provider with FallbackTTS + a deadline so a stall never blocks the child.
"""
from __future__ import annotations

import asyncio
import logging
import re

import edge_tts

from ..core.models import AudioClip

log = logging.getLogger(__name__)


class EdgeTTS:
    def __init__(
        self,
        voice: str = "vi-VN-HoaiMyNeural",
        rate: str = "-5%",
        attempts: int = 4,
        hedge_s: float = 3.0,
        chunk_chars: int = 0,
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._attempts = attempts
        self._hedge_s = hedge_s
        self._chunk_chars = chunk_chars

    async def _once(self, text: str) -> bytes:
        comm = edge_tts.Communicate(text, self._voice, rate=self._rate)
        chunks = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks += chunk["data"]
        if not chunks:
            raise RuntimeError("edge-tts returned no audio")
        return bytes(chunks)

    async def synthesize(self, text: str) -> AudioClip:
        """Optionally split into sentence chunks synthesized in parallel and concatenated."""
        chunks = split_chunks(text, self._chunk_chars) if self._chunk_chars > 0 else [text]
        if len(chunks) <= 1:
            return await self._synthesize_hedged(text)
        clips = await asyncio.gather(*(self._synthesize_hedged(c) for c in chunks))
        return AudioClip(data=b"".join(c.data for c in clips), mime="audio/mpeg")

    async def _synthesize_hedged(self, text: str) -> AudioClip:
        pending: set[asyncio.Task[bytes]] = set()
        last: BaseException | None = None
        launched = 0
        try:
            while True:
                if launched < self._attempts:
                    pending.add(asyncio.create_task(self._once(text)))
                    launched += 1
                if not pending:
                    break
                timeout = self._hedge_s if launched < self._attempts else None
                done, pending = await asyncio.wait(pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    exc = task.exception()
                    if exc is None:
                        return AudioClip(data=task.result(), mime="audio/mpeg")
                    last = exc
                    log.warning("edge-tts attempt failed: %s", exc)
                if not done and launched < self._attempts:
                    log.info("edge-tts slow, hedging with attempt %d", launched + 1)
        finally:
            for task in pending:
                task.cancel()
        raise RuntimeError(f"edge-tts failed after {self._attempts} attempts: {last}")


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_chunks(text: str, max_chars: int) -> list[str]:
    """Group sentences into chunks of at most `max_chars` (a single long sentence stays whole)."""
    sentences = [p.strip() for p in _SENTENCE_END.split(text.strip()) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for sent in sentences:
        if cur and len(cur) + 1 + len(sent) > max_chars:
            chunks.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        chunks.append(cur)
    return chunks
