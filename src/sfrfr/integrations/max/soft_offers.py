"""Периодические мягкие предложения: чек-лист и рекомендация друзьям.

Не после каждого сообщения и не одновременно с каждым другим предложением.
Без новых фоновых рассылок — только встраивание в ответ по запросу handler.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store
from sfrfr.services.lead_magnet_checklist import LEAD_MAGNET_BOT_URL

OfferKind = Literal["checklist", "share"]

# В коротком сценарии не повторяем чаще этого окна.
MIN_GAP = timedelta(hours=24)

CHECKLIST_HINT = (
    "Если удобно — могу прислать бесплатный чек-лист «Как самому проверить стаж» на e-mail. "
    "Напишите «Нужен чек-лист» или /checklist."
)

SHARE_HINT = (
    "Если кому-то из близких тоже полезно разобраться со стажем — "
    f"можно поделиться ссылкой на бот: {LEAD_MAGNET_BOT_URL}"
)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _mark(rec: MaxIntakeRecord, kind: OfferKind, *, now: datetime) -> None:
    iso = now.isoformat()
    if kind == "checklist":
        rec.soft_checklist_offered_at = iso
    else:
        rec.soft_share_offered_at = iso
    get_intake_store().save(rec)


def mark_declined(rec: MaxIntakeRecord, kind: OfferKind) -> None:
    if kind == "checklist":
        rec.soft_checklist_declined = True
    else:
        rec.soft_share_declined = True
    get_intake_store().save(rec)


def pick_soft_offer(
    rec: MaxIntakeRecord,
    *,
    logical_msg_count: int,
    now: datetime | None = None,
    other_offer_this_turn: bool = False,
) -> tuple[OfferKind, str] | None:
    """Выбрать одно мягкое предложение или None.

    Условия: не чаще MIN_GAP; не вместе с другим оффером; учитывать отказ и выдачу.
    """
    if other_offer_this_turn:
        return None
    moment = now or datetime.now(UTC)
    # Не в самом начале диалога и не слишком часто.
    if logical_msg_count < 6:
        return None

    checklist_at = _parse(rec.soft_checklist_offered_at)
    share_at = _parse(rec.soft_share_offered_at)
    last_any = max([t for t in (checklist_at, share_at) if t is not None], default=None)
    # После любого мягкого оффера — пауза MIN_GAP (не чек-лист и share подряд).
    if last_any is not None and moment - last_any < MIN_GAP:
        return None
    checklist_ok = not rec.soft_checklist_declined and rec.lm_send_count == 0
    share_ok = not rec.soft_share_declined
    # Приоритет чек-листу, затем рекомендация друзьям.
    if checklist_ok and checklist_at is None:
        _mark(rec, "checklist", now=moment)
        return "checklist", CHECKLIST_HINT
    if share_ok and share_at is None:
        _mark(rec, "share", now=moment)
        return "share", SHARE_HINT
    if checklist_ok and (checklist_at is None or moment - checklist_at >= MIN_GAP):
        _mark(rec, "checklist", now=moment)
        return "checklist", CHECKLIST_HINT
    if share_ok and (share_at is None or moment - share_at >= MIN_GAP):
        _mark(rec, "share", now=moment)
        return "share", SHARE_HINT
    return None
