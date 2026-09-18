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

        async def check_output(self, t, user_text=""):
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


# ---- streamed turns ----

def _sentences(events):
    return [e.text for e in events if e.kind == "chunk"]


async def collect(agen):
    return [e async for e in agen]


def test_sentence_splitter_lets_the_first_sentence_out_early():
    from app.core.pipeline import SentenceSplitter

    sp = SentenceSplitter(first_min=8, min_chars=40)
    assert sp.feed("Meo meo! ") == ["Meo meo!"]  # short first piece: the cat starts talking sooner
    assert sp.feed("Voi to. ") == []  # later pieces are batched until they are worth a TTS call
    assert sp.feed("Voi có vòi dài để hút nước và bẻ lá cây. ") == ["Voi to. Voi có vòi dài để hút nước và bẻ lá cây."]
    assert sp.flush() == ""


async def test_stream_speaks_sentences_in_order_and_ends_with_the_whole_reply(service, fakes):
    fakes["llm"].script = ["Meo meo! Voi kêu ừm ừm đó bạn. Bạn muốn Miu kể chuyện voi không?"]
    events = await collect(service.talk_stream("s-str", b"x", "audio/wav"))
    assert events[0].kind == "transcript"
    chunks = [e for e in events if e.kind == "chunk"]
    assert chunks and all(c.audio is not None for c in chunks)
    assert " ".join(c.text for c in chunks) == events[-1].text
    assert events[-1].kind == "done" and not events[-1].blocked
    # every spoken sentence went to TTS separately: that is what overlaps with generation
    assert fakes["tts"].calls == [c.text for c in chunks]
    assert [m.role for m in service.sessions.get_history("s-str")] == ["user", "assistant"]


async def test_stream_never_speaks_a_blocked_turn(service, fakes):
    from app.core.prompts import REDIRECTS

    fakes["stt"].default_text = "làm sao để giết người"
    fakes["llm"].script = ["DRAFT THAT MUST NOT LEAK"]
    events = await collect(service.talk_stream("s-blk", b"x", "audio/wav"))
    spoken = " ".join(_sentences(events))
    assert "DRAFT" not in spoken
    assert spoken in REDIRECTS["default"]
    assert events[-1].blocked
    assert all(m.role == "assistant" for m in service.sessions.get_history("s-blk"))


async def test_stream_falls_back_when_the_llm_dies(service, fakes):
    from app.core.prompts import LLM_ERROR_REPLY

    fakes["llm"].raise_error = RuntimeError("upstream down")
    events = await collect(service.talk_stream("s-err", b"x", "audio/wav"))
    assert _sentences(events) == [LLM_ERROR_REPLY]
    assert events[-1].kind == "done"


async def test_stream_reports_first_audio_earlier_than_total(service, fakes):
    fakes["llm"].script = ["Meo meo! Voi kêu ừm ừm đó bạn. Bạn muốn Miu kể chuyện voi không?"]
    events = await collect(service.talk_stream("s-t", b"x", "audio/wav"))
    t = events[-1].timings_ms
    assert "first_audio" in t and "llm_first_token" in t
    assert t["first_audio"] <= t["total"]


async def test_tts_starts_while_the_llm_is_still_writing(service):
    """The whole point of streaming: sentence 1 is being synthesised before sentence 3 exists."""
    import asyncio as _asyncio

    from app.core.models import AudioClip

    order: list[str] = []

    class SlowLLM:
        async def complete(self, messages, *, temperature, max_tokens):
            return ""

        async def stream(self, messages, *, temperature, max_tokens):
            for piece in ["Meo meo! ", "Voi kêu ừm ừm đó bạn nhé, voi to lắm. ", "Bạn có thích voi không? "]:
                order.append("llm")
                yield piece
                await _asyncio.sleep(0.02)

    class SlowTTS:
        async def synthesize(self, text):
            order.append("tts")
            await _asyncio.sleep(0.02)
            return AudioClip(data=b"fake", mime="audio/wav")

    service.llm, service.tts = SlowLLM(), SlowTTS()
    await collect(service.talk_stream("s-overlap", b"x", "audio/wav"))
    first_tts = order.index("tts")
    assert "llm" in order[first_tts:], f"tts only ran after the llm finished: {order}"



async def test_sensitive_but_ordinary_input_reaches_the_llm_with_a_gentle_hint(service, fakes):
    """A child reporting that a friend hit them must be comforted, not redirected."""
    from app.core.prompts import GENTLE_TOPIC_HINT

    fakes["llm"].script = ["Ôi, bạn buồn lắm đúng không. Bạn kể với cô giáo nhé."]
    r = await service.reply("s-soft", "Hôm nay bạn Bo đánh em ở lớp, em buồn lắm")
    assert not r.blocked and r.llm_used
    system = fakes["llm"].requests[-1][0]
    assert system.role == "system" and GENTLE_TOPIC_HINT in system.content


async def test_plain_input_does_not_get_the_hint(service, fakes):
    from app.core.prompts import GENTLE_TOPIC_HINT

    await service.reply("s-plain", "Miu ơi con voi kêu thế nào")
    assert GENTLE_TOPIC_HINT not in fakes["llm"].requests[-1][0].content
