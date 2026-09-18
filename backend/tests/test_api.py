import base64


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["providers"] == {"stt": "fake", "llm": "fake", "tts": "fake"}


async def test_stt_endpoint(client, wav_bytes):
    r = await client.post("/api/stt", files={"audio": ("a.wav", wav_bytes, "audio/wav")})
    assert r.status_code == 200 and r.json()["text"] == "xin chào Miu"


async def test_chat_endpoint(client):
    r = await client.post("/api/chat", json={"session_id": "abc", "text": "chào Miu"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "abc" and "chào Miu" in body["reply"]["text"]


async def test_tts_endpoint_returns_audio(client):
    r = await client.post("/api/tts", json={"text": "xin chào"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/wav")
    assert r.content.startswith(b"RIFF")


async def test_talk_endpoint_full_turn(client, wav_bytes):
    r = await client.post("/api/talk", files={"audio": ("a.wav", wav_bytes, "audio/wav")}, data={"session_id": "s9", "age_group": "7-12"})
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"]["text"] == "xin chào Miu"
    assert body["reply"]["blocked"] is False
    assert base64.b64decode(body["audio"]["base64"]).startswith(b"RIFF")


async def test_talk_generates_session_id(client, wav_bytes):
    r = await client.post("/api/talk", files={"audio": ("a.wav", wav_bytes, "audio/wav")})
    assert len(r.json()["session_id"]) == 32


async def test_talk_rejects_empty(client):
    r = await client.post("/api/talk", files={"audio": ("a.wav", b"", "audio/wav")})
    assert r.status_code == 400


async def test_clear_session(client):
    await client.post("/api/chat", json={"session_id": "z", "text": "hi"})
    r = await client.delete("/api/session/z")
    assert r.status_code == 204


def test_build_tts_wiring():
    from app.config import Settings
    from app.deps import build_tts
    from app.providers.fakes import FakeTTS
    from app.providers.tts_fallback import FallbackTTS

    assert isinstance(build_tts(Settings(tts_provider="fake", tts_fallback="none", _env_file=None)), FakeTTS)
    assert isinstance(build_tts(Settings(tts_provider="fake", tts_fallback="fake", _env_file=None)), FakeTTS)
    t = build_tts(Settings(tts_provider="edge", tts_fallback="fake", tts_deadline_s=2.5, _env_file=None))
    assert isinstance(t, FallbackTTS) and isinstance(t.fallback, FakeTTS) and t.deadline_s == 2.5
