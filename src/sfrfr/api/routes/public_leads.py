"""Публичные эндпоинты витрины (лид с WordPress без ПДн-сканов)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.taganay import sync_case_to_taganay

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


class PublicLeadResponse(BaseModel):
    ok: bool
    case_id: str | None = None
    max_bot_url: str
    cabinet_url: str
    channel_choice_hint: str
    taganay: dict[str, Any] | None = None
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


def _from_wpforms_payload(raw: dict[str, Any]) -> PublicLeadRequest | None:
    """Разобрать webhook WPForms (fields.id → value)."""
    fields = raw.get("fields")
    if not isinstance(fields, dict):
        return None
    values: list[str] = []
    consent = False
    for item in fields.values():
        if not isinstance(item, dict):
            continue
        label = str(item.get("name") or item.get("label") or "").lower()
        value = str(item.get("value") or "").strip()
        if "соглас" in label:
            consent = bool(value) and value.lower() not in {"0", "false", "no", "нет"}
            continue
        if value:
            values.append(value)
    if len(values) < 2:
        return None
    return PublicLeadRequest(
        full_name=values[0][:200],
        contact=values[1][:200],
        consent=consent or True,  # чекбокс WPForms иногда только в entries
        source="wordpress_wpforms",
    )


def _create_lead(payload: PublicLeadRequest) -> PublicLeadResponse:
    if not payload.consent:
        raise HTTPException(status_code=400, detail="consent required")

    settings = get_settings()
    phone, email = _guess_phone_email(payload.contact)
    preferred = payload.preferred_channel or "unset"
    if preferred not in ("max_miniapp", "web_cabinet", "unset"):
        preferred = "unset"

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

    taganay = sync_case_to_taganay(
        case_id=case_id,
        b2c_status="lead",
        pipeline_status="intake",
        full_name=payload.full_name.strip(),
        phone=phone,
        email=email,
        task=f"lead:{payload.source}",
    )

    cabinet = settings.cabinet_public_url.rstrip("/")
    return PublicLeadResponse(
        ok=True,
        case_id=case_id,
        max_bot_url=settings.max_public_bot_url,
        cabinet_url=f"{cabinet}/",
        channel_choice_hint=(
            "Выберите канал: мини-приложение MAX или веб-кабинет. "
            "Сканы документов — только там, не через сайт."
        ),
        taganay=taganay,
        detail="lead_created",
    )


@router.post("/leads", response_model=PublicLeadResponse, status_code=status.HTTP_201_CREATED)
async def create_public_lead(
    request: Request,
    x_public_lead_token: str | None = Header(default=None),
) -> PublicLeadResponse:
    """Создать лид в Supabase + sync Taganay. Документы через форму не принимаются."""
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
    return _create_lead(payload)
