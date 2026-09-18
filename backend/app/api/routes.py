"""HTTP surface. One endpoint per stage plus /talk for the whole turn.

Handlers are thin: parse, call the service, serialise. Nothing else lives here.
"""
from __future__ import annotations

import base64
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from ..core.models import TalkResult
from ..core.pipeline import ConversationService
from .schemas import AgeGroup, AudioOut, ChatIn, ChatOut, HealthOut, ReplyOut, TalkOut, TranscriptOut, TTSIn

router = APIRouter(prefix="/api")


def _svc(request: Request) -> ConversationService:
    return request.app.state.service


def _to_talk_out(r: TalkResult) -> TalkOut:
    return TalkOut(
        session_id=r.session_id,
        transcript=TranscriptOut(**r.transcript.__dict__),
        reply=ReplyOut(**r.reply.__dict__),
        audio=AudioOut(mime=r.audio.mime, base64=base64.b64encode(r.audio.data).decode()) if r.audio else None,
        timings_ms=r.timings_ms,
    )


async def _read_upload(request: Request, audio: UploadFile) -> tuple[bytes, str]:
    data = await audio.read()
    limit = request.app.state.settings.max_upload_bytes
    if len(data) > limit:
        raise HTTPException(413, f"audio larger than {limit} bytes")
    if not data:
        raise HTTPException(400, "empty audio")
    return data, audio.content_type or "application/octet-stream"


@router.get("/health", response_model=HealthOut)
async def health(request: Request) -> HealthOut:
    s = request.app.state.settings
    return HealthOut(status="ok", providers={"stt": s.stt_provider, "llm": s.llm_provider, "tts": s.tts_provider})


@router.post("/stt", response_model=TranscriptOut)
async def stt(request: Request, audio: UploadFile = File(...)) -> TranscriptOut:
    data, mime = await _read_upload(request, audio)
    t = await _svc(request).transcribe(data, mime)
    return TranscriptOut(**t.__dict__)


@router.post("/chat", response_model=ChatOut)
async def chat(request: Request, body: ChatIn) -> ChatOut:
    reply = await _svc(request).reply(body.session_id, body.text, body.age_group)
    return ChatOut(session_id=body.session_id, reply=ReplyOut(**reply.__dict__))


@router.post("/tts")
async def tts(request: Request, body: TTSIn) -> Response:
    clip = await _svc(request).speak(body.text)
    return Response(content=clip.data, media_type=clip.mime)


@router.post("/talk", response_model=TalkOut)
async def talk(
    request: Request,
    audio: UploadFile = File(...),
    session_id: str = Form(""),
    age_group: AgeGroup = Form("3-6"),
    want_audio: bool = Form(True),
) -> TalkOut:
    data, mime = await _read_upload(request, audio)
    sid = session_id or uuid.uuid4().hex
    result = await _svc(request).talk(sid, data, mime, age_group, want_audio)
    return _to_talk_out(result)


@router.delete("/session/{session_id}", status_code=204)
async def clear_session(request: Request, session_id: str) -> Response:
    _svc(request).sessions.clear(session_id)
    return Response(status_code=204)
