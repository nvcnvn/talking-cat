import io
import math
import struct
import wave

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.core.pipeline import ConversationService
from app.core.safety import CompositeSafetyFilter, RuleBasedSafetyFilter
from app.core.session import InMemorySessionStore
from app.main import create_app
from app.providers.fakes import FakeLLM, FakeSTT, FakeTTS


def make_wav(seconds: float = 0.5, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 220 * i / rate))) for i in range(n)))
    return buf.getvalue()


@pytest.fixture
def wav_bytes() -> bytes:
    return make_wav()


@pytest.fixture
def fakes():
    return {"stt": FakeSTT(), "llm": FakeLLM(), "tts": FakeTTS()}


@pytest.fixture
def service(fakes) -> ConversationService:
    return ConversationService(
        stt=fakes["stt"],
        llm=fakes["llm"],
        tts=fakes["tts"],
        safety=CompositeSafetyFilter([RuleBasedSafetyFilter()]),
        sessions=InMemorySessionStore(),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(stt_provider="fake", llm_provider="fake", tts_provider="fake", safety_llm_check=False, _env_file=None)


@pytest.fixture
async def client(settings, service):
    app = create_app(settings, service)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
