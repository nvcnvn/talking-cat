"""Whisper on Apple Silicon via mlx-whisper (Metal). Runs natively on macOS, not in Docker.

Model weights are pulled from Hugging Face on first use (e.g. mlx-community/whisper-small-mlx,
mlx-community/whisper-large-v3-turbo). Audio is decoded in-process with PyAV, so no ffmpeg binary
is needed. Also runs on Linux CPU with `pip install "mlx[cpu]"` for testing the same code path.
"""
from __future__ import annotations

import asyncio
import logging
import threading

from ..core.models import Transcript
from .audio_decode import decode_to_pcm16k

log = logging.getLogger(__name__)


class MlxWhisperSTT:
    def __init__(self, model_repo: str = "mlx-community/whisper-small-mlx", initial_prompt: str = "") -> None:
        self._repo = model_repo
        self._initial_prompt = initial_prompt or None
        self._lock = threading.Lock()  # mlx_whisper is not re-entrant across threads
        self._loaded = False

    def warmup(self) -> None:
        """Download weights and JIT-compile kernels once, so the first child request is not slow."""
        import numpy as np

        self._transcribe_array(np.zeros(16000, dtype=np.float32), "vi")
        self._loaded = True

    def _transcribe_array(self, audio, language: str) -> dict:
        import mlx_whisper

        with self._lock:
            return mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=self._repo,
                language=language,
                initial_prompt=self._initial_prompt,
                condition_on_previous_text=False,
                fp16=True,
                verbose=None,
            )

    def _transcribe_sync(self, audio: bytes, mime: str, language: str) -> Transcript:
        pcm = decode_to_pcm16k(audio)
        if pcm.size == 0:
            return Transcript(text="", language=language, confidence=None, duration_s=0.0)
        result = self._transcribe_array(pcm, language)
        segments = result.get("segments") or []
        text = " ".join(s["text"].strip() for s in segments if s.get("text", "").strip()) or result.get("text", "").strip()
        probs = [s["avg_logprob"] for s in segments if "avg_logprob" in s]
        conf = None
        if probs:
            import math

            conf = float(sum(math.exp(p) for p in probs) / len(probs))
        duration = float(segments[-1]["end"]) if segments else None
        return Transcript(text=text, language=result.get("language") or language, confidence=conf, duration_s=duration)

    async def transcribe(self, audio: bytes, mime: str, language: str = "vi") -> Transcript:
        return await asyncio.to_thread(self._transcribe_sync, audio, mime, language)
