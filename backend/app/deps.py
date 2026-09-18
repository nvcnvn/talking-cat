"""Builds providers from Settings. This is the single composition root."""
from __future__ import annotations

import logging

from .config import Settings
from .core.pipeline import ConversationService, PipelineConfig
from .core.safety import CompositeSafetyFilter, LLMSafetyFilter, RuleBasedSafetyFilter
from .core.session import InMemorySessionStore
from .providers.fakes import FakeLLM, FakeSTT, FakeTTS

log = logging.getLogger(__name__)


def build_stt(s: Settings):
    if s.stt_provider == "fake":
        return FakeSTT()
    if s.stt_provider == "mlx_whisper":
        from .providers.stt_mlx_whisper import MlxWhisperSTT

        return MlxWhisperSTT(s.mlx_whisper_model, s.whisper_initial_prompt)
    from .providers.stt_whisper import WhisperSTT

    return WhisperSTT(s.whisper_model, s.whisper_device, s.whisper_compute_type, s.whisper_initial_prompt)


def build_llm(s: Settings):
    if s.llm_provider == "fake":
        return FakeLLM()
    from .providers.llm_openai_compat import OpenAICompatLLM

    if not s.llm_api_key:
        log.warning("LLM_API_KEY is empty; LLM calls will fail")
    return OpenAICompatLLM(s.llm_base_url, s.llm_api_key, s.llm_model, s.llm_timeout_s)


def _tts_by_name(name: str, s: Settings):
    if name == "fake":
        return FakeTTS()
    if name == "piper":
        from .providers.tts_piper import PiperTTS

        return PiperTTS(s.piper_voice, s.piper_data_dir)
    from .providers.tts_edge import EdgeTTS

    return EdgeTTS(s.tts_voice, s.tts_rate)


def build_tts(s: Settings):
    primary = _tts_by_name(s.tts_provider, s)
    if s.tts_fallback == "none" or s.tts_fallback == s.tts_provider:
        return primary
    from .providers.tts_fallback import FallbackTTS

    return FallbackTTS(primary, _tts_by_name(s.tts_fallback, s), s.tts_deadline_s)


def build_safety(s: Settings, llm):
    rules = RuleBasedSafetyFilter()
    classifier = LLMSafetyFilter(llm)
    inputs = [rules, classifier] if s.safety_llm_check else [rules]
    outputs = [rules, classifier] if s.safety_llm_check_output else [rules]
    return CompositeSafetyFilter(inputs, outputs)


def build_service(s: Settings) -> ConversationService:
    llm = build_llm(s)
    return ConversationService(
        stt=build_stt(s),
        llm=llm,
        tts=build_tts(s),
        safety=build_safety(s, llm),
        sessions=InMemorySessionStore(s.session_ttl_s, s.session_max_turns),
        config=PipelineConfig(
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            max_user_chars=s.max_user_chars,
            max_reply_chars=s.max_reply_chars,
            stt_language=s.whisper_language,
            min_confidence=s.stt_min_confidence,
        ),
    )
