"""Self-hosted Piper TTS (ONNX, CPU). Deterministic and fast; voice quality is plainer than Edge."""
from __future__ import annotations

import asyncio
import io
import logging
import threading
import wave
from pathlib import Path

from ..core.models import AudioClip

log = logging.getLogger(__name__)


class PiperTTS:
    def __init__(self, voice: str = "vi_VN-vais1000-medium", data_dir: str = "/opt/piper") -> None:
        self._voice = voice
        self._data_dir = Path(data_dir)
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from piper import PiperVoice  # lazy: heavy import

                    path = self._data_dir / f"{self._voice}.onnx"
                    if not path.exists():
                        from piper.download_voices import download_voice

                        log.info("downloading piper voice %s to %s", self._voice, self._data_dir)
                        self._data_dir.mkdir(parents=True, exist_ok=True)
                        download_voice(self._voice, self._data_dir)
                    log.info("loading piper voice %s", path)
                    self._model = PiperVoice.load(str(path))
        return self._model

    def warmup(self) -> None:
        self._get_model()

    def _synth_sync(self, text: str) -> bytes:
        model = self._get_model()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            model.synthesize_wav(text, w)
        return buf.getvalue()

    async def synthesize(self, text: str) -> AudioClip:
        data = await asyncio.to_thread(self._synth_sync, text)
        return AudioClip(data=data, mime="audio/wav")
