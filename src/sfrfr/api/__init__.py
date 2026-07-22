from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sfrfr.api.routes import cases, documents, health, max_webhook
from sfrfr.core.config import get_settings

# Мини-приложение MAX на витрине (отдельный origin от API)
_CORS_ORIGINS = (
    "https://taxi-doroga-dobra.ru",
    "https://www.taxi-doroga-dobra.ru",
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
