"""Защищённые API для client и admin кабинетов."""

from __future__ import annotations

import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse

from sfrfr.api.schemas.portal import (
    CabinetRegisterRequest,
    CabinetRegisterResponse,
    CaseMessageCreate,
    CaseSummary,
    ClientCaseDetail,
    ConsentAcceptRequest,
    ContractAcceptRequest,
    CreateCaseRequest,
    FindingItem,
    LinkMaxRequest,
    LinkWebFromMaxRequest,
    LinkWebFromMaxResponse,
    MaxOtpLinkRequest,
    MaxOtpPollResponse,
    MaxOtpRequest,
    MaxOtpRequestResponse,
    MaxOtpVerifyRequest,
    MaxOtpVerifyResponse,
    PipelineRunResponse,
    PortalMeResponse,
    PortalSiteReviewRequest,
    PortalSiteReviewResponse,
    PreferencesUpdateRequest,
    PreferredChannel,
    SignedDocumentResponse,
)
from sfrfr.core.config import get_settings
from sfrfr.core.copy import SUBMISSION_INSTRUCTION, WARNING
from sfrfr.core.success_fee import calc_success_fee
from sfrfr.db.case_repository import CaseRepository
from sfrfr.db.client_channels import ClientChannelRepository
from sfrfr.db.session import get_supabase_client
from sfrfr.models.case_status import STATUS_HINTS_RU, STATUS_LABELS_RU, CaseStatus, status_label_ru
from sfrfr.ops.auth_log import auth_event
from sfrfr.security.auth import Principal, get_current_principal, staff_role_capabilities
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET, SIGNED_URL_TTL_SECONDS
from sfrfr.security.max_webapp import extract_max_user_id, verify_max_init_data
from sfrfr.services.client_work_map import build_client_work_map

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_SUBMISSION_INSTRUCTION = (
    f"{SUBMISSION_INSTRUCTION} Используйте проект обращения и чек-лист как подсказку."
)

_SFR_WARNING = WARNING


def _repo() -> CaseRepository:
    return CaseRepository()


def _summary(case: dict, *, unread: int = 0, consent_accepted: bool = False) -> CaseSummary:
    checklist = case.get("checklist_items") or []
    work = build_client_work_map(
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        consent_accepted=consent_accepted,
        documents=list(case.get("documents") or []),
        checklist_items=list(checklist),
        orders=list(case.get("orders") or []),
    )
    return CaseSummary(
        id=str(case["id"]),
        pipeline_status=case["pipeline_status"],
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        expert_user_id=str(case["expert_user_id"]) if case.get("expert_user_id") else None,
        expert_assigned=bool(case.get("expert_user_id")),
        checklist_open_count=sum(1 for item in checklist if item.get("status") != "done"),
        next_action=work.get("now_need") or CaseRepository.next_client_action(case),
        unread_messages=unread,
        consent_accepted=consent_accepted,
        status_label=work.get("status_label"),
    )


def _client_detail(case: dict, *, consent_accepted: bool, draft: dict | None) -> ClientCaseDetail:
    repo = _repo()
    case_id = str(case["id"])
    status_raw = case.get("pipeline_status") or "intake"
    try:
        status_enum = CaseStatus(str(status_raw))
        label = STATUS_LABELS_RU.get(status_enum, str(status_raw))
        hint = STATUS_HINTS_RU.get(status_enum)
    except ValueError:
        label = status_label_ru(status_raw)
        hint = None
    documents = _client_documents(list(case.get("documents") or []))
    orders: list[Any] = []
    try:
        orders = list(repo.list_orders(case_id) or [])
    except Exception as exc:  # noqa: BLE001
        logger.info("client orders skipped: %s", exc)
    work = build_client_work_map(
        pipeline_status=str(status_raw),
        b2c_status=str(case.get("b2c_status") or ""),
        consent_accepted=consent_accepted,
        documents=documents,
        checklist_items=list(case.get("checklist_items") or []),
        orders=orders,
    )
    return ClientCaseDetail(
        id=case_id,
        pipeline_status=status_raw,
        b2c_status=case["b2c_status"],
        created_at=case.get("created_at"),
        expert_assigned=bool(case.get("expert_user_id")),
        consent_accepted=consent_accepted,
        checklist_items=list(case.get("checklist_items") or []),
        required_documents=CaseRepository.required_document_items(case),
        documents=documents,
        findings=[],
        draft=draft,
        next_action=work.get("now_need") or CaseRepository.next_client_action(case),
        status_label=work.get("status_label") or label,
        status_hint=work.get("status_hint") or hint,
        pipeline_error=None,
        submission_instruction=_SUBMISSION_INSTRUCTION,
        warning=_SFR_WARNING,
        work=work,
    )


def _require_consent_for_upload(repo: CaseRepository, case_id: str) -> None:
    if get_settings().require_consent and not repo.has_consent(case_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="consent required before document upload",
        )


_DOC_TYPE_LABELS_RU = {
    "sfr_decision": "Решение СФР",
    "ils": "Выписка ИЛС",
    "workbook": "Трудовая книжка",
    "payment_receipt": "Чек оплаты",
    "diagnosis_report": "Результат диагностики",
}


def _document_filename(storage_path: str | None) -> str:
    if not storage_path:
        return "документ"
    name = Path(str(storage_path)).name.strip()
    return name or "документ"


def _with_download_param(url: str, filename: str) -> str:
    """Браузер скачивает файл, а не открывает превью."""
    name = quote(filename or "document", safe=".-_")
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}download={name}"


_DATE_IN_DOC_RE = re.compile(
    r"(?:от\s+)?(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE,
)


def _normalize_doc_date(raw: str) -> str:
    parts = re.split(r"[./]", (raw or "").strip())
    if len(parts) != 3:
        return (raw or "").strip()
    day, month, year = parts
    if len(year) == 2:
        year = f"20{year}"
    try:
        d, m, y = int(day), int(month), int(year)
        if not (1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2100):
            return (raw or "").strip()
        return f"{d:02d}.{m:02d}.{y}"
    except ValueError:
        return (raw or "").strip()


def _title_from_preview(preview: str, *, filename: str, type_label: str | None) -> str:
    if type_label:
        return type_label
    text = " ".join((preview or "").split())
    lowered = text.lower()
    if (
        "сзи-илс" in lowered
        or "индивидуального лицевого счёта" in lowered
        or "индивидуального лицевого счета" in lowered
        or re.search(r"\bилс\b", lowered)
    ):
        return "Выписка ИЛС"
    if "трудов" in lowered:
        return "Трудовая книжка"
    if "решени" in lowered and "сфр" in lowered:
        return "Решение СФР"
    first = text.split(".")[0].strip() if text else ""
    if 4 <= len(first) <= 80:
        return first
    stem = Path(filename or "").stem.replace("_", " ").strip()
    return stem or "Документ"


