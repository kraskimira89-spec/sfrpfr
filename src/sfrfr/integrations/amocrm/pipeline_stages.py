"""Этапы воронки amoCRM и маппинг сигналов SFRFR → status (по имени этапа)."""

from __future__ import annotations

from typing import Any

# Ключ → точное имя статуса в amo (воронка «Проверка стажа»).
AMO_STAGE_NAMES: dict[str, str] = {
    "new_lead": "Новый лид",
    "contacted": "Связались",
    "qualified": "Квалифицирован",
    "diag_offer": "Диагностика предложена",
    "diag_paid": "Диагностика оплачена",
    "docs_in": "Документы в кабинете",
    "diag_out": "Диагностика выдана",
    "svc_offer": "Сопровождение предложено",
    "svc_paid": "Сопровождение оплачено",
    "pack_out": "Пакет выдан",
    "client_submit": "Клиент подал в СФР",
    "result_ok": "Результат подтверждён",
    "review_asked": "Отзыв запрошен",
    "review_got": "Отзыв получен",
    "won": "Закрыто успешно",
}

# Порядок для запрета отката колонки назад (lost отдельно).
AMO_STAGE_ORDER: tuple[str, ...] = (
    "new_lead",
    "contacted",
    "qualified",
    "diag_offer",
    "diag_paid",
    "docs_in",
    "diag_out",
    "svc_offer",
    "svc_paid",
    "pack_out",
    "client_submit",
    "result_ok",
    "review_asked",
    "review_got",
    "won",
)

# Имена статусов, которые создаём скриптом ensure.
AMO_STAGES_TO_ENSURE: tuple[str, ...] = tuple(
    AMO_STAGE_NAMES[k] for k in AMO_STAGE_ORDER
)

from sfrfr.integrations.amocrm.task_templates import (  # noqa: F401
    TASK_DOCS_AFTER_DIAG,
    TASK_FIRST_CONTACT,
    TASK_REVIEW_REMINDER,
)


def stage_order_index(key: str | None) -> int:
    if not key:
        return -1
    try:
        return AMO_STAGE_ORDER.index(key)
    except ValueError:
        return -1


def suggest_amo_stage_key(
    *,
    pipeline_status: str | None = None,
    b2c_status: str | None = None,
    task: str | None = None,
    for_create: bool = False,
) -> str | None:
    """
    Предложить ключ этапа amo.
    При обновлении не возвращает new_lead (входной этап только на create).
    """
    pipe = (pipeline_status or "").strip().lower()
    b2c = (b2c_status or "").strip().lower()
    task_l = (task or "").strip().lower()

    key: str | None = None

    if task_l.startswith("review_ask") or task_l in {"review_asked", "review"}:
        key = "review_asked"
    elif task_l.startswith("paid:diag"):
        key = "diag_paid"
    elif task_l.startswith("paid:accomp") or task_l.startswith("paid:service"):
        key = "svc_paid"
    elif task_l.startswith("paid:"):
        key = "svc_paid"
    elif b2c == "diagnostic_paid":
        key = "diag_paid"
    elif b2c == "service_paid":
        key = "svc_paid"
    elif b2c == "package_delivered":
        key = "pack_out"
    elif b2c in {"awaiting_client_submission", "result_pending"}:
        key = "client_submit"
    elif b2c == "result_confirmed":
        key = "result_ok"
    elif b2c == "closed":
        key = "won"
    elif pipe == "completed":
        key = "review_asked"
    elif pipe in {"audited", "draft_ready", "human_review"}:
        key = "diag_out"
    elif pipe in {
        "documents_received",
        "ocr_done",
        "classified",
        "extracted",
    }:
        key = "docs_in"
    elif pipe == "intake" or b2c == "lead":
        key = "new_lead" if for_create else None
    elif for_create:
        key = "new_lead"

    if key == "new_lead" and not for_create:
        return None
    return key


def resolve_status_id_by_name(
    statuses: list[dict[str, Any]],
    stage_name: str,
) -> int | None:
    want = stage_name.strip().casefold()
    for item in statuses:
        name = str(item.get("name") or "").strip()
        if name.casefold() == want and item.get("id") is not None:
            return int(item["id"])
    aliases = {
        "закрыто успешно": ("успешно реализовано", "успех"),
        "отказ": ("закрыто и не реализовано", "не реализовано"),
    }
    for canonical, alts in aliases.items():
        if want == canonical:
            for alt in alts:
                for item in statuses:
                    if str(item.get("name") or "").strip().casefold() == alt:
                        return int(item["id"])
    return None


def key_for_status_id(
    statuses: list[dict[str, Any]],
    status_id: int | None,
) -> str | None:
    if status_id is None:
        return None
    name_by_id = {
        int(s["id"]): str(s.get("name") or "")
        for s in statuses
        if s.get("id") is not None
    }
    name = name_by_id.get(int(status_id), "")
    for key, stage_name in AMO_STAGE_NAMES.items():
        if name.strip().casefold() == stage_name.casefold():
            return key
    if "успеш" in name.casefold():
        return "won"
    if "не реализовано" in name.casefold() or name.casefold() == "закрыто и не реализовано":
        return "lost"
    return None


def should_move_forward(current_key: str | None, target_key: str | None) -> bool:
    if not target_key:
        return False
    if current_key is None:
        return True
    return stage_order_index(target_key) >= stage_order_index(current_key)
