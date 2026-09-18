"""faster-whisper STT. Model is loaded lazily on first use and inference runs in a thread."""
from __future__ import annotations

import asyncio
import io
import logging
import threading

from ..core.models import Transcript

log = logging.getLogger(__name__)


class WhisperSTT:
    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8", initial_prompt: str = "") -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._initial_prompt = initial_prompt or None
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel  # heavy import, keep lazy

                    log.info("loading whisper model=%s device=%s compute=%s", self._model_size, self._device, self._compute_type)
                    self._model = WhisperModel(self._model_size, device=self._device, compute_type=self._compute_type)
        return self._model

    def warmup(self) -> None:
        self._get_model()

    def _transcribe_sync(self, audio: bytes, language: str) -> Transcript:
        model = self._get_model()
        segments, info = model.transcribe(
            io.BytesIO(audio),
            language=language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=self._initial_prompt,
        )
        parts, probs = [], []
        for seg in segments:
            parts.append(seg.text.strip())
            probs.append(seg.avg_logprob)
        text = " ".join(p for p in parts if p)
        conf = None
        if probs:
            import math

            conf = float(sum(math.exp(p) for p in probs) / len(probs))
        return Transcript(text=text, language=info.language or language, confidence=conf, duration_s=float(info.duration or 0))

    async def transcribe(self, audio: bytes, mime: str, language: str = "vi") -> Transcript:
        return await asyncio.to_thread(self._transcribe_sync, audio, language)