def _meta_from_preview(
    preview: str,
    *,
    filename: str,
    type_label: str | None,
) -> tuple[str | None, str]:
    """Дата внутри документа + название из текста/типа."""
    cleaned = _sanitize_content_preview(preview or "", limit=2000)
    match = _DATE_IN_DOC_RE.search(cleaned)
    inner_date = _normalize_doc_date(match.group(1)) if match else None
    inner_title = _title_from_preview(cleaned, filename=filename, type_label=type_label)
    return inner_date, inner_title


def _document_type_label(doc_type: str | None) -> str | None:
    if not doc_type:
        return None
    key = str(doc_type).strip().lower()
    return _DOC_TYPE_LABELS_RU.get(key, key)


def _sanitize_content_preview(text: str, *, limit: int = 280) -> str:
    cleaned = " ".join((text or "").split())
    if cleaned.startswith("[ocr_"):
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _extract_upload_preview(data: bytes, filename: str) -> str:
    """Короткий фрагмент текста сразу после загрузки (без полного пайплайна)."""
    suffix = Path(filename or "document.bin").suffix.lower() or ".bin"
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        return ""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        from sfrfr.ocr import extract_text

        raw = extract_text(tmp_path)
        return _sanitize_content_preview(raw)
    except Exception as exc:  # noqa: BLE001
        logger.info("document preview extract skipped: %s", exc)
        return ""
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _client_document(item: dict[str, Any]) -> dict[str, Any]:
    storage_path = str(item.get("storage_path") or "")
    filename = _document_filename(storage_path)
    type_label = _document_type_label(str(item["doc_type"]) if item.get("doc_type") else None)
    preview = _sanitize_content_preview(str(item.get("content_preview") or ""))
    inner_date, inner_title = _meta_from_preview(
        preview,
        filename=filename,
        type_label=type_label,
    )
    return {
        "id": item.get("id"),
        "storage_path": storage_path,
        "doc_type": item.get("doc_type"),
        "doc_type_label": type_label,
        "created_at": item.get("created_at"),
        "filename": filename,
        "content_preview": preview or None,
        "inner_date": inner_date,
        "inner_title": inner_title,
    }


def _client_documents(raw_docs: list[Any] | None) -> list[dict[str, Any]]:
    """Безопасное представление документов для клиента (+ краткое содержание)."""
    out: list[dict[str, Any]] = []
    for item in raw_docs or []:
        if not isinstance(item, dict):
            continue
        out.append(_client_document(item))
    out.sort(key=lambda d: str(d.get("created_at") or ""), reverse=True)
    return out


def _channel_repo() -> ClientChannelRepository:
    return ClientChannelRepository()


def _resolve_max_user_id(
    *,
    max_user_id: str | None,
    init_data: str | None,
    require_verified: bool,
    link_token: str | None = None,
) -> str:
    from sfrfr.security.max_link_token import verify_max_link_token

    if link_token:
        token_uid = verify_max_link_token(link_token)
        if not token_uid:
            raise HTTPException(status_code=401, detail="invalid or expired link_token")
        if max_user_id and max_user_id != token_uid:
            raise HTTPException(status_code=400, detail="max_user_id does not match link_token")
        return token_uid

    settings = get_settings()
    resolved = extract_max_user_id(init_data, fallback=max_user_id)
    if not resolved:
        raise HTTPException(status_code=400, detail="max_user_id or init_data required")
    if init_data and settings.max_bot_token:
        ok = verify_max_init_data(init_data, settings.max_bot_token)
        if not ok and (require_verified or settings.app_env == "production"):
            raise HTTPException(status_code=401, detail="invalid MAX init_data signature")
    elif require_verified and settings.app_env == "production" and not init_data:
        raise HTTPException(
            status_code=400,
            detail="init_data or link_token required in production",
        )
    return resolved


def _ensure_client_row(principal: Principal) -> dict:
    repo = _channel_repo()
    if principal.max_user_id:
        row = repo.ensure_for_max_user(principal.max_user_id)
        if principal.email and not principal.is_max_only and not row.get("user_id"):
            row = repo.link_max_to_user(
                user_id=principal.user_id,
                max_user_id=principal.max_user_id,
                email=principal.email,
            )
        return row
    return repo.ensure_for_auth_user(
        principal.user_id,
        email=principal.email,
        phone=principal.phone,
    )


def _me_response(principal: Principal, row: dict) -> PortalMeResponse:
    settings = get_settings()
    channel = row.get("preferred_channel") or PreferredChannel.UNSET.value
    try:
        preferred = PreferredChannel(channel)
    except ValueError:
        preferred = PreferredChannel.UNSET
    return PortalMeResponse(
        user_id=principal.user_id,
        email=principal.email or row.get("email"),
        client_id=str(row["id"]),
        full_name=row.get("full_name"),
        role=principal.role.value if principal.role else None,
        is_staff=principal.is_staff,
        preferred_channel=preferred,
        preferred_channel_set_at=row.get("preferred_channel_set_at"),
        max_linked=bool(row.get("max_user_id")),
        web_linked=bool(row.get("user_id")),
        max_user_id=str(row["max_user_id"]) if row.get("max_user_id") else None,
        cabinet_url=settings.cabinet_public_url.rstrip("/"),
        max_bot_url=settings.max_chat_url,
        max_miniapp_url=settings.max_miniapp_url,
    )


@router.get("/me", response_model=PortalMeResponse)
def get_me(principal: Principal = Depends(get_current_principal)) -> PortalMeResponse:
    """Профиль: клиент (канал/связка) или сотрудник (роль)."""
    if principal.is_staff:
        settings = get_settings()
        return PortalMeResponse(
            user_id=principal.user_id,
            email=principal.email,
            role=principal.role.value if principal.role else None,
            is_staff=True,
            preferred_channel=PreferredChannel.UNSET,
            max_linked=False,
            web_linked=True,
            cabinet_url=settings.cabinet_public_url.rstrip("/"),
            max_bot_url=settings.max_chat_url,
            max_miniapp_url=settings.max_miniapp_url,
            role_capabilities=staff_role_capabilities(principal.role),
        )
    row = _ensure_client_row(principal)
    return _me_response(principal, row)


@router.patch("/me/preferences", response_model=PortalMeResponse)
def patch_preferences(
    payload: PreferencesUpdateRequest,
    principal: Principal = Depends(get_current_principal),
) -> PortalMeResponse:
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client only")
    repo = _channel_repo()
    row = _ensure_client_row(principal)
    updated = repo.set_preferred_channel(str(row["id"]), payload.preferred_channel.value)
    action = f"preferred_channel:{payload.preferred_channel.value}"
    if principal.max_user_id:
        action = f"{action}:max:{principal.max_user_id}"
    repo.audit(principal.audit_actor_id(), action)
    return _me_response(principal, updated)


