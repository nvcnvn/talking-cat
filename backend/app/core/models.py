"""Plain data passed between stages. No framework types here."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]
AgeGroup = Literal["3-6", "7-12"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str = "vi"
    confidence: float | None = None
    duration_s: float | None = None


@dataclass(frozen=True)
class AudioClip:
    data: bytes
    mime: str  # e.g. "audio/mpeg", "audio/wav"


@dataclass(frozen=True)
class SafetyVerdict:
    allowed: bool
    category: str = "ok"  # ok | violence | sexual | drugs | self_harm | personal_info | hate | other
    reason: str = ""


@dataclass(frozen=True)
class ChatReply:
    text: str
    blocked: bool = False
    category: str = "ok"
    llm_used: bool = True


@dataclass
class TalkResult:
    transcript: Transcript
    reply: ChatReply
    audio: AudioClip | None
    session_id: str
    timings_ms: dict[str, int] = field(default_factory=dict)
