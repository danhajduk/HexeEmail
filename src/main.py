from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import AppConfig
from logging_utils import correlation_id_middleware, setup_logging
from service import NodeService


def create_app(
    config: AppConfig | None = None,
    *,
    service: NodeService | None = None,
) -> FastAPI:
    setup_logging()
    app_config = config or AppConfig()
    node_service = service or NodeService(app_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = node_service
        await node_service.start()
        try:
            yield
        finally:
            await node_service.stop()

    app = FastAPI(title="Synthia Email Node", lifespan=lifespan)
    app.middleware("http")(correlation_id_middleware)

    @app.get("/health/live")
    async def health_live():
        return {"live": True, "version": node_service.health_snapshot()["version"]}

    @app.get("/health/ready")
    async def health_ready():
        return node_service.health_snapshot()

    @app.get("/onboarding/status")
    async def onboarding_status():
        return node_service.onboarding_status()

    @app.get("/status")
    async def status():
        return node_service.status()

    return app
