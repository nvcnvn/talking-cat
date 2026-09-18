#!/usr/bin/env python3
"""Send a prerecorded audio file through a running backend and play/save the reply.

Usage:
  python scripts/talk_file.py path/to/clip.wav [--url http://localhost:8000] [--session abc] [--age 7-12] [--out reply.mp3]

With STT_PROVIDER=fake on the server you can also pass a text file whose first line is
"#transcript: <words>" to control what the cat "hears".
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import pathlib
import sys
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("audio")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--session", default="cli")
    p.add_argument("--age", default="3-6", choices=["3-6", "7-12"])
    p.add_argument("--out", default=None, help="write reply audio here")
    p.add_argument("--no-audio", action="store_true")
    a = p.parse_args()

    path = pathlib.Path(a.audio)
    data = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    boundary = "----talkingcat"
    fields = {"session_id": a.session, "age_group": a.age, "want_audio": "false" if a.no_audio else "true"}
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
    body += data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(f"{a.url}/api/talk", data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        out = json.load(resp)

    print("heard :", out["transcript"]["text"])
    print("reply :", out["reply"]["text"], "(blocked)" if out["reply"]["blocked"] else "")
    print("timing:", out["timings_ms"])
    if out.get("audio"):
        ext = ".mp3" if out["audio"]["mime"] == "audio/mpeg" else ".wav"
        dest = pathlib.Path(a.out or f"reply{ext}")
        dest.write_bytes(base64.b64decode(out["audio"]["base64"]))
        print("audio :", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
