from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from config import AppConfig
from logging_utils import correlation_id_middleware, setup_logging
from models import OperatorConfigInput
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

    @app.get("/ui/bootstrap")
    async def ui_bootstrap():
        return node_service.ui_bootstrap()

    @app.get("/ui/config")
    async def ui_config():
        return node_service.operator_config_response()

    @app.put("/ui/config")
    async def update_ui_config(payload: OperatorConfigInput):
        try:
            return await node_service.update_operator_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/onboarding/start")
    async def start_ui_onboarding():
        try:
            return await node_service.start_onboarding(force=node_service.state.onboarding_status != "pending")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
