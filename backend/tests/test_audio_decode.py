import numpy as np

from app.providers.audio_decode import decode_to_pcm16k
from tests.conftest import make_wav


def test_wav_decodes_to_16k_mono_float32():
    pcm = decode_to_pcm16k(make_wav(seconds=1.0, rate=16000))
    assert pcm.dtype == np.float32 and abs(pcm.size - 16000) < 50
    assert 0.05 < np.abs(pcm).max() <= 1.0


def test_resamples_other_rates():
    pcm = decode_to_pcm16k(make_wav(seconds=0.5, rate=44100))
    assert abs(pcm.size - 8000) < 100
