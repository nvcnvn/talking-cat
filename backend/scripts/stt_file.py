#!/usr/bin/env python3
"""Transcribe local audio files with a chosen STT provider, without the HTTP server.

  python scripts/stt_file.py clip1.mp3 clip2.wav              # provider from .env / STT_PROVIDER
  STT_PROVIDER=mlx_whisper python scripts/stt_file.py clip.mp3  # Mac (or Linux with mlx[cpu], slow)

Prints text, confidence and wall time per file, so STT engines/models can be compared
on the same prerecorded clips in both environments.
"""
from __future__ import annotations

import asyncio
import mimetypes
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.deps import build_stt  # noqa: E402


async def main(paths: list[str]) -> int:
    s = load_settings()
    stt = build_stt(s)
    print(f"provider={s.stt_provider} model={s.mlx_whisper_model if s.stt_provider == 'mlx_whisper' else s.whisper_model}")
    warm = getattr(stt, "warmup", None)
    if warm:
        t = time.perf_counter()
        await asyncio.to_thread(warm)
        print(f"warmup: {time.perf_counter() - t:.1f}s")
    for p in paths:
        path = pathlib.Path(p)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        t = time.perf_counter()
        tr = await stt.transcribe(path.read_bytes(), mime, language=s.whisper_language)
        conf = f"{tr.confidence:.2f}" if tr.confidence is not None else "-"
        print(f"{path.name}: {time.perf_counter() - t:.1f}s conf={conf} -> {tr.text}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1:])))
