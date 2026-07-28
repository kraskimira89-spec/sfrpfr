"""Публичные эндпоинты витрины (лид с WordPress без ПДн-сканов)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.amocrm import AmoCrmClient, sync_case_to_amocrm
from sfrfr.integrations.amocrm.sync import persist_crm_external_id
from sfrfr.integrations.recaptcha import RecaptchaVerifier

logger = logging.getLogger(__name__)
router = APIRouter()


class PublicLeadRequest(BaseModel):
    """Минимальный лид с сайта: без СНИЛС и файлов (ТЗ-02 / ТЗ-07 этап 1)."""

    full_name: str = Field(min_length=1, max_length=200)
    contact: str = Field(
        min_length=3,
        max_length=200,
        description="Телефон или канал связи (MAX/email)",
    )
    consent: bool = Field(description="Согласие на связь и обработку данных обращения")
    preferred_channel: str | None = Field(
        default=None,
        max_length=32,
        description="max_miniapp | web_cabinet | unset",
    )
    source: str = Field(default="wordpress", max_length=64)
    recaptcha_token: str | None = Field(
        default=None,
        max_length=4000,
        description="Токен reCAPTCHA Enterprise с витрины",
    )


class PublicLeadResponse(BaseModel):
    ok: bool
    case_id: str | None = None
    max_bot_url: str
    cabinet_url: str
    channel_choice_hint: str
    amocrm: dict[str, Any] | None = None
    detail: str = ""


def _require_public_token(x_public_lead_token: str | None) -> None:
    settings = get_settings()
    expected = (settings.public_lead_token or "").strip()
    if not expected:
        if settings.app_env in ("local", "dev", "development") or settings.app_debug:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PUBLIC_LEAD_TOKEN not configured",
        )
    if not x_public_lead_token or x_public_lead_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


def _guess_phone_email(contact: str) -> tuple[str | None, str | None]:
    raw = contact.strip()
    if "@" in raw:
        return None, raw[:200]
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if len(digits) >= 10:
        return digits[:32], None
    return raw[:64], None


def _normalize_channel(raw: str | None) -> str:
    """Привести выбор канала с формы к max_miniapp | web_cabinet | unset."""
    s = (raw or "").strip().lower()
    if not s:
        return "unset"
    if s in ("max_miniapp", "web_cabinet", "unset"):
        return s
    if "max" in s or "мессенджер" in s:
        return "max_miniapp"
    if "кабинет" in s or "web" in s or "сайт" in s or "браузер" in s:
        return "web_cabinet"
    return "unset"


def _from_wpforms_payload(raw: dict[str, Any]) -> PublicLeadRequest | None:
    """Разобрать webhook WPForms (fields.id → value)."""
    fields = raw.get("fields")
    if not isinstance(fields, dict):
        return None
    values: list[str] = []
    consent = False
    preferred: str | None = None
    recaptcha_token: str | None = None
    for item in fields.values():
        if not isinstance(item, dict):
            continue
        label = str(item.get("name") or item.get("label") or "").lower()
        value = str(item.get("value") or "").strip()
        if "recaptcha" in label or "g-recaptcha" in label:
            if value:
                recaptcha_token = value[:4000]
            continue
        if "соглас" in label:
            consent = bool(value) and value.lower() not in {"0", "false", "no", "нет"}
            continue
        if "канал" in label or "channel" in label:
            preferred = value
            continue
        if value:
            values.append(value)
    if len(values) < 2:
        return None
    if not recaptcha_token:
        recaptcha_token = (
            str(raw.get("recaptcha_token") or raw.get("g-recaptcha-response") or "").strip()
            or None
        )
    return PublicLeadRequest(
        full_name=values[0][:200],
        contact=values[1][:200],
        consent=consent,
        preferred_channel=_normalize_channel(preferred),
        source="wordpress_wpforms",
        recaptcha_token=recaptcha_token,
    )


def _require_amocrm_lead(amocrm: dict[str, Any] | None) -> None:
    """После заявки с сайта сделка в amoCRM обязательна (кроме local без ключей)."""
    settings = get_settings()
    amo = amocrm if isinstance(amocrm, dict) else {}
    local = settings.app_env.strip().lower() in ("local", "dev", "development")
    client = AmoCrmClient()
    if amo.get("skipped") or not client.available:
        if local:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="amocrm_not_configured",
        )
    if not amo.get("ok") or not amo.get("lead_id"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="amocrm_sync_failed",
        )


def _notify_max_managers_new_lead(
    *,
    case_id: str,
    full_name: str,
    contact: str,
    channel: str,
    crm_url: str | None,
) -> dict[str, Any]:
    """Уведомить операторов в MAX о новом лиде (клиенту без max_user_id писать нельзя)."""
    try:
        from sfrfr.db.staff_roles import list_manager_max_user_ids
        from sfrfr.integrations.max.client import MaxBotClient
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}

    settings = get_settings()
    bot = MaxBotClient()
    if not bot.available:
        return {"ok": False, "skipped": True, "reason": "no MAX_BOT_TOKEN"}

    manager_ids = list_manager_max_user_ids(
        extra_ids=settings.staff_login_approver_max_user_ids,
    )
    chat_ids = [
        p.strip()
        for p in (settings.staff_login_approver_max_chat_ids or "").split(",")
        if p.strip()
    ]
    if not manager_ids and not chat_ids:
        return {"ok": False, "skipped": True, "reason": "no managers"}

    lines = [
        "Новая заявка с сайта",
        f"Имя: {full_name}",
        f"Контакт: {contact}",
        f"Канал: {channel}",
        f"case_id: {case_id}",
    ]
    if crm_url:
        lines.append(f"amoCRM: {crm_url}")
    lines.append("Клиенту показаны ссылки MAX и кабинет. Напишите в выбранном канале.")
    text = "\n".join(lines)

    sent = 0
    targets = manager_ids or [None] * max(1, len(chat_ids))
    for i, mid in enumerate(targets):
        cid = chat_ids[i] if i < len(chat_ids) else None
        try:
            bot.send_message(
                text=text,
                user_id=str(mid) if mid else None,
                chat_id=cid,
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("max lead notify failed: %s", exc)
            continue
    return {"ok": sent > 0, "sent": sent}


def _require_recaptcha(token: str | None, *, client_ip: str | None = None) -> None:
    """При настроенном Enterprise — обязательная проверка; в local/debug можно пропуск."""
    verifier = RecaptchaVerifier()
    if not verifier.configured:
        return
    settings = get_settings()
    if not (token or "").strip():
        if settings.app_env in ("local", "dev", "development") or settings.app_debug:
            return
        raise HTTPException(status_code=400, detail="recaptcha_token required")
    result = verifier.verify(token or "", expected_action="lead", user_ip=client_ip)
    if result.get("skipped"):
        return
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail="recaptcha_failed",
        )


def _create_lead(
    payload: PublicLeadRequest,
    *,
    client_ip: str | None = None,
) -> PublicLeadResponse:
    if not payload.consent:
        raise HTTPException(status_code=400, detail="consent required")
    _require_recaptcha(payload.recaptcha_token, client_ip=client_ip)

    settings = get_settings()
    phone, email = _guess_phone_email(payload.contact)
    preferred = _normalize_channel(payload.preferred_channel)

    client = get_supabase_client()
    client_row = (
        client.table("clients")
        .insert(
            {
                "full_name": payload.full_name.strip(),
                "phone": phone,
                "email": email,
                "preferred_channel": preferred,
            }
        )
        .execute()
    )
    if not client_row.data:
        raise HTTPException(status_code=502, detail="failed to create client")
    client_id = str(client_row.data[0]["id"])

    case_row = (
        client.table("cases")
        .insert(
            {
                "client_id": client_id,
                "pipeline_status": "intake",
                "b2c_status": "lead",
                "segment": "b2c",
                "problem_type": f"lead:{payload.source}",
            }
        )
        .execute()
    )
    if not case_row.data:
        raise HTTPException(status_code=502, detail="failed to create case")
    case_id = str(case_row.data[0]["id"])

    client.table("access_audit").insert(
        {
            "case_id": case_id,
            "actor_id": None,
            "action": f"public_lead:{payload.source}",
        }
    ).execute()

    for idx, title in enumerate(
        ("Выписка ИЛС", "Трудовая книжка / сведения о стаже", "Решение СФР (если есть)")
    ):
        client.table("checklist_items").insert(
            {
                "case_id": case_id,
                "title": title,
                "item_type": "document",
                "owner": "client",
                "status": "open",
                "sort_order": idx,
            }
        ).execute()

    admin_base = (settings.admin_public_url or "").rstrip("/")
    amocrm = sync_case_to_amocrm(
        case_id=case_id,
        b2c_status="lead",
        pipeline_status="intake",
        full_name=payload.full_name.strip(),
        phone=phone,
        email=email,
        channel=preferred,
        source=payload.source,
        consent=bool(payload.consent),
        case_url=f"{admin_base}/?case={case_id}" if admin_base else None,
        task=f"lead:{payload.source}",
    )
    _require_amocrm_lead(amocrm if isinstance(amocrm, dict) else None)
    lead_id = amocrm.get("lead_id") if isinstance(amocrm, dict) else None
    if lead_id and amocrm.get("ok"):
        persist_crm_external_id(case_id, str(lead_id))

    crm_url = amocrm.get("crm_url") if isinstance(amocrm, dict) else None
    max_notify = _notify_max_managers_new_lead(
        case_id=case_id,
        full_name=payload.full_name.strip(),
        contact=payload.contact.strip(),
        channel=preferred,
        crm_url=str(crm_url) if crm_url else None,
    )
    if isinstance(amocrm, dict):
        amocrm = {**amocrm, "max_notify": max_notify}

    cabinet = settings.cabinet_public_url.rstrip("/")
    max_url = settings.max_public_bot_url or settings.max_chat_url
    if preferred == "web_cabinet":
        channel_hint = (
            "Вы выбрали веб-кабинет. Откройте кабинет и загрузите сканы только туда. "
            "При необходимости можно также написать в MAX."
        )
    elif preferred == "max_miniapp":
        channel_hint = (
            "Вы выбрали MAX. Откройте бота / мини-приложение и продолжите там. "
            "Сканы — только в MAX или кабинете, не через сайт."
        )
    else:
        channel_hint = (
            "Выберите канал: мини-приложение MAX или веб-кабинет. "
            "Сканы документов — только там, не через сайт."
        )
    return PublicLeadResponse(
        ok=True,
        case_id=case_id,
        max_bot_url=max_url,
        cabinet_url=f"{cabinet}/",
        channel_choice_hint=channel_hint,
        amocrm=amocrm if isinstance(amocrm, dict) else None,
        detail="lead_created",
    )


@router.post("/leads", response_model=PublicLeadResponse, status_code=status.HTTP_201_CREATED)
async def create_public_lead(
    request: Request,
    x_public_lead_token: str | None = Header(default=None),
) -> PublicLeadResponse:
    """Создать лид в Supabase + sync amoCRM. Документы через форму не принимаются."""
    _require_public_token(x_public_lead_token)
    raw = await request.json()
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    payload: PublicLeadRequest | None = None
    if "full_name" in raw and "contact" in raw:
        payload = PublicLeadRequest.model_validate(raw)
    else:
        payload = _from_wpforms_payload(raw)
    if payload is None:
        raise HTTPException(
            status_code=400,
            detail="expected full_name+contact+consent or WPForms fields payload",
        )
    client_ip = request.client.host if request.client else None
    return _create_lead(payload, client_ip=client_ip)
