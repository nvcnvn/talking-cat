import asyncio

import pytest

pytest.importorskip("edge_tts")
from app.providers.tts_edge import EdgeTTS, split_chunks  # noqa: E402


async def test_hedge_takes_first_success(monkeypatch):
    tts = EdgeTTS(attempts=3, hedge_s=0.05)
    calls = []

    async def fake_once(self, text):
        n = len(calls)
        calls.append(n)
        if n == 0:
            await asyncio.sleep(1.0)  # simulates the hanging attempt
            raise RuntimeError("no audio")
        return b"MP3" + bytes([n])

    monkeypatch.setattr(EdgeTTS, "_once", fake_once)
    clip = await asyncio.wait_for(tts.synthesize("xin chào"), 0.5)
    assert clip.data == b"MP3\x01" and clip.mime == "audio/mpeg"
    assert len(calls) == 2


async def test_all_attempts_fail(monkeypatch):
    async def fake_once(self, text):
        raise RuntimeError("no audio")

    monkeypatch.setattr(EdgeTTS, "_once", fake_once)
    with pytest.raises(RuntimeError, match="after 2 attempts"):
        await EdgeTTS(attempts=2, hedge_s=0.01).synthesize("x")


def test_split_chunks_groups_sentences():
    text = "Một. Hai hai. Ba ba ba! Bốn bốn bốn bốn? Năm."
    assert split_chunks(text, 14) == ["Một. Hai hai.", "Ba ba ba!", "Bốn bốn bốn bốn?", "Năm."]
    assert split_chunks("chỉ một câu dài không có dấu chấm", 5) == ["chỉ một câu dài không có dấu chấm"]
    assert split_chunks("  ", 10) == []


async def test_long_text_is_chunked_and_concatenated(monkeypatch):
    async def fake_once(self, text):
        return text.encode() + b"|"

    monkeypatch.setattr(EdgeTTS, "_once", fake_once)
    clip = await EdgeTTS(chunk_chars=10).synthesize("Câu một. Câu hai. Câu ba.")
    assert clip.data == "Câu một.|Câu hai.|Câu ba.|".encode()
