import asyncio

from app.core.models import AudioClip
from app.providers.fakes import FakeTTS
from app.providers.tts_fallback import FallbackTTS


class SlowTTS:
    def __init__(self, delay, fail=False):
        self.delay, self.fail = delay, fail

    async def synthesize(self, text):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("upstream")
        return AudioClip(b"PRIMARY", "audio/mpeg")


async def test_primary_wins_when_fast():
    t = FallbackTTS(SlowTTS(0.01), FakeTTS(), deadline_s=0.5)
    assert (await t.synthesize("x")).data == b"PRIMARY"


async def test_fallback_on_deadline():
    fb = FakeTTS()
    t = FallbackTTS(SlowTTS(0.5), fb, deadline_s=0.05)
    clip = await t.synthesize("xin chào")
    assert clip.mime == "audio/wav" and fb.calls == ["xin chào"]


async def test_fallback_on_error():
    fb = FakeTTS()
    t = FallbackTTS(SlowTTS(0.0, fail=True), fb, deadline_s=1)
    assert (await t.synthesize("x")).mime == "audio/wav"
