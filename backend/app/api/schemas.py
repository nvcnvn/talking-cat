from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgeGroup = Literal["3-6", "7-12"]


class TranscriptOut(BaseModel):
    text: str
    language: str
    confidence: float | None = None
    duration_s: float | None = None


class ReplyOut(BaseModel):
    text: str
    blocked: bool
    category: str
    llm_used: bool


class AudioOut(BaseModel):
    mime: str
    base64: str


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)
    age_group: AgeGroup = "3-6"


class ChatOut(BaseModel):
    session_id: str
    reply: ReplyOut


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class TalkOut(BaseModel):
    session_id: str
    transcript: TranscriptOut
    reply: ReplyOut
    audio: AudioOut | None
    timings_ms: dict[str, int]


class HealthOut(BaseModel):
    status: str
    providers: dict[str, str]