@router.post("/me/site-review", response_model=PortalSiteReviewResponse)
def submit_client_site_review(
    payload: PortalSiteReviewRequest,
    principal: Principal = Depends(get_current_principal),
) -> PortalSiteReviewResponse:
    """Отзыв из личного кабинета: подпись из профиля, client_id в очереди."""
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client only")
    if not payload.consent:
        raise HTTPException(status_code=400, detail="consent_required")
    row = _ensure_client_row(principal)
    from sfrfr.api.routes.public_site_reviews import notify_site_review_queued
    from sfrfr.core.site_reviews import author_label_from_client, enqueue_quote

    label = ""
    if payload.publish_consent:
        label = author_label_from_client(
            str(row.get("full_name") or ""),
            payload.city or "",
        )
    result = enqueue_quote(
        text=payload.text,
        source="cabinet",
        consent=True,
        publish_consent=bool(payload.publish_consent),
        author_label=label,
        client_id=str(row.get("id") or ""),
    )
    if result is None:
        raise HTTPException(status_code=400, detail="consent_required")
    if not result.get("queued"):
        raise HTTPException(
            status_code=400,
            detail=str(result.get("reason") or "rejected"),
        )
    item_id = str(result.get("id") or "")
    notify_site_review_queued(
        text=payload.text,
        item_id=item_id,
        source="cabinet",
        send_email=True,
        publish_consent=bool(payload.publish_consent),
        author_label=label,
        client_id=str(row.get("id") or ""),
    )
    detail = (
        "После модерации появится на странице с датой публикации."
        if payload.publish_consent
        else "Принято как внутренняя обратная связь (без публикации на сайте)."
    )
    return PortalSiteReviewResponse(
        ok=True,
        queued=True,
        id=item_id,
        status=str(result.get("status") or ""),
        detail=detail,
    )


