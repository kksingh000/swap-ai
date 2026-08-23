"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    callbacks,
    calls,
    config as config_routes,
    dashboard,
    leads,
    telephony,
    training,
    whatsapp,
    ws,
)
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import Base, engine, session_scope
from app.services.classification.ml_classifier import get_classifier
from app.services.llm.factory import get_llm
from app.services.scheduling.scheduler import rehydrate_jobs, shutdown_scheduler, start_scheduler

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F401 - registers models before create_all

    Base.metadata.create_all(bind=engine)

    db = session_scope()
    try:
        from app.services.config_service import get_config

        get_config(db)  # seeds the store profile on first boot
    finally:
        db.close()

    llm = get_llm()
    log.info("LLM provider: %s (available=%s)", llm.name, llm.available)
    log.info("Lead classifier: %s", "loaded" if get_classifier().loaded else "not trained yet")

    start_scheduler()
    rehydrate_jobs()
    log.info("%s ready at %s", settings.APP_NAME, settings.PUBLIC_BASE_URL)

    yield

    shutdown_scheduler()
    await llm.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "AI voice sales agent for a thrift/swap store. Understands English, Hindi and "
        "Hinglish, scores leads in real time, and triggers WhatsApp + callbacks mid-call."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    calls.router,
    leads.router,
    whatsapp.router,
    callbacks.router,
    dashboard.router,
    config_routes.router,
    training.router,
    telephony.router,
):
    app.include_router(router, prefix=settings.API_PREFIX)

app.include_router(ws.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/dashboard/health",
        "websocket": f"{settings.API_PREFIX}/ws",
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": request.url.path},
    )
