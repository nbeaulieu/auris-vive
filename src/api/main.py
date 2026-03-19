"""
API entry point — SDD-006 (pending)

FastAPI application factory.  The app is constructed in create_app() rather
than at module level so tests can instantiate it without side effects.

Open questions (SDD-006)
------------------------
    Q-API-1  Authentication model — API key (simple, stateless) vs OAuth2
             (required for Spotify/Apple Music embed).  Blocks all route
             implementations.
    Q-API-2  Job result storage — in-memory dict (dev only) vs Redis vs
             Postgres.  Affects job_queue.py design.
    Q-API-3  WebSocket protocol — do clients subscribe per job_id, or is
             there a broadcast channel?
"""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routes import jobs, health


def create_app() -> FastAPI:
    app = FastAPI(
        title="Auris Vive",
        description="Real-time music intelligence API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.include_router(health.router)
    app.include_router(jobs.router, prefix="/jobs")

    return app


# Uvicorn entry point: uvicorn src.api.main:app
app = create_app()
