"""A TTS failure must not kill the turn: the child still gets the sentences on screen."""
import asyncio, pytest
from app.core.pipeline import ConversationService
from app.core.models import Transcript, SafetyVerdict
from app.core.session import InMemorySessionStore


class BoomTTS:
    async def synthesize(self, text): raise RuntimeError("say failed")

class OneVoiceSTT:
    async def transcribe(self, a, m, language="vi"): return Transcript("con voi ăn gì", "vi", 0.9)

class TinyLLM:
    async def complete(self, m, *, temperature, max_tokens): return "Voi ăn lá cây. Bạn thích voi không?"
    async def stream(self, m, *, temperature, max_tokens):
        for d in ["Voi ăn lá cây. ", "Bạn thích voi không?"]:
            yield d

class OkSafety:
    async def check_input(self, t): return SafetyVerdict(True, "ok", "")
    async def check_output(self, t, u=""): return SafetyVerdict(True, "ok", "")


def test_tts_failure_still_delivers_the_reply():
    svc = ConversationService(stt=OneVoiceSTT(), llm=TinyLLM(), tts=BoomTTS(),
                              safety=OkSafety(), sessions=InMemorySessionStore(600, 12))

    async def run():
        return [e async for e in svc.talk_stream("s1", b"x", "audio/wav", "3-6", True)]

    events = asyncio.run(run())
    kinds = [e.kind for e in events]
    assert "done" in kinds, f"turn died instead of finishing: {kinds}"
    chunks = [e for e in events if e.kind == "chunk"]
    assert chunks, "no sentences reached the child"
    assert all(e.audio is None for e in chunks), "expected silent chunks"
    assert "Voi ăn lá cây." in " ".join(e.text for e in chunks)
