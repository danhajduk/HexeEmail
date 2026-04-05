from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.capabilities import build_capabilities_router
from api.routes.governance import build_governance_router
from api.routes.node import build_node_router
from api.routes.providers_gmail import build_providers_gmail_router
from api.routes.runtime import build_runtime_router
from config import AppConfig
from email_node.api.patterns import build_pattern_router
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

    app = FastAPI(title="Hexe Email Node", lifespan=lifespan)
    app.middleware("http")(correlation_id_middleware)
    app.include_router(build_node_router(node_service))
    app.include_router(build_capabilities_router(node_service))
    app.include_router(build_runtime_router(node_service))
    app.include_router(build_governance_router(node_service))
    app.include_router(build_providers_gmail_router(node_service))
    app.include_router(build_pattern_router(node_service))

    return app
