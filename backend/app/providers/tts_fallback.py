"""Primary TTS with a deadline; falls back to a second provider on timeout or error."""
from __future__ import annotations

import asyncio
import logging

from ..core.interfaces import TTSProvider
from ..core.models import AudioClip

log = logging.getLogger(__name__)


class FallbackTTS:
    def __init__(self, primary: TTSProvider, fallback: TTSProvider, deadline_s: float = 4.0) -> None:
        self.primary = primary
        self.fallback = fallback
        self.deadline_s = deadline_s

    async def synthesize(self, text: str) -> AudioClip:
        try:
            return await asyncio.wait_for(self.primary.synthesize(text), timeout=self.deadline_s)
        except asyncio.TimeoutError:
            log.warning("primary tts exceeded %.1fs, using fallback", self.deadline_s)
        except Exception as exc:  # noqa: BLE001
            log.warning("primary tts failed (%s), using fallback", exc)
        return await self.fallback.synthesize(text)

    def warmup(self) -> None:
        for p in (self.primary, self.fallback):
            w = getattr(p, "warmup", None)
            if w:
                w()