@router.get("/me/notification-links")
def me_notification_links(
    case_id: str | None = None,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Порядок CTA кабинет/MAX по preferred_channel (для писем и заглушек)."""
    from sfrfr.integrations.client_channels.notifications import notification_channel_links

    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client only")
    row = _ensure_client_row(principal)
    return notification_channel_links(
        preferred_channel=row.get("preferred_channel"),
        max_linked=bool(row.get("max_user_id")),
        case_id=case_id,
    )


def _find_client_by_phone(phone: str) -> dict | None:
    from sfrfr.security.login_otp import normalize_phone

    normalized = normalize_phone(phone)
    if not normalized:
        return None
    client = get_supabase_client()
    digits = "".join(ch for ch in normalized if ch.isdigit())
    candidates = {normalized, digits, "+" + digits}
    if digits.startswith("7") and len(digits) == 11:
        candidates.add("8" + digits[1:])
        candidates.add("+7" + digits[1:])
    for value in candidates:
        rows = client.table("clients").select("*").eq("phone", value).limit(1).execute().data or []
        if rows:
            return rows[0]
    return None


def _ensure_auth_email_for_client(row: dict, *, phone: str) -> str:
    """Email для Supabase session: из клиента или синтетический."""
    email = (row.get("email") or "").strip().lower()
    if email and "@" in email:
        return email
    max_uid = str(row.get("max_user_id") or "unknown")
    # стабильный технический email, подтверждённый через service role
    return f"max_{max_uid}@clients.sfrfr.local"


def _supabase_magic_token_hash(email: str) -> str:
    from sfrfr.db.staff_roles import find_user_by_email

    client = get_supabase_client()
    existing = find_user_by_email(email)
    if existing is None:
        created = client.auth.admin.create_user(
            {
                "email": email.strip().lower(),
                "email_confirm": True,
                "app_metadata": {"role_source": "max_otp_login"},
            }
        )
        if getattr(created, "user", None) is None and not (
            isinstance(created, dict) and created.get("user")
        ):
            raise HTTPException(status_code=502, detail="failed to create auth user")
    link = client.auth.admin.generate_link({"type": "magiclink", "email": email})
    props = getattr(link, "properties", None)
    if props is None and isinstance(link, dict):
        props = link.get("properties") or link
    hashed = None
    if props is not None:
        hashed = getattr(props, "hashed_token", None) or (
            props.get("hashed_token") if isinstance(props, dict) else None
        )
    if not hashed:
        raise HTTPException(status_code=502, detail="failed to create auth session")
    return str(hashed)


def _raise_auth(
    status_code: int,
    detail: str,
    *,
    event: str,
    audience: str = "client",
    ticket: str | None = None,
    **extra: Any,
) -> NoReturn:
    auth_event(
        event,
        outcome="denied" if status_code < 500 else "error",
        audience=audience,
        status_code=status_code,
        detail=detail,
        ticket=ticket,
        **extra,
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _validate_cabinet_register(
    payload: CabinetRegisterRequest,
) -> tuple[str, str]:
    """Почта и телефон обязательны; телефон — российский +7XXXXXXXXXX."""
    from sfrfr.security.login_otp import normalize_phone

    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отметьте согласие с СОПД — без него регистрацию продолжить нельзя.",
        )
    email = (payload.email or "").strip().lower()
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите корректную электронную почту.",
        )
    phone = normalize_phone(payload.phone or "")
    if not phone or not phone.startswith("+7") or len(phone) != 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите телефон в формате +7 XXX XXX-XX-XX.",
        )
    return email, phone


@router.post("/auth/register", response_model=CabinetRegisterResponse)
def register_cabinet_client(payload: CabinetRegisterRequest) -> CabinetRegisterResponse:
    """Проверка контактов саморегистрации клиента (почта и телефон обязательны)."""
    email, phone = _validate_cabinet_register(payload)
    return CabinetRegisterResponse(
        ok=True,
        email=email,
        phone=phone,
        message="Контакты приняты. Код подтверждения отправим на почту.",
    )


@router.post("/auth/otp/request", response_model=MaxOtpRequestResponse)
def request_max_otp(payload: MaxOtpRequest) -> MaxOtpRequestResponse:
    """Старт входа через MAX: код в чате MAX, ввод на странице кабинета.

    1) На странице входа открывают чат MAX и нажимают «Получить код для входа».
    2) Код из MAX вводят на странице входа — сессия открывается.
    3) В чате MAX предлагаются кнопки: приложение или интерфейс.
    Для staff — отдельный сценарий с кодом со страницы входа.
    """
    from sfrfr.db.staff_roles import get_staff_role_by_email
    from sfrfr.integrations.amocrm.urls import staff_max_login_url
    from sfrfr.integrations.max.client import MaxBotClient, inline_confirm_login_keyboard
    from sfrfr.security.login_otp import (
        CONFIRM_STAFF_CABINET_LOGIN_LABEL,
        CONFIRM_WEB_LOGIN_LABEL,
        normalize_phone,
    )
    from sfrfr.security.login_pending import (
        bind_max_direct,
        create_pending,
    )

    settings = get_settings()
    audience = payload.audience or "client"
    staff_email = (payload.email or "").strip().lower() or None

    if audience == "staff":
        if not staff_email or "@" not in staff_email:
            _raise_auth(
                400,
                "Укажите рабочий email сотрудника.",
                event="otp_request",
                audience="staff",
                reason="missing_email",
            )
        role = get_staff_role_by_email(staff_email)
        if role is None:
            _raise_auth(
                403,
                "Email не найден в staff-ролях. Подайте заявку на доступ "
                "во вкладке «Запрос доступа» или обратитесь к администратору.",
                event="otp_request",
                audience="staff",
                reason="staff_email_unknown",
            )
        pending = create_pending(audience="staff", staff_email=staff_email)
        from sfrfr.db.staff_roles import trusted_login_max_user_id
        from sfrfr.integrations.max.ops_bot import get_ops_bot, ops_bot_configured

        trusted_mid = trusted_login_max_user_id(staff_email)
        if trusted_mid:
            bind_max_direct(
                ticket_id=pending.ticket_id,
                max_user_id=trusted_mid,
                contact=staff_email,
            )
            auth_event(
                "otp_request",
                outcome="ok",
                audience="staff",
                ticket=pending.ticket_id,
                status="pending_confirm",
                mode="trusted_max",
            )
            if ops_bot_configured():
                try:
                    ops = get_ops_bot()
                    if ops.available:
                        ops.send_message(
                            user_id=trusted_mid,
                            text=(
                                "Запрос входа в кабинет сотрудника.\n"
                                f"Нажмите «{CONFIRM_STAFF_CABINET_LOGIN_LABEL}»."
                            ),
                            attachments=inline_confirm_login_keyboard(
                                ticket_id=pending.ticket_id,
                                label=CONFIRM_STAFF_CABINET_LOGIN_LABEL,
                            ),
                        )
                except Exception:  # noqa: BLE001
                    logger.exception("ops staff login notify failed email=%s", staff_email)
            return MaxOtpRequestResponse(
                ok=True,
                ticket=pending.ticket_id,
                pair_code="",
                expires_in=max(60, int(pending.expires_at - time.time())),
                max_bot_url=staff_max_login_url(),
                status="pending_confirm",
                message=(
                    "Нажмите «Перейти в MAX» ниже и подтвердите вход в ops-боте. "
                    "Кабинет откроется на этой странице автоматически."
                ),
            )

        auth_event(
            "otp_request",
            outcome="ok",
            audience="staff",
            ticket=pending.ticket_id,
            status="pending_pair",
        )
        return MaxOtpRequestResponse(
            ok=True,
            ticket=pending.ticket_id,
            pair_code=pending.pair_code,
            expires_in=max(60, int(pending.expires_at - time.time())),
            max_bot_url=staff_max_login_url(),
            status="pending_pair",
            message=(
                "Код ниже — отправьте его в ops-бот MAX, затем нажмите "
                "«Войти в кабинет сотрудника». Кабинет откроется на этой странице. "
                "При первом входе нужно одобрение руководителя."
            ),
        )

    pending = create_pending()
    phone_raw = (payload.phone or "").strip()

    if phone_raw:
        phone = normalize_phone(phone_raw)
        if not phone:
            _raise_auth(
                400,
                "invalid phone",
                event="otp_request",
                ticket=pending.ticket_id,
                reason="invalid_phone",
            )
        row = _find_client_by_phone(phone)
        if not row:
            _raise_auth(
                404,
                (
                    "Номер не найден. Войдите через чат MAX без номера "
                    "(кнопка «Получить код для входа») или по почте."
                ),
                event="otp_request",
                ticket=pending.ticket_id,
                reason="phone_not_found",
            )
        if not row.get("max_user_id"):
            _raise_auth(
                404,
                (
                    "Для номера нет привязки к чату MAX. Откройте чат MAX, нажмите «Начать», "
                    "затем «Получить код для входа» и введите код на странице входа."
                ),
                event="otp_request",
                ticket=pending.ticket_id,
                reason="phone_no_max",
            )
        contact = _ensure_auth_email_for_client(row, phone=phone)
        bind_max_direct(
            ticket_id=pending.ticket_id,
            max_user_id=str(row["max_user_id"]),
            contact=contact,
        )
        bot = MaxBotClient()
        if not bot.available:
            _raise_auth(
                503,
                "MAX bot not configured",
                event="otp_request",
                ticket=pending.ticket_id,
                reason="max_bot_missing",
            )
        text = f"Запрос входа в личный кабинет на компьютере.\nНажмите «{CONFIRM_WEB_LOGIN_LABEL}»."
        attachments = inline_confirm_login_keyboard(
            ticket_id=pending.ticket_id,
            label=CONFIRM_WEB_LOGIN_LABEL,
        )
        try:
            bot.send_message(
                text=text,
                user_id=str(row["max_user_id"]),
                attachments=attachments,
            )
        except Exception as exc:  # noqa: BLE001
            auth_event(
                "otp_request",
                outcome="error",
                status_code=502,
                ticket=pending.ticket_id,
                max_user_id=str(row["max_user_id"]),
                reason="max_send_failed",
                detail=type(exc).__name__,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Не удалось отправить сообщение в чат MAX. Откройте чат MAX и нажмите «Начать»."
                ),
            ) from exc
        ClientChannelRepository().audit(
            str(row.get("user_id") or row.get("id")),
            f"login_confirm_max_sent:{row['max_user_id']}",
        )
        auth_event(
            "otp_request",
            outcome="ok",
            ticket=pending.ticket_id,
            max_user_id=str(row["max_user_id"]),
            status="pending_confirm",
            mode="phone",
        )
        return MaxOtpRequestResponse(
            ok=True,
            ticket=pending.ticket_id,
            pair_code="",
            expires_in=max(60, int(pending.expires_at - time.time())),
            max_bot_url=settings.max_chat_url,
            status="pending_confirm",
            message=(
                "Подтвердите вход в чате MAX одной кнопкой — "
                "кабинет откроется на этой странице автоматически."
            ),
        )

    auth_event(
        "otp_request",
        outcome="ok",
        ticket=pending.ticket_id,
        status="pending_pair",
        mode="max_chat_code",
    )
    return MaxOtpRequestResponse(
        ok=True,
        ticket=pending.ticket_id,
        pair_code="",
        expires_in=max(60, int(pending.expires_at - time.time())),
        max_bot_url=settings.max_chat_url,
        status="pending_pair",
        message=(
            "Откройте чат MAX и нажмите «Получить код для входа» — "
            "кабинет откроется на этой странице автоматически."
        ),
    )


@router.get("/auth/otp/poll", response_model=MaxOtpPollResponse)
def poll_max_otp(ticket: str) -> MaxOtpPollResponse:
    """ПК опрашивает: подтвердил ли клиент/сотрудник вход в MAX."""
    from sfrfr.security.login_pending import get_pending

    pending = get_pending(ticket)
    if not pending:
        auth_event(
            "otp_poll",
            outcome="denied",
            ticket=ticket,
            status="expired",
            reason="missing_or_stale",
        )
        return MaxOtpPollResponse(
            ok=False,
            status="expired",
            message="Сессия входа не найдена или устарела.",
        )
    if pending.status == "approved" and pending.token_hash:
        auth_event(
            "otp_poll",
            outcome="ok",
            audience=pending.audience,
            ticket=ticket,
            status="approved",
        )
        return MaxOtpPollResponse(
            ok=True,
            status="approved",
            token_hash=pending.token_hash,
            email=pending.email or "",
            type="email",
            message="Вход подтверждён",
        )
    if pending.status == "expired":
        auth_event(
            "otp_poll",
            outcome="denied",
            audience=pending.audience,
            ticket=ticket,
            status="expired",
            reason="ttl",
        )
        return MaxOtpPollResponse(
            ok=False,
            status="expired",
            message="Время подтверждения истекло.",
        )
    if pending.status == "pending_manager":
        return MaxOtpPollResponse(
            ok=True,
            status="pending_manager",
            message="Ожидаем подтверждение руководителя в чате MAX…",
        )
    if pending.status == "code_sent":
        return MaxOtpPollResponse(
            ok=True,
            status="code_sent",
            verify_ticket=pending.otp_verify_ticket or "",
            message="Код отправлен в чат MAX — введите его на этой странице.",
        )
    if pending.status == "pending_confirm":
        return MaxOtpPollResponse(
            ok=True,
            status="pending_confirm",
            verify_ticket=pending.otp_verify_ticket or "",
            message=(
                "Код отправлен в чат MAX — введите его здесь."
                if pending.audience == "client"
                else "Код принят в чате MAX. Завершаем вход…"
            ),
        )
    if pending.audience == "staff":
        return MaxOtpPollResponse(
            ok=True,
            status="pending_pair",
            message=(
                f"Отправьте в чат MAX код {pending.pair_code} со страницы входа — "
                "после этого вход откроется сам."
            ),
        )
    return MaxOtpPollResponse(
        ok=True,
        status="pending_pair",
        message=(
            "Откройте личный чат MAX и нажмите «Получить код для входа». "
            "Затем введите код на этой странице."
        ),
    )


def _session_from_max_identity(*, contact: str, max_user_id: str) -> MaxOtpVerifyResponse:
    from sfrfr.db.client_channels import ClientChannelRepository

    repo = ClientChannelRepository()
    row = repo.get_by_max_user_id(max_user_id)
    if not row:
        # Клиент мог ещё не успеть создаться в MAX — создаём здесь
        try:
            row = repo.ensure_for_max_user(max_user_id)
        except Exception as exc:  # noqa: BLE001
            auth_event(
                "session_from_max",
                outcome="error",
                status_code=502,
                max_user_id=max_user_id,
                reason="ensure_client_failed",
                detail=type(exc).__name__,
            )
            raise HTTPException(status_code=502, detail="failed to create client") from exc
    if not row:
        _raise_auth(
            404,
            "client not found",
            event="session_from_max",
            max_user_id=max_user_id,
            reason="client_missing",
        )

    email = contact if "@" in contact else _ensure_auth_email_for_client(row, phone="")
    token_hash = _supabase_magic_token_hash(email)

    from sfrfr.db.staff_roles import find_user_by_email, user_id_of

    client = get_supabase_client()
    user = find_user_by_email(email)
    if user is not None and not row.get("user_id"):
        client.table("clients").update({"user_id": user_id_of(user), "email": email}).eq(
            "id", row["id"]
        ).execute()

    ClientChannelRepository().audit(
        str(row.get("user_id") or row.get("id")),
        f"login_otp_max_ok:{max_user_id}",
    )
    return MaxOtpVerifyResponse(
        ok=True,
        token_hash=token_hash,
        email=email,
        type="email",
        message="Вход подтверждён",
    )


@router.post("/auth/otp/verify", response_model=MaxOtpVerifyResponse)
def verify_max_otp(payload: MaxOtpVerifyRequest) -> MaxOtpVerifyResponse:
    """Проверить код из MAX и выдать token_hash для Supabase verifyOtp."""
    from sfrfr.security.login_otp import verify_login_otp
    from sfrfr.security.login_pending import (
        consume_otp_code,
        lookup_otp_verify_ticket_by_code,
    )

    ticket = (payload.ticket or "").strip()
    if not ticket:
        ticket = lookup_otp_verify_ticket_by_code(payload.code) or ""
    if not ticket:
        _raise_auth(
            400,
            "invalid or expired code",
            event="otp_verify",
            reason="missing_ticket",
        )
    verified = verify_login_otp(ticket=ticket, code=payload.code)
    if not verified:
        _raise_auth(
            400,
            "invalid or expired code",
            event="otp_verify",
            ticket=ticket[:32],
            reason="bad_code",
        )
    contact, max_user_id = verified
    consume_otp_code(payload.code)
    response = _session_from_max_identity(contact=contact, max_user_id=max_user_id)
    auth_event(
        "otp_verify",
        outcome="ok",
        ticket=ticket[:32],
        max_user_id=max_user_id,
    )
    return response


@router.post("/auth/otp/link", response_model=MaxOtpVerifyResponse)
def verify_max_login_link(payload: MaxOtpLinkRequest) -> MaxOtpVerifyResponse:
    """Обмен одноразовой ссылки из MAX на token_hash (вход без ввода кода)."""
    from sfrfr.security.login_otp import verify_login_link
    from sfrfr.security.login_pending import approve, latest_for_max

    verified = verify_login_link(link_token=payload.t)
    if not verified:
        _raise_auth(
            400,
            "invalid or expired link",
            event="otp_link",
            reason="bad_link",
        )
    contact, max_user_id = verified
    response = _session_from_max_identity(contact=contact, max_user_id=max_user_id)
    auth_event(
        "otp_link",
        outcome="ok",
        max_user_id=max_user_id,
    )
    # Если вход начали на ПК — одобряем poll-сессию при открытии ссылки с телефона
    pending = latest_for_max(max_user_id)
    if (
        pending is not None
        and pending.audience == "client"
        and pending.status in {"pending_confirm", "pending_pair"}
        and response.token_hash
        and response.email
    ):
        approve(
            ticket_id=pending.ticket_id,
            token_hash=response.token_hash,
            email=response.email,
        )
    return response


@router.post("/link/max", response_model=PortalMeResponse)
def link_max(
    payload: LinkMaxRequest,
    principal: Principal = Depends(get_current_principal),
) -> PortalMeResponse:
    """JWT-клиент привязывает MAX (initData или signed link_token)."""
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client only")
    if principal.is_max_only:
        raise HTTPException(status_code=400, detail="use web OTP session to complete link")
    max_uid = _resolve_max_user_id(
        max_user_id=payload.max_user_id,
        init_data=payload.init_data,
        link_token=payload.link_token,
        require_verified=True,
    )
    repo = _channel_repo()
    row = repo.link_max_to_user(
        user_id=principal.user_id,
        max_user_id=max_uid,
        email=principal.email,
    )
    if payload.preferred_channel is not None:
        row = repo.set_preferred_channel(str(row["id"]), payload.preferred_channel.value)
    repo.audit(principal.audit_actor_id(), f"link_max:{max_uid}")
    return _me_response(principal, row)


@router.post("/link/web-from-max", response_model=LinkWebFromMaxResponse)
def link_web_from_max(payload: LinkWebFromMaxRequest) -> LinkWebFromMaxResponse:
    """
    Из mini-app: зарегистрировать max_user_id и выдать ссылку на веб-кабинет.
    OTP/JWT клиент завершит связку через POST /link/max (+ link_token).
    """
    from sfrfr.security.max_link_token import make_max_link_token

    max_uid = _resolve_max_user_id(
        max_user_id=payload.max_user_id,
        init_data=payload.init_data,
        require_verified=bool(payload.init_data),
    )
    repo = _channel_repo()
    row = repo.ensure_for_max_user(max_uid)
    if payload.preferred_channel:
        row = repo.set_preferred_channel(str(row["id"]), payload.preferred_channel.value)
    token = make_max_link_token(max_uid)
    settings = get_settings()
    qs = f"link_max={max_uid}&link_token={token}"
    base = settings.cabinet_public_url.rstrip("/")
    if payload.case_id:
        cabinet = f"{base}/cases/{payload.case_id}?{qs}"
    else:
        cabinet = f"{base}/?{qs}"
    return LinkWebFromMaxResponse(
        client_id=str(row["id"]),
        max_user_id=max_uid,
        cabinet_url=cabinet,
        link_token=token,
        message=(
            "Войдите в веб-кабинет по одноразовому коду. После входа аккаунт будет связан с MAX."
        ),
    )


@router.get("/me/cases", response_model=list[CaseSummary])
def list_my_cases(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummary]:
    """Клиент видит свои дела, сотрудник — дела по своей роли."""
    repo = _repo()
    summaries: list[CaseSummary] = []
    for case in repo.list_cases(principal):
        case_id = str(case["id"])
        unread = 0
        actor_id = principal.audit_actor_id()
        if not principal.is_staff and actor_id:
            unread = repo.unread_staff_messages(case_id, actor_id)
        summaries.append(
            _summary(
                case,
                unread=unread,
                consent_accepted=repo.has_consent(case_id),
            )
        )
    return summaries


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_my_case(
    payload: CreateCaseRequest | None = None,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Создать дело для текущего клиента (веб или MAX). Один клиент — одно дело."""
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client only")
    body = payload or CreateCaseRequest()
    client_row = _ensure_client_row(principal)
    if body.full_name and body.full_name.strip():
        get_supabase_client().table("clients").update({"full_name": body.full_name.strip()}).eq(
            "id", client_row["id"]
        ).execute()
    repo = _repo()
    case = repo.create_case_for_client(
        client_id=str(client_row["id"]),
        actor_id=principal.audit_actor_id(),
        problem_type=body.problem_type,
    )
    case_id = str(case["id"])
    refreshed = repo.require_case(principal, case_id)
    detail = _client_detail(
        refreshed,
        consent_accepted=repo.has_consent(case_id),
        draft=None,
    )
    return detail.model_dump(mode="json")


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    case = repo.require_case(principal, case_id)
    repo.audit(case_id, principal.audit_actor_id(), "case_viewed")
    if principal.is_staff:
        pipeline = CaseRepository._one_or_none(
            get_supabase_client()
            .table("case_pipeline_data")
            .select("*")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )
        case["pipeline_data"] = pipeline
        return case

    detail = _client_detail(
        case,
        consent_accepted=repo.has_consent(case_id),
        draft=repo.get_pipeline_draft(case_id),
    )
    return detail.model_dump(mode="json")


