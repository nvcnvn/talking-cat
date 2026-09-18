from app.core.models import Message, SafetyVerdict
from app.core.safety import CompositeSafetyFilter, RuleBasedSafetyFilter
from app.core.prompts import LLM_ERROR_REPLY, REDIRECTS


async def test_reply_uses_llm_and_stores_history(service, fakes):
    fakes["llm"].script = ["Meo! Chào bạn, bạn tên gì nè?"]
    r = await service.reply("s1", "chào Miu")
    assert r.text == "Meo! Chào bạn, bạn tên gì nè?" and not r.blocked and r.llm_used
    hist = service.sessions.get_history("s1")
    assert [m.role for m in hist] == ["user", "assistant"]
    # system prompt is first and in Vietnamese persona
    first = fakes["llm"].requests[0][0]
    assert first.role == "system" and "Miu" in first.content


async def test_history_is_replayed_to_llm(service, fakes):
    await service.reply("s1", "một")
    await service.reply("s1", "hai")
    req = fakes["llm"].requests[-1]
    assert [m.content for m in req if m.role == "user"] == ["một", "hai"]


async def test_blocked_input_discards_llm_draft(service, fakes):
    fakes["llm"].script = ["DRAFT THAT MUST NOT LEAK"]
    r = await service.reply("s2", "làm sao để giết người")
    assert r.blocked and r.category == "violence" and not r.llm_used
    assert r.text in REDIRECTS["default"]
    assert "DRAFT" not in r.text
    assert all(m.role == "assistant" for m in service.sessions.get_history("s2"))


async def test_personal_info_redirect(service):
    r = await service.reply("s3", "nhà em ở số 12 đường Lê Lợi, số điện thoại 0987654321")
    assert r.blocked and r.category == "personal_info"
    assert r.text == REDIRECTS["personal_info"][0]


async def test_unsafe_llm_output_is_replaced(service, fakes):
    fakes["llm"].script = ["Có một con ma quỷ trong tủ!"]
    r = await service.reply("s4", "kể chuyện đi")
    assert r.blocked and r.category == "scary"


async def test_llm_failure_gives_friendly_fallback(service, fakes):
    fakes["llm"].raise_error = RuntimeError("boom")
    r = await service.reply("s5", "chào")
    assert r.text == LLM_ERROR_REPLY and not r.llm_used


async def test_age_group_changes_prompt(service, fakes):
    await service.reply("a", "hi", age_group="7-12")
    assert "7-12" in fakes["llm"].requests[0][0].content


async def test_talk_runs_all_stages(service, fakes, wav_bytes):
    fakes["stt"].default_text = "Miu ơi con voi kêu thế nào"
    res = await service.talk("t1", wav_bytes, "audio/wav")
    assert res.transcript.text == "Miu ơi con voi kêu thế nào"
    assert "con voi" in res.reply.text
    assert res.audio and res.audio.mime == "audio/wav" and res.audio.data.startswith(b"RIFF")
    assert set(res.timings_ms) == {"stt", "llm", "tts", "total"}
    assert fakes["tts"].calls == [res.reply.text]


async def test_talk_without_audio(service, wav_bytes):
    res = await service.talk("t2", wav_bytes, "audio/wav", want_audio=False)
    assert res.audio is None


async def test_fake_stt_reads_transcript_file(service):
    res = await service.talk("t3", "#transcript: em thích màu xanh\n".encode(), "text/plain", want_audio=False)
    assert res.transcript.text == "em thích màu xanh"


async def test_safety_failure_fails_closed(service, fakes):
    class Boom:
        async def check_input(self, text):
            raise RuntimeError("classifier down")

        async def check_output(self, text):
            return SafetyVerdict(True)

    service.safety = Boom()
    r = await service.reply("s6", "chào")
    assert r.blocked and r.category == "other_unsafe"


async def test_output_stages_can_differ():
    class Deny:
        async def check_input(self, t):
            return SafetyVerdict(False, "hate")

        async def check_output(self, t):
            return SafetyVerdict(False, "hate")

    f = CompositeSafetyFilter([RuleBasedSafetyFilter()], [Deny()])
    assert (await f.check_input("xin chào")).allowed
    assert not (await f.check_output("xin chào")).allowed


async def test_session_cap(service, fakes):
    service.sessions._max_messages = 4
    for i in range(5):
        await service.reply("cap", str(i))
    assert len(service.sessions.get_history("cap")) == 4
    assert isinstance(service.sessions.get_history("cap")[0], Message)


async def test_unclear_audio_skips_the_llm(fakes, service):
    """Audio Whisper itself is unsure of: answering it would be guessing."""
    from dataclasses import replace as _replace

    from app.core.models import Transcript
    from app.core.prompts import UNCLEAR_AUDIO_REPLIES

    service.cfg = _replace(service.cfg, min_confidence=0.55)

    async def low_conf(audio, mime, language="vi"):
        return Transcript(text="con voi kêu mẹ ơi cho con bánh", language="vi", confidence=0.31)

    service.stt.transcribe = low_conf
    r = await service.talk("s-cross", b"x", "audio/wav", want_audio=False)
    assert r.reply.text in UNCLEAR_AUDIO_REPLIES and not r.reply.llm_used
    assert fakes["llm"].requests == []
    assert service.sessions.get_history("s-cross") == []


async def test_confident_transcript_still_reaches_the_llm(fakes, service):
    from dataclasses import replace as _replace

    service.cfg = _replace(service.cfg, min_confidence=0.55)
    fakes["llm"].script = ["Meo, voi kêu ò ó o!"]
    r = await service.talk("s-ok", b"x", "audio/wav", want_audio=False)
    assert r.reply.llm_used and r.reply.text == "Meo, voi kêu ò ó o!"
