"""App factory. `create_app(settings, service)` lets tests inject everything."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import Settings, load_settings
from .core.pipeline import ConversationService
from .deps import build_service


def create_app(settings: Settings | None = None, service: ConversationService | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.service = service or build_service(settings)
        import asyncio

        for provider in (app.state.service.stt, app.state.service.tts):
            warm = getattr(provider, "warmup", None)
            if warm:
                await asyncio.to_thread(warm)
        yield
        close = getattr(app.state.service.llm, "aclose", None)
        if close:
            await close()

    app = FastAPI(title="Talking Cat API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
