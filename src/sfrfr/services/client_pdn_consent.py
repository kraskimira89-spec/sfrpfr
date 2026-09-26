"""Согласие на ПДн: один раз на клиента (MAX и кабинет)."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION

logger = logging.getLogger(__name__)

COOKIE_CONSENT_VERSION = "cookies-site-2026-09-22"

CONSENT_GATE_TEXT = (
    "Перед началом работы нужно ваше согласие на обработку персональных данных.\n\n"
    "Оператор: ООО «ПОД ПРИСМОТРОМ», ИНН 8905066468, ОГРН 1208900000572, "
    "629804, ЯНАО, г. Ноябрьск, ул. Рабочая, д. 109Б, кв. 4; "
    "e-mail: proverkastaza@yandex.ru; генеральный директор Лопакова Н. Ф.\n\n"
    "Цели: создать ваше дело, проверить документы о стаже, "
    "подготовить проекты обращений и держать с вами связь.\n"
    "Какие данные: ФИО, год рождения, контакты, сведения о работе и стаже, "
    "документы, ответы СФР, переписка в этом чате.\n"
    "Что делаем с данными: получаем, храним, систематизируем, распознаём текст, "
    "анализируем, готовим документы.\n"
    "Где и сколько храним: на серверах в России, до достижения целей "
    "или отзыва согласия, но не дольше 5 лет после завершения работы по договору.\n"
    "Как отозвать: письмом на proverkastaza@yandex.ru или через личный кабинет.\n\n"
    "Полный текст согласия: https://proverkastaza.ru/soglasie/\n"
    "Политика обработки персональных данных: https://proverkastaza.ru/politika-pdn/\n"
    "На сайте используются файлы cookie: https://proverkastaza.ru/cookies/\n\n"
    f"Версия согласия: {CURRENT_CONSENT_VERSION}.\n\n"
    "Нажимая «Начать», вы даёте согласие. Без него мы не принимаем анкету и документы. "
    "Согласие запрашивается один раз — повторно мы его не просим."
)

CONSENT_DECLINED_TEXT = (
    "Поняли. Без согласия на обработку персональных данных "
    "мы не можем принять документы и вести дело.\n\n"
    "Вопросы можно задать по телефону +7 909 195-04-08 "
    "или на proverkastaza@yandex.ru.\n\n"
    "Если передумаете — нажмите «Начать» в этом чате."
)

PDN_CONSENT_DECLINE_CALLBACK = "pdn_consent:no"


def consent_text_sha256() -> str:
    """SHA-256 текста экрана согласия — доказательство, какой текст видел клиент."""
    return hashlib.sha256(CONSENT_GATE_TEXT.encode("utf-8")).hexdigest()


def max_consent_evidence(
    *,
    update_type: str,
    callback_id: str | None,
    chat_id: int | str | None,
    message_id: str | None,
    via: str,
) -> dict[str, Any]:
    """Технические сведения события MAX для записи согласия (без ПДн)."""
    raw = {
        "channel": "max",
        "via": via,
        "update_type": update_type,
        "callback_id": callback_id,
        "chat_id": str(chat_id) if chat_id is not None else None,
        "message_id": message_id,
    }
    return {k: v for k, v in raw.items() if v}


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
            "cookie_consent_version": COOKIE_CONSENT_VERSION,
            "cookie_consent_accepted_at": now,
        }
        slim = {
            "pdn_consent_version": version,
            "pdn_consent_accepted_at": now,
        }

        def _upd(eq_col: str, eq_val: str) -> bool:
            try:
                client.table("clients").update(payload).eq(eq_col, eq_val).execute()
                return True
            except Exception:
                try:
                    client.table("clients").update(slim).eq(eq_col, eq_val).execute()
                    return True
                except Exception as exc2:  # noqa: BLE001
                    logger.warning("mark_client_pdn_consent failed: %s", exc2)
                    return False

        if client_id:
            return _upd("id", client_id)
        mid = str(max_user_id or "").strip()
        if mid:
            return _upd("max_user_id", mid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mark_client_pdn_consent failed: %s", exc)
    return False


def _ensure_cookie_consent_row(repo: Any, *, case_id: str) -> None:
    try:
        existing = (
            repo.client.table("consents")
            .select("id")
            .eq("case_id", case_id)
            .eq("version", COOKIE_CONSENT_VERSION)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            return
        repo.client.table("consents").insert(
            {"case_id": case_id, "version": COOKIE_CONSENT_VERSION}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("cookie consent row skipped: %s", exc)


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
            try:
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
            except Exception:  # noqa: BLE001
                client_row = None
        inherit = client_has_pdn_consent(client_row)
        if not inherit and client_id:
            siblings = (
                repo.client.table("cases")
                .select("id")
                .eq("client_id", client_id)
                .limit(50)
                .execute()
                .data
                or []
            )
            for row in siblings if isinstance(siblings, list) else []:
                sid = str(row.get("id") or "")
                if not sid or sid == case_id:
                    continue
                if (
                    repo.client.table("consents")
                    .select("id")
                    .eq("case_id", sid)
                    .eq("version", CURRENT_CONSENT_VERSION)
                    .limit(1)
                    .execute()
                    .data
                ):
                    inherit = True
                    break
        if not inherit:
            return False
        version = str(
            (client_row or {}).get("pdn_consent_version") or CURRENT_CONSENT_VERSION
        )
        repo.accept_consent(
            case_id,
            version=version,
            actor_id=actor_id or "system:client_pdn_once",
            client_id=client_id,
            source="inherited",
        )
        _ensure_cookie_consent_row(repo, case_id=case_id)
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
    evidence: dict[str, Any] | None = None,
) -> None:
    """Согласие один раз: клиент (ПДн+cookies) + (если есть) дело."""
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
                    client_id=client_id,
                    max_user_id=str(max_user_id or "").strip() or None,
                    text_sha256=consent_text_sha256(),
                    source="max_start",
                    evidence=evidence,
                )
            _ensure_cookie_consent_row(repo, case_id=case_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("accept_pdn_once case failed: %s", exc)
