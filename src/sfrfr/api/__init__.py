from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sfrfr.api.routes import (
    admin_portal,
    cases,
    documents,
    email_webhooks,
    health,
    max_webhook,
    payments,
    portal,
    public_leads,
    public_review_draft,
    public_site_reviews,
    public_staff_register,
    secure_actions,
    supabase_auth_email,
)
from sfrfr.core.config import get_settings
from sfrfr.ops.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(app_env=settings.app_env, debug=settings.app_debug)
    is_production = settings.app_env.strip().lower() == "production"
    cors_origins = [
        origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
    ]
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, tags=["health"])
    if not is_production:
        # Старый демонстрационный API хранит дела локально и не имеет авторизации.
        app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
        app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(portal.router, prefix="/api/portal", tags=["portal"])
    app.include_router(admin_portal.router, prefix="/api/portal", tags=["portal-admin"])
    app.include_router(secure_actions.router, prefix="/api/portal", tags=["secure-actions"])
    app.include_router(
        public_leads.router,
        prefix="/api/public",
        tags=["public"],
    )
    app.include_router(
        public_review_draft.router,
        prefix="/api/public",
        tags=["public-review"],
    )
    app.include_router(
        public_site_reviews.router,
        prefix="/api/public",
        tags=["public-reviews"],
    )
    app.include_router(
        public_staff_register.router,
        prefix="/api/public",
        tags=["public-staff"],
    )
    app.include_router(
        max_webhook.router,
        prefix="/api/integrations/max",
        tags=["max"],
    )
    app.include_router(
        supabase_auth_email.router,
        prefix="/api/integrations/supabase",
        tags=["supabase-auth"],
    )
    app.include_router(
        payments.public_router,
        prefix="/api/public",
        tags=["public-pay"],
    )
    app.include_router(
        payments.webhook_router,
        prefix="/api/integrations/payments",
        tags=["payments"],
    )
    app.include_router(
        email_webhooks.router,
        prefix="/api/webhooks",
        tags=["email-webhooks"],
    )
    app.include_router(
        payments.router,
        prefix="/api/portal",
        tags=["portal-payments"],
    )
    return app


app = create_app()
