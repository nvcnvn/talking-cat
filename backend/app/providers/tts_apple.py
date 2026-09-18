"""macOS on-device voice via the `say` binary.

No network and no model download: the voice ships with the OS. On this machine `Linh` (vi_VN)
renders a ~9 s reply in ~0.5 s, which is fast enough to be the primary voice, so every utterance
in a turn - filler included - comes from the same engine instead of flipping between two.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from ..core.models import AudioClip

log = logging.getLogger(__name__)


class AppleSayTTS:
    def __init__(self, voice: str = "Linh", rate_wpm: int = 180) -> None:
        self._voice = voice
        self._rate = str(rate_wpm)

    async def synthesize(self, text: str) -> AudioClip:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "say.wav"
            proc = await asyncio.create_subprocess_exec(
                "say", "-v", self._voice, "-r", self._rate, "-o", str(out),
                "--data-format=LEI16@22050", "--", text,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(f"say failed ({proc.returncode}): {err.decode()[:200]}")
            return AudioClip(data=out.read_bytes(), mime="audio/wav")
