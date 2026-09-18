"""MlxWhisperSTT is exercised with a stubbed `mlx_whisper` module so it runs on Linux CI."""
import sys
import types

import pytest

from app.providers.stt_mlx_whisper import MlxWhisperSTT


@pytest.fixture
def fake_mlx(monkeypatch):
    calls = []

    def transcribe(audio, **kw):
        calls.append((audio, kw))
        return {
            "text": " Miu ơi, con voi kêu thế nào? ",
            "language": "vi",
            "segments": [
                {"text": " Miu ơi,", "avg_logprob": -0.1, "end": 0.8},
                {"text": " con voi kêu thế nào?", "avg_logprob": -0.3, "end": 2.1},
            ],
        }

    mod = types.ModuleType("mlx_whisper")
    mod.transcribe = transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", mod)
    return calls


async def test_transcribe_joins_segments_and_passes_options(fake_mlx, wav_bytes):
    stt = MlxWhisperSTT("mlx-community/whisper-small-mlx", initial_prompt="Miu ơi")
    t = await stt.transcribe(wav_bytes, "audio/wav")
    assert t.text == "Miu ơi, con voi kêu thế nào?"
    assert t.language == "vi" and t.duration_s == 2.1 and 0.7 < t.confidence < 1
    pcm, kw = fake_mlx[0]
    assert pcm.dtype.name == "float32" and 7000 < pcm.size < 9000  # 0.5 s fixture at 16 kHz
    assert kw["path_or_hf_repo"] == "mlx-community/whisper-small-mlx"
    assert kw["language"] == "vi" and kw["initial_prompt"] == "Miu ơi"


async def test_empty_audio_short_circuits(fake_mlx, monkeypatch):
    import app.providers.stt_mlx_whisper as mod
    import numpy as np

    monkeypatch.setattr(mod, "decode_to_pcm16k", lambda b: np.zeros(0, dtype=np.float32))
    t = await MlxWhisperSTT().transcribe(b"", "audio/webm")
    assert t.text == "" and fake_mlx == []


def test_config_selects_mlx_provider(monkeypatch):
    from app.config import Settings
    from app.deps import build_stt

    monkeypatch.setitem(sys.modules, "mlx_whisper", types.ModuleType("mlx_whisper"))
    stt = build_stt(Settings(stt_provider="mlx_whisper", mlx_whisper_model="mlx-community/whisper-large-v3-turbo", _env_file=None))
    assert isinstance(stt, MlxWhisperSTT) and stt._repo == "mlx-community/whisper-large-v3-turbo"
