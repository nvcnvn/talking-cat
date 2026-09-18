"""Provider contracts. Each has a real and a fake implementation in app/providers."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import AudioClip, Message, SafetyVerdict, Transcript


@runtime_checkable
class STTProvider(Protocol):
    async def transcribe(self, audio: bytes, mime: str, language: str = "vi") -> Transcript: ...


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], *, temperature: float, max_tokens: int) -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> AudioClip: ...


@runtime_checkable
class SafetyFilter(Protocol):
    async def check_input(self, text: str) -> SafetyVerdict: ...
    async def check_output(self, text: str) -> SafetyVerdict: ...


@runtime_checkable
class SessionStore(Protocol):
    def get_history(self, session_id: str) -> list[Message]: ...
    def append(self, session_id: str, *messages: Message) -> None: ...
    def clear(self, session_id: str) -> None: ...
