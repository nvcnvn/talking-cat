"""Decode any browser/file audio (webm/opus, mp4, mp3, wav, ogg) to 16 kHz mono float32 PCM.

Uses PyAV, which bundles its own ffmpeg libraries, so no system ffmpeg is required on
either Linux or macOS. Whisper models take exactly this array format.
"""
from __future__ import annotations

import io

import numpy as np

TARGET_RATE = 16000


def decode_to_pcm16k(data: bytes) -> np.ndarray:
    import av

    with av.open(io.BytesIO(data)) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=TARGET_RATE)
        chunks: list[np.ndarray] = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32, copy=False)
