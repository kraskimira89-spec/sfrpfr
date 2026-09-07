"""Согласие на ПДн: один раз на клиента (MAX и кабинет)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION

logger = logging.getLogger(__name__)

CONSENT_GATE_TEXT = (
    "Перед началом работы нужно ваше согласие на обработку персональных данных.\n\n"
    "Нажимая «Начать», вы соглашаетесь на обработку персональных данных "
    "в целях проверки сведений о стаже и подготовки документов "
    "(текст согласия: https://proverkastaza.ru/soglasie/).\n\n"
    "Без согласия мы не сможем принять документы и вести дело."
)

CONSENT_DECLINED_TEXT = (
    "Поняли. Без согласия на обработку персональных данных "
    "мы не можем принять документы и вести дело.\n\n"
    "Если передумаете — нажмите «Начать» в этом чате."
)

PDN_CONSENT_DECLINE_CALLBACK = "pdn_consent:no"


def client_has_pdn_consent(client_row: dict[str, Any] | None) -> bool:
    if not isinstance(client_row, dict):
        return False
    version = str(client_row.get("pdn_consent_version") or "").strip()
    accepted = client_row.get("pdn_consent_accepted_at")
    return bool(accepted) and (not version or version == CURRENT_CONSENT_VERSION)


def mark_client_pdn_consent(
    *,
    client_id: str | None = None,
    max_user_id: str | None = None,
    version: str = CURRENT_CONSENT_VERSION,
) -> bool:
    """Записать согласие на уровне клиента. True если обновлено."""
    try:
        from sfrfr.db.session import get_supabase_client

        client = get_supabase_client()
        now = datetime.now(UTC).isoformat()
        payload = {
            "pdn_consent_version": version,
            "pdn_consent_accepted_at": now,
        }
        if client_id:
            client.table("clients").update(payload).eq("id", client_id).execute()
            return True
        mid = str(max_user_id or "").strip()
        if mid:
            client.table("clients").update(payload).eq("max_user_id", mid).execute()
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("mark_client_pdn_consent failed: %s", exc)
    return False


def ensure_case_consent_from_client(
    *,
    case_id: str,
    client_id: str | None,
    actor_id: str | None = None,
) -> bool:
    """Если у клиента уже есть согласие — продублировать на дело без повторного вопроса."""
    if not case_id:
        return False
    try:
        from sfrfr.db.case_repository import CaseRepository

        repo = CaseRepository()
        if repo.has_consent(case_id):
            return True
        client_row = None
        if client_id:
            rows = (
                repo.client.table("clients")
                .select("id, pdn_consent_version, pdn_consent_accepted_at")
                .eq("id", client_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            client_row = rows[0] if rows else None
        if not client_has_pdn_consent(client_row):
            return False
        version = str((client_row or {}).get("pdn_consent_version") or CURRENT_CONSENT_VERSION)
        repo.accept_consent(
            case_id,
            version=version,
            actor_id=actor_id or "system:client_pdn_once",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_case_consent_from_client failed case=%s: %s", case_id[:8], exc)
        return False


def accept_pdn_once(
    *,
    case_id: str | None,
    client_id: str | None = None,
    max_user_id: str | None = None,
    actor_id: str | None = None,
    version: str = CURRENT_CONSENT_VERSION,
) -> None:
    """Согласие один раз: клиент + (если есть) дело."""
    mark_client_pdn_consent(
        client_id=client_id,
        max_user_id=max_user_id,
        version=version,
    )
    if case_id:
        try:
            from sfrfr.db.case_repository import CaseRepository

            repo = CaseRepository()
            if not repo.has_consent(case_id):
                repo.accept_consent(
                    case_id,
                    version=version,
                    actor_id=actor_id or "system:max_start",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("accept_pdn_once case failed: %s", exc)