@router.get("/meta/status-labels")
def status_labels() -> dict:
    """Общие RU-лейблы этапов для веб и mini-app (ТЗ-09 §5.2)."""
    from sfrfr.models.case_status import status_labels_payload

    return status_labels_payload()


@router.post("/cases/{case_id}/run", response_model=PipelineRunResponse)
def run_case_pipeline(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> PipelineRunResponse:
    """Запросить проверку (клиент или сотрудник). Без автоподачи в СФР."""
    repo = _repo()
    repo.require_case(principal, case_id)
    if not principal.is_staff:
        _require_consent_for_upload(repo, case_id)

    # Legacy in-memory пайплайн, если дело ещё там (мини-приложение MVP).
    try:
        from sfrfr.core.case_store import get_case_store

        store = get_case_store()
        store.require(case_id)
        record = store.run_until(case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        repo.audit(case_id, principal.user_id, "pipeline_run_local")
        findings = [
            FindingItem(type=f.type, detail=f.detail, severity=getattr(f, "severity", "info"))
            for f in record.ctx.findings
        ]
        draft = record.ctx.draft.model_dump(mode="json") if record.ctx.draft else None
        analysis_notes = record.ctx.analysis_notes
        # Синхронизация в Supabase для кабинета эксперта (если дело уже там).
        if principal.is_staff:
            try:
                repo.save_pipeline_snapshot(
                    case_id,
                    CaseRepository.snapshot_from_case_context(record.ctx),
                )
            except Exception:  # noqa: BLE001 — локальный run не должен падать из‑за sync
                pass
        else:
            # Клиенту не отдаём сырое обоснование аналитика (только эксперту/админу).
            analysis_notes = None
        return PipelineRunResponse(
            ok=True,
            message="Проверка выполнена (локальный пайплайн).",
            pipeline_status=record.ctx.status.value,
            findings=findings,
            analysis_notes=analysis_notes,
            draft=draft,
            warning=_SFR_WARNING,
        )
    except KeyError:
        pass

    result = repo.request_pipeline_run(case_id, principal.user_id)
    findings = [
        FindingItem(
            type=str(f.get("type") or "info"),
            detail=str(f.get("detail") or ""),
            severity=str(f.get("severity") or "info"),
        )
        for f in (result.get("findings") or [])
        if isinstance(f, dict)
    ]
    analysis_notes = result.get("analysis_notes") if principal.is_staff else None
    return PipelineRunResponse(
        ok=bool(result.get("ok")),
        message=str(result.get("message") or ""),
        pipeline_status=result.get("pipeline_status"),
        findings=findings,
        analysis_notes=str(analysis_notes) if analysis_notes else None,
        draft=result.get("draft") if isinstance(result.get("draft"), dict) else None,
        warning=_SFR_WARNING,
    )


@router.get("/cases/{case_id}/findings")
def list_findings(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    findings = repo.get_pipeline_findings(case_id)
    # Fallback: in-memory store
    if not findings:
        try:
            from sfrfr.core.case_store import get_case_store

            record = get_case_store().require(case_id)
            findings = [f.model_dump(mode="json") for f in record.ctx.findings]
        except KeyError:
            pass
    return {"case_id": case_id, "findings": findings, "warning": _SFR_WARNING}


@router.get("/cases/{case_id}/draft")
def get_draft(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    draft = repo.get_pipeline_draft(case_id)
    if draft is None:
        try:
            from sfrfr.core.case_store import get_case_store

            record = get_case_store().require(case_id)
            if record.ctx.draft:
                draft = record.ctx.draft.model_dump(mode="json")
        except KeyError:
            pass
    return {
        "case_id": case_id,
        "draft": draft,
        "submission_instruction": _SUBMISSION_INSTRUCTION,
        "warning": _SFR_WARNING,
    }


@router.get("/cases/{case_id}/checklist")
def list_checklist(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    case = repo.require_case(principal, case_id)
    items = list(case.get("checklist_items") or []) or repo.list_checklist(case_id)
    return {
        "case_id": case_id,
        "items": items,
        "next_action": CaseRepository.next_client_action({**case, "checklist_items": items}),
        "required_documents": CaseRepository.required_document_items(
            {**case, "checklist_items": items}
        ),
    }


@router.get("/cases/{case_id}/documents")
def list_case_documents(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.list_documents(case_id)


@router.post("/cases/{case_id}/consents", status_code=status.HTTP_201_CREATED)
def accept_consent(
    case_id: str,
    payload: ConsentAcceptRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client or representative only")
    forwarded = request.headers.get("x-forwarded-for")
    ip: str | None
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    return repo.accept_consent(
        case_id,
        version=payload.version,
        actor_id=principal.user_id,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/cases/{case_id}/representatives")
def list_case_representatives_client(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Клиент/представитель: кто имеет доступ к делу (ТЗ-03)."""
    repo = _repo()
    repo.require_case(principal, case_id)
    items = repo.list_representatives(case_id)
    return {
        "items": items,
        "you_are_representative": repo.is_representative(principal, case_id),
    }


@router.get("/cases/{case_id}/consents")
def list_consents(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    return {
        "consents": repo.list_consents(case_id),
        "contract_acceptances": repo.list_contract_acceptances(case_id),
        "offer_url": "https://proverkastaza.ru/oferta/",
        "pdn_url": "https://proverkastaza.ru/politika-pdn/",
        "consent_url": "https://proverkastaza.ru/soglasie/",
    }


@router.post("/cases/{case_id}/contract-acceptances", status_code=status.HTTP_201_CREATED)
def accept_contract(
    case_id: str,
    payload: ContractAcceptRequest,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client or representative only")
    return repo.accept_contract(
        case_id,
        offer_version=payload.offer_version,
        actor_id=principal.user_id,
        order_id=payload.order_id,
        meta={"accepted_by": principal.user_id},
    )


@router.get("/cases/{case_id}/orders")
def list_orders(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    repo = _repo()
    repo.require_case(principal, case_id)
    return repo.list_orders(case_id)


@router.get("/cases/{case_id}/result")
def get_result(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    evidence = repo.get_result_evidence(case_id) or {}
    before = float(evidence.get("monthly_before_rub") or 0)
    after = float(evidence.get("monthly_after_rub") or 0)
    lump = float(evidence.get("lump_sum_rub") or 0)
    fee = calc_success_fee(lump_sum_rub=lump, monthly_increase_rub=max(after - before, 0))
    return {
        "evidence": evidence or None,
        "success_fee": fee,
        "post_payment_note": (
            "Счёт post-payment выставляется только после подтверждения результата экспертом "
            "и по истечении окна ожидания 2–3 месяца."
        ),
        "warning": _SFR_WARNING,
    }


@router.post("/cases/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_case_document(
    case_id: str,
    file: UploadFile = File(...),
    doc_type: str | None = Form(default=None),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Загрузить разрешённый файл в private bucket через доверенный API."""
    repo = _repo()
    repo.require_case(principal, case_id)
    if not principal.is_staff:
        _require_consent_for_upload(repo, case_id)

    content_type = file.content_type or ""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="unsupported document type")

    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="document exceeds 50 MiB")

    filename = Path(file.filename or "document").name
    document_id = str(uuid4())
    storage_path = f"{case_id}/{document_id}/{filename}"
    content_preview = _extract_upload_preview(data, filename)
    client = get_supabase_client()
    client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
        storage_path,
        data,
        {"content-type": content_type, "x-upsert": "false"},
    )
    insert_row: dict[str, Any] = {
        "id": document_id,
        "case_id": case_id,
        "storage_path": storage_path,
        "doc_type": doc_type,
        "uploaded_by": principal.user_id,
    }
    if content_preview:
        insert_row["content_preview"] = content_preview
    response = client.table("documents").insert(insert_row).execute()
    action = "result_decision_uploaded" if doc_type == "sfr_decision" else "document_uploaded"
    repo.audit(case_id, principal.user_id, action)
    try:
        from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe

        mirror = mirror_case_document_safe(case_id, filename, data)
        if mirror.get("ok"):
            repo.audit(case_id, principal.user_id, "document_mirrored_yandex_disk")
    except Exception as exc:  # noqa: BLE001
        logger.info("document yandex disk mirror skipped: %s", exc)
    try:
        from sfrfr.integrations.max.case_chat_log import (
            append_case_chat_message,
            format_document_event,
        )

        append_case_chat_message(
            case_id=case_id,
            author_kind="staff" if principal.is_staff else "client",
            body=format_document_event(filename=filename, doc_type=doc_type),
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("document case_message skipped: %s", exc)
    if doc_type == "sfr_decision":
        client.table("cases").update({"b2c_status": "result_pending"}).eq("id", case_id).execute()
        existing = repo.get_result_evidence(case_id)
        if existing:
            client.table("result_evidence").update({"document_id": document_id}).eq(
                "id", existing["id"]
            ).execute()
        else:
            client.table("result_evidence").insert(
                {"case_id": case_id, "document_id": document_id}
            ).execute()
    if (doc_type or "").strip().lower() == "diagnosis_report" and principal.is_staff:
        try:
            from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository

            DiagnosisFeedbackRepository().mark_pdf_issued(case_id)
        except Exception as exc:  # noqa: BLE001
            logger.info("diagnosis_feedback pdf_issued skipped: %s", exc)
    payment_receipt = None
    try:
        from sfrfr.ocr import extract_text_from_bytes
        from sfrfr.services.payment_receipt import handle_uploaded_receipt

        ocr_text = extract_text_from_bytes(data, filename)
        payment_receipt = handle_uploaded_receipt(
            repo,
            case_id=case_id,
            ocr_text=ocr_text,
            document_id=document_id,
            actor_id=principal.user_id,
            doc_type=doc_type,
        )
        if payment_receipt and payment_receipt.get("status") == "confirmed":
            action = "payment_receipt_confirmed"
            repo.audit(case_id, principal.user_id, action)
    except Exception as exc:  # noqa: BLE001
        logger.info("payment receipt check skipped: %s", exc)
    row = response.data[0] if response.data else {"id": document_id}
    if content_preview and "content_preview" not in row:
        row = {**row, "content_preview": content_preview}
    if "storage_path" not in row:
        row = {**row, "storage_path": storage_path}
    if "doc_type" not in row:
        row = {**row, "doc_type": doc_type}
    client_doc = _client_document(row)
    if payment_receipt:
        client_doc = {
            **client_doc,
            "payment_receipt": {
                "status": payment_receipt.get("status"),
                "ask_receipt": payment_receipt.get("ask_receipt"),
                "message": payment_receipt.get("client_message"),
            },
        }
    return client_doc


@router.post(
    "/cases/{case_id}/documents/{document_id}/signed-url",
    response_model=SignedDocumentResponse,
)
def create_document_signed_url(
    case_id: str,
    document_id: str,
    principal: Principal = Depends(get_current_principal),
) -> SignedDocumentResponse:
    """Выдать краткоживущую ссылку после проверки доступа к делу."""
    repo = _repo()
    repo.require_case(principal, case_id)
    row = CaseRepository._one_or_none(
        get_supabase_client()
        .table("documents")
        .select("storage_path")
        .eq("id", document_id)
        .eq("case_id", case_id)
        .limit(1)
        .execute()
    )
    if not row:
        raise HTTPException(status_code=404, detail="document not found")

    expires_in = SIGNED_URL_TTL_SECONDS
    storage_path = str(row["storage_path"] or "")
    signed = (
        get_supabase_client()
        .storage.from_(PRIVATE_STORAGE_BUCKET)
        .create_signed_url(storage_path, expires_in)
    )
    raw_url = str(signed.get("signedURL") or signed.get("signedUrl") or "")
    if not raw_url:
        raise HTTPException(status_code=502, detail="signed url failed")
    repo.audit(case_id, principal.user_id, "document_download_url_created")
    return SignedDocumentResponse(
        url=_with_download_param(raw_url, _document_filename(storage_path)),
        expires_in=expires_in,
    )


@router.delete("/cases/{case_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_document(
    case_id: str,
    document_id: str,
    principal: Principal = Depends(get_current_principal),
) -> None:
    """Удалить файл до приёмки специалистом (клиент, не PDF диагностики)."""
    if principal.is_staff:
        raise HTTPException(status_code=403, detail="client only")
    repo = _repo()
    case = repo.require_case(principal, case_id)
    client = get_supabase_client()
    row = CaseRepository._one_or_none(
        client.table("documents")
        .select("id, storage_path, doc_type, created_at, content_preview")
        .eq("id", document_id)
        .eq("case_id", case_id)
        .limit(1)
        .execute()
    )
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    if _lower_doc_type(row.get("doc_type")) == "diagnosis_report":
        raise HTTPException(status_code=403, detail="result cannot be deleted")
    work = build_client_work_map(
        pipeline_status=str(case.get("pipeline_status") or ""),
        b2c_status=str(case.get("b2c_status") or ""),
        consent_accepted=repo.has_consent(case_id),
        documents=_client_documents(list(case.get("documents") or [])),
        checklist_items=list(case.get("checklist_items") or []),
    )
    allowed = {
        str(slot.get("document_id"))
        for slot in (work.get("documents") or [])
        if slot.get("can_delete")
    }
    if document_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Файл уже принят специалистом или его нельзя удалить.",
        )
    path = str(row.get("storage_path") or "")
    if path:
        try:
            client.storage.from_(PRIVATE_STORAGE_BUCKET).remove([path])
        except Exception as exc:  # noqa: BLE001
            logger.info("storage remove skipped: %s", exc)
    client.table("documents").delete().eq("id", document_id).eq("case_id", case_id).execute()
    repo.audit(case_id, principal.user_id, "document_deleted")


def _lower_doc_type(value: object) -> str:
    return str(value or "").strip().lower()


@router.get("/diag-share/{token}")
def open_diagnosis_share(token: str, request: Request) -> RedirectResponse:
    """Одноразовая/короткоживущая ссылка на PDF диагностики (ТЗ-28/30).

    Без case_id в URL. Prefetch/боты не считаются открытием.
    """
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    raw = (token or "").strip()
    if len(raw) < 20:
        raise HTTPException(status_code=404, detail="not found")
    ua = request.headers.get("user-agent")
    try:
        resolved = DiagnosisDeliveryService().resolve_share_token(raw, user_agent=ua)
    except LookupError:
        raise HTTPException(status_code=404, detail="not found") from None
    except PermissionError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    if resolved.get("bot_skipped"):
        from fastapi.responses import Response

        return Response(status_code=204)  # type: ignore[return-value]

    document_id = resolved.get("document_id")
    case_id = resolved.get("case_id")
    if not document_id or not case_id:
        raise HTTPException(status_code=404, detail="document missing")
    row = CaseRepository._one_or_none(
        get_supabase_client()
        .table("documents")
        .select("storage_path")
        .eq("id", document_id)
        .eq("case_id", case_id)
        .limit(1)
        .execute()
    )
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    expires_in = SIGNED_URL_TTL_SECONDS
    signed = (
        get_supabase_client()
        .storage.from_(PRIVATE_STORAGE_BUCKET)
        .create_signed_url(row["storage_path"], expires_in)
    )
    url = signed.get("signedURL") or signed.get("signedUrl")
    if not url:
        raise HTTPException(status_code=502, detail="signed url failed")
    try:
        CaseRepository().audit(str(case_id), None, "diagnosis_share_viewed")
    except Exception as exc:  # noqa: BLE001
        logger.info("diagnosis share audit skipped: %s", exc)
    return RedirectResponse(url=str(url), status_code=302)


@router.get("/cases/{case_id}/messages")
def list_messages(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    """Полная лента: сообщения + события загрузки документов (как в переписке MAX)."""
    case = _repo().require_case(principal, case_id)
    # Досозданные в буфере реплики (до появления case_id) — слить при открытии карточки.
    try:
        client_row = case.get("clients") or {}
        if isinstance(client_row, list):
            client_row = client_row[0] if client_row else {}
        max_uid = str((client_row or {}).get("max_user_id") or "").strip()
        if max_uid:
            from sfrfr.integrations.max.case_chat_log import flush_pending_case_chat

            flush_pending_case_chat(max_user_id=max_uid, case_id=case_id)
    except Exception as exc:  # noqa: BLE001
        logger.info("flush pending chat on list_messages skipped: %s", exc)

    client = get_supabase_client()
    messages = (
        client.table("case_messages")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    docs = (
        client.table("documents")
        .select("id, storage_path, doc_type, created_at, uploaded_by")
        .eq("case_id", case_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    # Уже записанные [Документ] … — не дублировать из таблицы documents.
    covered: set[str] = set()
    for row in messages:
        body = str(row.get("body") or "")
        if body.startswith("[Документ] "):
            covered.add(body.split("\n", 1)[0].strip().lower())

    timeline: list[dict] = list(messages)
    for doc in docs:
        path = str(doc.get("storage_path") or "")
        name = Path(path).name or "файл"
        doc_type = doc.get("doc_type")
        from sfrfr.integrations.max.case_chat_log import format_document_event

        body = format_document_event(filename=name, doc_type=str(doc_type) if doc_type else None)
        if body.lower() in covered:
            continue
        timeline.append(
            {
                "id": f"doc:{doc.get('id')}",
                "case_id": case_id,
                "author_user_id": doc.get("uploaded_by"),
                "author_kind": "client",
                "body": body,
                "created_at": doc.get("created_at"),
            }
        )
    timeline.sort(key=lambda row: str(row.get("created_at") or ""))
    return timeline


@router.post("/cases/{case_id}/messages", status_code=status.HTTP_201_CREATED)
def create_message(
    case_id: str,
    payload: CaseMessageCreate,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    repo = _repo()
    repo.require_case(principal, case_id)
    kind = "staff" if principal.is_staff else "client"
    response = (
        get_supabase_client()
        .table("case_messages")
        .insert(
            {
                "case_id": case_id,
                "author_user_id": principal.user_id,
                "author_kind": kind,
                "body": payload.body,
            }
        )
        .execute()
    )
    repo.audit(case_id, principal.user_id, "message_created")
    return response.data[0]
