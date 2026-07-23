from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sfrfr.api.routes import admin_portal, cases, documents, health, max_webhook, portal
from sfrfr.core.config import get_settings
from sfrfr.ops.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(app_env=settings.app_env, debug=settings.app_debug)
    cors_origins = [
        origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
    ]
    # docs/redoc/openapi — публичны для разработчика; service_role в браузер не нужен (ТЗ-05).
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(portal.router, prefix="/api/portal", tags=["portal"])
    app.include_router(admin_portal.router, prefix="/api/portal", tags=["portal-admin"])
    app.include_router(
        max_webhook.router,
        prefix="/api/integrations/max",
        tags=["max"],
    )
    return app


app = create_app()
