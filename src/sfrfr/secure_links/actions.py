"""Действия Sprint 2: consent + view_pdf по secure action link."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sfrfr.core.config import Settings, get_settings
from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION, CaseRepository
from sfrfr.db.session import get_supabase_client
from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.secure_links.service import SecureActionLinkService, StoredSecureLink
from sfrfr.secure_links.urls import public_secure_action_url, public_secure_pdf_url
from sfrfr.services.contact_policy import looks_like_bot_user_agent

logger = logging.getLogger(__name__)

# Синтетический actor для audit (не JWT пользователя)
SECURE_LINK_ACTOR_ID = "00000000-0000-4000-8000-0000000000c1"

CONSENT_TTL_HOURS = 72
VIEW_PDF_TTL_HOURS = 72
VIEW_PDF_MAX_USES = 5
CONSENT_MAX_USES = 1

PDN_URL = "https://proverkastaza.ru/politika-pdn/"
CONSENT_URL = "https://proverkastaza.ru/soglasie/"
OFFER_URL = "https://proverkastaza.ru/oferta/"


def _flags(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


def require_links_enabled(settings: Settings | None = None) -> None:
    if not _flags(settings).secure_action_links_enabled:
        raise SecureLinksDisabled()


def require_result_view_enabled(settings: Settings | None = None) -> None:
    require_links_enabled(settings)
    if not _flags(settings).secure_result_view_enabled:
        raise SecureLinksDisabled("secure_result_view_disabled")


def issue_consent_link(
    *,
    case_id: str,
    max_user_id: str | None = None,
    issued_via: str = "system",
    actor: str | None = None,
    service: SecureActionLinkService | None = None,
) -> dict[str, Any]:
    """Создать purpose=consent; возвращает url + prefix (без логирования raw)."""
    require_links_enabled()
    svc = service or SecureActionLinkService()
    issued = svc.create(
        case_id=case_id,
        purpose="consent",
        ttl_hours=CONSENT_TTL_HOURS,
        max_uses=CONSENT_MAX_USES,
        max_user_id=max_user_id,
        issued_via=issued_via,
        actor=actor,
        meta={"sprint": 2},
    )
    return {
        "link_id": issued.id,
        "purpose": issued.purpose,
        "token_prefix": issued.token_prefix,
        "expires_at": issued.expires_at.isoformat(),
        "url": public_secure_action_url(issued.raw_token),
        "raw_token_once": issued.raw_token,
    }


def issue_view_pdf_link(
    *,
    case_id: str,
    document_id: str | None = None,
    diagnostic_result_id: str | None = None,
    max_user_id: str | None = None,
    issued_via: str = "system",
    actor: str | None = None,
    service: SecureActionLinkService | None = None,
) -> dict[str, Any]:
    """purpose=view_pdf; resource = document или diagnostic_result."""
    require_result_view_enabled()
    resource_id: str | None = None
    resource_type: str | None = None
    if document_id:
        resource_id = document_id
        resource_type = "document"
    elif diagnostic_result_id:
        resource_id = diagnostic_result_id
        resource_type = "diagnostic_result"
    else:
        raise SecureLinkDenied("missing_resource")

    svc = service or SecureActionLinkService()
    issued = svc.create(
        case_id=case_id,
        purpose="view_pdf",
        ttl_hours=VIEW_PDF_TTL_HOURS,
        max_uses=VIEW_PDF_MAX_USES,
        resource_id=resource_id,
        resource_type=resource_type,
        max_user_id=max_user_id,
        issued_via=issued_via,
        actor=actor,
        meta={"sprint": 2},
    )
    return {
        "link_id": issued.id,
        "purpose": issued.purpose,
        "token_prefix": issued.token_prefix,
        "expires_at": issued.expires_at.isoformat(),
        "url": public_secure_action_url(issued.raw_token),
        "pdf_url": public_secure_pdf_url(issued.raw_token),
        "raw_token_once": issued.raw_token,
    }


def load_context(raw_token: str, *, user_agent: str | None = None) -> dict[str, Any]:
    """Контекст страницы без case_id / ПДн."""
    require_links_enabled()
    svc = SecureActionLinkService()
    link = svc.verify(raw_token, consume=False, actor="client_open")
    if link.purpose == "view_pdf":
        require_result_view_enabled()

    already_consent = False
    if link.purpose == "consent":
        already_consent = CaseRepository().has_consent(link.case_id)

    return {
        "ok": True,
        "purpose": link.purpose,
        "status": link.status,
        "expires_at": link.expires_at.isoformat(),
        "uses_left": max(0, link.max_uses - link.use_count),
        "consent_already": already_consent,
        "consent_version": CURRENT_CONSENT_VERSION,
        "links": {
            "pdn": PDN_URL,
            "consent": CONSENT_URL,
            "offer": OFFER_URL,
        },
        "title": _title_for(link.purpose),
        "hint": _hint_for(link.purpose),
        "bot_ua": looks_like_bot_user_agent(user_agent or ""),
    }


def grant_consent_via_token(
    raw_token: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_links_enabled()
    svc = SecureActionLinkService()
    link = svc.verify(raw_token, purpose="consent", consume=False, actor="client_consent")
    repo = CaseRepository()
    if not repo.has_consent(link.case_id):
        repo.accept_consent(
            link.case_id,
            version=CURRENT_CONSENT_VERSION,
            actor_id=SECURE_LINK_ACTOR_ID,
            ip=ip,
            user_agent=user_agent,
        )
    consumed = svc.verify(raw_token, purpose="consent", consume=True, actor="client_consent")
    return {
        "ok": True,
        "purpose": "consent",
        "status": consumed.status,
        "message": (
            "Согласие принято. Документы в чат не отправляйте — "
            "когда понадобится передача, пришлём защищённую ссылку."
        ),
    }


def resolve_pdf_signed_url(
    raw_token: str,
    *,
    user_agent: str | None = None,
    signed_ttl_seconds: int = 300,
) -> dict[str, Any]:
    """Проверка view_pdf → signed URL. Prefetch/боты не consume."""
    require_result_view_enabled()
    if looks_like_bot_user_agent(user_agent or ""):
        return {"bot_skipped": True}

    svc = SecureActionLinkService()
    link = svc.verify(raw_token, purpose="view_pdf", consume=False, actor="client_pdf")
    document_id = _document_id_for_link(link)
    if not document_id:
        raise SecureLinkDenied("document_missing")

    row = (
        get_supabase_client()
        .table("documents")
        .select("storage_path")
        .eq("id", document_id)
        .eq("case_id", link.case_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not row:
        raise SecureLinkDenied("document_missing")

    from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

    signed = (
        get_supabase_client()
        .storage.from_(PRIVATE_STORAGE_BUCKET)
        .create_signed_url(row[0]["storage_path"], signed_ttl_seconds)
    )
    url = signed.get("signedURL") or signed.get("signedUrl")
    if not url:
        raise SecureLinkDenied("signed_url_failed")

    svc.verify(raw_token, purpose="view_pdf", consume=True, actor="client_pdf")
    try:
        CaseRepository().audit(link.case_id, None, "secure_view_pdf")
    except Exception as exc:  # noqa: BLE001
        logger.info("secure view_pdf audit skipped: %s", exc)

    return {"url": str(url), "expires_in": signed_ttl_seconds, "bot_skipped": False}


def _document_id_for_link(link: StoredSecureLink) -> str | None:
    if link.resource_type == "document" and link.resource_id:
        return link.resource_id
    if link.resource_type == "diagnostic_result" and link.resource_id:
        rows = (
            get_supabase_client()
            .table("diagnostic_results")
            .select("document_id, case_id, status")
            .eq("id", link.resource_id)
            .eq("case_id", link.case_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        if str(rows[0].get("status") or "") not in ("published", "reviewed"):
            # reviewed тоже ок для staff-issued preview; published — основной
            if str(rows[0].get("status") or "") != "published":
                return None
        doc = rows[0].get("document_id")
        return str(doc) if doc else None
    return None


def _title_for(purpose: str) -> str:
    if purpose == "consent":
        return "Согласие на обработку документов"
    if purpose == "view_pdf":
        return "Результат диагностики"
    return "Защищённое действие"


def _hint_for(purpose: str) -> str:
    if purpose == "consent":
        return (
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
            "Решение принимает СФР. Сканы в чат не отправляйте."
        )
    if purpose == "view_pdf":
        return (
            "Документ доступен по защищённой ссылке. Не пересылайте его в открытые чаты. "
            "Решение о пенсии принимает СФР."
        )
    return "Одно действие. Регистрация не нужна."


def is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False
