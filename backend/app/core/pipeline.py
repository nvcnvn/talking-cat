"""ConversationService: the only place stages are wired together.

Every stage is injected, so any of them can be a fake. Each public method
corresponds to one stage plus `talk()` which runs the whole turn.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass

from .interfaces import LLMProvider, SafetyFilter, SessionStore, STTProvider, TTSProvider
from .models import AgeGroup, AudioClip, ChatReply, Message, SafetyVerdict, TalkResult, Transcript, TurnEvent
from .prompts import (
    GENTLE_TOPIC_HINT,
    FALLBACK_REPLY,
    LLM_ERROR_REPLY,
    REDIRECTS,
    THINKING_LINES,
    UNCLEAR_AUDIO_REPLIES,
    system_prompt,
)
from .safety import sanitize_for_speech, soft_topic

log = logging.getLogger(__name__)


_SENTENCE_END = ".!?…\n"


class SentenceSplitter:
    """Cuts a token stream into speakable sentences.

    The first sentence may be short so the cat starts talking as early as possible;
    later ones are batched to keep the number of TTS calls (and their overhead) down.
    """

    def __init__(self, first_min: int = 8, min_chars: int = 40) -> None:
        self._buf = ""
        self._first_min = first_min
        self._min = min_chars
        self._emitted = 0

    def feed(self, delta: str) -> list[str]:
        self._buf += delta
        out: list[str] = []
        while (cut := self._cut()) is not None:
            piece, self._buf = self._buf[:cut].strip(), self._buf[cut:].lstrip()
            if piece:
                out.append(piece)
                self._emitted += 1
        return out

    def flush(self) -> str:
        piece, self._buf = self._buf.strip(), ""
        if piece:
            self._emitted += 1
        return piece

    def _cut(self) -> int | None:
        need = self._first_min if self._emitted == 0 else self._min
        for i, ch in enumerate(self._buf):
            if ch in _SENTENCE_END and i + 1 >= need:
                return i + 1
        return None


@dataclass
class PipelineConfig:
    temperature: float = 0.7
    max_tokens: int = 220
    max_user_chars: int = 400
    max_reply_chars: int = 500
    stt_language: str = "vi"
    min_confidence: float = 0.0  # transcripts below this are crosstalk/noise, not a question


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
        self._thinking_cache: dict[str, AudioClip] = {}

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
        messages = self._messages(session_id, user_text, age_group)
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
        out_verdict = await self.safety.check_output(text, user_text)
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

    def _messages(self, session_id: str, user_text: str, age_group: AgeGroup) -> list[Message]:
        """System prompt + history + the child's words, plus a gentle-handling hint when the
        child brings up something sensitive but ordinary (being hit, toy guns, scary films)."""
        system = system_prompt(age_group)
        if topic := soft_topic(user_text):
            log.info("soft topic=%s session=%s", topic, session_id)
            system = f"{system}\n\n{GENTLE_TOPIC_HINT}"
        return [Message("system", system), *self.sessions.get_history(session_id), Message("user", user_text)]

    async def thinking_clip(self, index: int) -> AudioClip:
        """A "let me think" filler in the cat's current voice. Cached: the words never change,
        and it must be instant - it exists to cover a wait, not to add one."""
        line = THINKING_LINES[index % len(THINKING_LINES)]
        if line not in self._thinking_cache:
            self._thinking_cache[line] = await self.speak(line)
        return self._thinking_cache[line]

    # ---- full turn ----
    async def talk(self, session_id: str, audio: bytes, mime: str, age_group: AgeGroup = "3-6", want_audio: bool = True) -> TalkResult:
        timings: dict[str, int] = {}
        t0 = time.perf_counter()
        transcript = await self.transcribe(audio, mime)
        timings["stt"] = int((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        if self._is_unclear(transcript):
            log.info("unclear audio session=%s conf=%s text=%r", session_id, transcript.confidence, transcript.text[:80])
            reply = ChatReply(self._rng.choice(UNCLEAR_AUDIO_REPLIES), blocked=False, llm_used=False)
        else:
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
        log.info("turn session=%s timings_ms=%s chars=%d", session_id, timings, len(reply.text))
        return TalkResult(transcript=transcript, reply=reply, audio=clip, session_id=session_id, timings_ms=timings)

    # ---- full turn, streamed ----
    async def talk_stream(
        self, session_id: str, audio: bytes, mime: str, age_group: AgeGroup = "3-6", want_audio: bool = True
    ) -> AsyncIterator[TurnEvent]:
        """Same turn as `talk()`, but the cat starts speaking the first sentence while the
        LLM is still writing the rest: generation, TTS and playback overlap."""
        t0 = time.perf_counter()
        timings: dict[str, int] = {}
        transcript = await self.transcribe(audio, mime)
        timings["stt"] = int((time.perf_counter() - t0) * 1000)
        yield TurnEvent("transcript", transcript=transcript)

        user_text = transcript.text.strip()[: self.cfg.max_user_chars]
        if not user_text or self._is_unclear(transcript):
            text = FALLBACK_REPLY if not user_text else self._rng.choice(UNCLEAR_AUDIO_REPLIES)
            async for ev in self._one_chunk_turn(session_id, text, want_audio, timings, t0, store_user=None):
                yield ev
            return

        safety = asyncio.create_task(self.safety.check_input(user_text))
        messages = self._messages(session_id, user_text, age_group)

        deltas: asyncio.Queue[str | None] = asyncio.Queue()
        failure: list[BaseException] = []

        async def pump() -> None:
            try:
                async for delta in self.llm.stream(messages, temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens):
                    await deltas.put(delta)
            except BaseException as exc:  # noqa: BLE001 - reported to the consumer below
                failure.append(exc)
            finally:
                await deltas.put(None)

        pump_task = asyncio.create_task(pump())
        splitter = SentenceSplitter()
        pending: deque[tuple[str, asyncio.Task[AudioClip] | None]] = deque()
        spoken: list[str] = []
        checked_input = False
        stop = False
        redirect: str | None = None

        def speak_task(text: str) -> asyncio.Task[AudioClip] | None:
            return asyncio.create_task(self.speak(text)) if want_audio else None

        async def gate(sentence: str) -> str | None:
            """Safety for one sentence: the input verdict once, output rules every time."""
            nonlocal checked_input
            if not checked_input:
                checked_input = True
                verdict = await safety
                if isinstance(verdict, BaseException) or not verdict.allowed:
                    category = "other_unsafe" if isinstance(verdict, BaseException) else verdict.category
                    log.info("blocked input session=%s category=%s", session_id, category)
                    return None
            out = await self.safety.check_output(sentence, user_text)
            if not out.allowed:
                log.warning("blocked output session=%s category=%s", session_id, out.category)
                return None
            return sentence

        try:
            while True:
                if pending:
                    text, task = pending.popleft()
                    clip = await task if task else None
                    timings.setdefault("first_audio", int((time.perf_counter() - t0) * 1000))
                    yield TurnEvent("chunk", text=text, audio=clip)
                    continue
                if stop:
                    break
                item = await deltas.get()
                if item is None:
                    if failure and not spoken:
                        log.error("llm stream failure session=%s: %r", session_id, failure[0])
                        async for ev in self._one_chunk_turn(session_id, LLM_ERROR_REPLY, want_audio, timings, t0, store_user=None):
                            yield ev
                        return
                    if tail := splitter.flush():
                        sentences = [tail]
                    else:
                        sentences = []
                    stop = True
                else:
                    timings.setdefault("llm_first_token", int((time.perf_counter() - t0) * 1000))
                    sentences = splitter.feed(item)
                for sentence in sentences:
                    budget = self.cfg.max_reply_chars - sum(len(s) for s in spoken)
                    clean = sanitize_for_speech(sentence, max(budget, 0))
                    if not clean:
                        continue
                    safe = await gate(clean)
                    if safe is None:
                        for _, task in pending:
                            if task:
                                task.cancel()
                        pending.clear()
                        spoken.clear()
                        redirect = self._redirect("default")
                        pending.append((redirect, speak_task(redirect)))
                        stop = True
                        break
                    spoken.append(safe)
                    pending.append((safe, speak_task(safe)))
                    if len(" ".join(spoken)) >= self.cfg.max_reply_chars:
                        stop = True
                        break
        finally:
            pump_task.cancel()
            for _, task in pending:
                if task:
                    task.cancel()

        reply_text = redirect or " ".join(spoken) or FALLBACK_REPLY
        if redirect:
            # Do not store the blocked utterance; store the redirect so the cat stays coherent.
            self.sessions.append(session_id, Message("assistant", reply_text))
        else:
            self.sessions.append(session_id, Message("user", user_text), Message("assistant", reply_text))
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        log.info("turn(stream) session=%s timings_ms=%s chars=%d", session_id, timings, len(reply_text))
        yield TurnEvent("done", text=reply_text, blocked=redirect is not None, timings_ms=timings)

    async def _one_chunk_turn(
        self, session_id: str, text: str, want_audio: bool, timings: dict[str, int], t0: float, store_user: str | None
    ) -> AsyncIterator[TurnEvent]:
        """A whole reply the LLM did not write (fallback, redirect, error): one chunk, then done."""
        clip = None
        if want_audio:
            try:
                clip = await self.speak(text)
            except Exception:  # noqa: BLE001
                log.exception("tts failure session=%s", session_id)
        timings["first_audio"] = int((time.perf_counter() - t0) * 1000)
        if store_user is not None:
            self.sessions.append(session_id, Message("user", store_user), Message("assistant", text))
        yield TurnEvent("chunk", text=text, audio=clip)
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        log.info("turn(stream) session=%s timings_ms=%s chars=%d", session_id, timings, len(text))
        yield TurnEvent("done", text=text, blocked=False, timings_ms=timings)

    def _is_unclear(self, t: Transcript) -> bool:
        """Noise gate, not a crosstalk detector: it only catches audio Whisper itself is unsure of
        (measured ~0.53 on babble, ~0.88 on one clear voice). Clear voices overlapping stay ~0.85
        and are caught by the persona prompt instead."""
        return bool(t.text.strip()) and t.confidence is not None and t.confidence < self.cfg.min_confidence

    def _redirect(self, category: str) -> str:
        options = REDIRECTS.get(category) or REDIRECTS["default"]
        return self._rng.choice(options)
