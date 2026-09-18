"""Fake providers for tests and for running the stack without models or API keys.

Select with STT_PROVIDER=fake, LLM_PROVIDER=fake, TTS_PROVIDER=fake.
"""
from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import dataclass, field

from ..core.models import AudioClip, Message, Transcript

FAKE_TRANSCRIPT_PREFIX = b"#transcript:"


@dataclass
class FakeSTT:
    """Returns `default_text`, unless the payload is a UTF-8 text file starting with
    `#transcript:` in which case the rest of the line is returned. Lets end-to-end
    tests upload a tiny text file instead of real audio and still control the words.
    Real audio bytes (e.g. a .wav fixture) fall back to `default_text`."""

    default_text: str = "xin chào Miu"
    calls: list[tuple[int, str]] = field(default_factory=list)

    async def transcribe(self, audio: bytes, mime: str, language: str = "vi") -> Transcript:
        self.calls.append((len(audio), mime))
        if audio.startswith(FAKE_TRANSCRIPT_PREFIX):
            text = audio[len(FAKE_TRANSCRIPT_PREFIX) :].split(b"\n", 1)[0].decode("utf-8", "replace").strip()
            return Transcript(text=text, language=language, confidence=1.0)
        return Transcript(text=self.default_text, language=language, confidence=1.0, duration_s=1.0)


@dataclass
class FakeLLM:
    """Scripted replies. Pops from `script` if present, else echoes the last user message.
    Records every request so tests can assert on the prompt."""

    script: list[str] = field(default_factory=list)
    requests: list[list[Message]] = field(default_factory=list)
    raise_error: Exception | None = None

    async def complete(self, messages: list[Message], *, temperature: float, max_tokens: int) -> str:
        self.requests.append(list(messages))
        if self.raise_error:
            raise self.raise_error
        if self.script:
            return self.script.pop(0)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        # The safety classifier prompt goes through the same LLM; answer "ok" to it.
        if messages and messages[0].role == "system" and "content-safety classifier" in messages[0].content:
            return "ok"
        return f"Meo meo! Bạn vừa nói: {last_user}. Bạn có muốn chơi đố vui không?"

    async def stream(self, messages: list[Message], *, temperature: float, max_tokens: int):
        """Same words as `complete`, handed over in small pieces like a real stream."""
        text = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        for i in range(0, len(text), 7):
            yield text[i : i + 7]


@dataclass
class FakeTTS:
    """Produces a real, playable WAV (soft beep whose length scales with the text)
    so the browser playback path and lip-sync are exercised without a TTS service."""

    sample_rate: int = 16000
    seconds_per_char: float = 0.04
    calls: list[str] = field(default_factory=list)

    async def synthesize(self, text: str) -> AudioClip:
        self.calls.append(text)
        return AudioClip(data=self.render(text), mime="audio/wav")

    def render(self, text: str) -> bytes:
        n = int(self.sample_rate * max(0.4, min(6.0, len(text) * self.seconds_per_char)))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            frames = bytearray()
            for i in range(n):
                # gentle amplitude modulation so a level meter shows movement
                env = 0.5 + 0.5 * math.sin(2 * math.pi * 3 * i / self.sample_rate)
                sample = int(6000 * env * math.sin(2 * math.pi * 440 * i / self.sample_rate))
                frames += struct.pack("<h", sample)
            w.writeframes(bytes(frames))
        return buf.getvalue()
