"""ConversationService: the only place stages are wired together.

Every stage is injected, so any of them can be a fake. Each public method
corresponds to one stage plus `talk()` which runs the whole turn.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from .interfaces import LLMProvider, SafetyFilter, SessionStore, STTProvider, TTSProvider
from .models import AgeGroup, AudioClip, ChatReply, Message, SafetyVerdict, TalkResult, Transcript
from .prompts import FALLBACK_REPLY, LLM_ERROR_REPLY, REDIRECTS, system_prompt
from .safety import sanitize_for_speech

log = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    temperature: float = 0.7
    max_tokens: int = 220
    max_user_chars: int = 400
    max_reply_chars: int = 500
    stt_language: str = "vi"


class ConversationService:
    def __init__(
        self,
        *,
        stt: STTProvider,
        llm: LLMProvider,
        tts: TTSProvider,
        safety: SafetyFilter,
        sessions: SessionStore,
        config: PipelineConfig | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.safety = safety
        self.sessions = sessions
        self.cfg = config or PipelineConfig()
        self._rng = rng or random.Random()

    # ---- stage 1: speech to text ----
    async def transcribe(self, audio: bytes, mime: str) -> Transcript:
        return await self.stt.transcribe(audio, mime, language=self.cfg.stt_language)

    # ---- stage 2: safety + LLM ----
    async def reply(self, session_id: str, user_text: str, age_group: AgeGroup = "3-6") -> ChatReply:
        user_text = user_text.strip()[: self.cfg.max_user_chars]
        if not user_text:
            return ChatReply(FALLBACK_REPLY, blocked=False, llm_used=False)

        # Safety check and generation run concurrently: the LLM classifier costs a full
        # round-trip, and on the (rare) blocked input we simply discard the draft reply.
        history = self.sessions.get_history(session_id)
        messages = [Message("system", system_prompt(age_group)), *history, Message("user", user_text)]
        verdict, raw = await asyncio.gather(
            self.safety.check_input(user_text),
            self.llm.complete(messages, temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens),
            return_exceptions=True,
        )
        if isinstance(verdict, BaseException):
            log.exception("safety failure session=%s", session_id, exc_info=verdict)
            verdict = SafetyVerdict(False, "other_unsafe", "safety_error")
        if not verdict.allowed:
            log.info("blocked input session=%s category=%s reason=%s", session_id, verdict.category, verdict.reason)
            text = self._redirect(verdict.category)
            # Do not store the blocked utterance; store the redirect so the cat stays coherent.
            self.sessions.append(session_id, Message("assistant", text))
            return ChatReply(text, blocked=True, category=verdict.category, llm_used=False)
        if isinstance(raw, BaseException):
            log.error("llm failure session=%s: %r", session_id, raw)
            return ChatReply(LLM_ERROR_REPLY, blocked=False, llm_used=False)

        text = sanitize_for_speech(raw, self.cfg.max_reply_chars) or FALLBACK_REPLY
        out_verdict = await self.safety.check_output(text)
        if not out_verdict.allowed:
            log.warning("blocked output session=%s category=%s", session_id, out_verdict.category)
            text = self._redirect(out_verdict.category)
            self.sessions.append(session_id, Message("user", user_text), Message("assistant", text))
            return ChatReply(text, blocked=True, category=out_verdict.category, llm_used=True)

        self.sessions.append(session_id, Message("user", user_text), Message("assistant", text))
        return ChatReply(text)

    # ---- stage 3: text to speech ----
    async def speak(self, text: str) -> AudioClip:
        return await self.tts.synthesize(text)

    # ---- full turn ----
    async def talk(self, session_id: str, audio: bytes, mime: str, age_group: AgeGroup = "3-6", want_audio: bool = True) -> TalkResult:
        timings: dict[str, int] = {}
        t0 = time.perf_counter()
        transcript = await self.transcribe(audio, mime)
        timings["stt"] = int((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        reply = await self.reply(session_id, transcript.text, age_group)
        timings["llm"] = int((time.perf_counter() - t1) * 1000)

        clip: AudioClip | None = None
        if want_audio:
            t2 = time.perf_counter()
            try:
                clip = await self.speak(reply.text)
            except Exception:  # noqa: BLE001
                log.exception("tts failure session=%s", session_id)
            timings["tts"] = int((time.perf_counter() - t2) * 1000)
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        return TalkResult(transcript=transcript, reply=reply, audio=clip, session_id=session_id, timings_ms=timings)

    def _redirect(self, category: str) -> str:
        options = REDIRECTS.get(category) or REDIRECTS["default"]
        return self._rng.choice(options)
