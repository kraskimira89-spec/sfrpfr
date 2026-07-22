from fastapi import FastAPI

from sfrfr.api.routes import cases, documents, health, max_webhook
from sfrfr.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(health.router, tags=["health"])
    app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(
        max_webhook.router,
        prefix="/api/integrations/max",
        tags=["max"],
    )
    return app


app = create_app()
