"""Статусы пенсионного кейса (MVP pipeline)."""

from __future__ import annotations

from enum import StrEnum


class CaseStatus(StrEnum):
    """Жизненный цикл кейса: intake → … → completed."""

    INTAKE = "intake"
    DOCUMENTS_RECEIVED = "documents_received"
    OCR_DONE = "ocr_done"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    AUDITED = "audited"
    DRAFT_READY = "draft_ready"
    HUMAN_REVIEW = "human_review"
    COMPLETED = "completed"
    FAILED = "failed"


# Линейный happy-path (без FAILED)
PIPELINE_ORDER: tuple[CaseStatus, ...] = (
    CaseStatus.INTAKE,
    CaseStatus.DOCUMENTS_RECEIVED,
    CaseStatus.OCR_DONE,
    CaseStatus.CLASSIFIED,
    CaseStatus.EXTRACTED,
    CaseStatus.AUDITED,
    CaseStatus.DRAFT_READY,
    CaseStatus.HUMAN_REVIEW,
    CaseStatus.COMPLETED,
)

# Отображаемые названия этапов для бота / UI
# Совпадают с shared/status-labels.json (единый словарь ТЗ-09 §5.2).
STATUS_LABELS_RU: dict[CaseStatus, str] = {
    CaseStatus.INTAKE: "Приём данных",
    CaseStatus.DOCUMENTS_RECEIVED: "Документы получены",
    CaseStatus.OCR_DONE: "Текст распознан",
    CaseStatus.CLASSIFIED: "Документы классифицированы",
    CaseStatus.EXTRACTED: "Периоды извлечены",
    CaseStatus.AUDITED: "Сверка завершена",
    CaseStatus.DRAFT_READY: "Черновик готов",
    CaseStatus.HUMAN_REVIEW: "На проверке специалиста",
    CaseStatus.COMPLETED: "Завершено",
    CaseStatus.FAILED: "Ошибка",
}

STATUS_HINTS_RU: dict[CaseStatus, str] = {
    CaseStatus.INTAKE: "Загрузите сканы ИЛС и трудовой книжки.",
    CaseStatus.DOCUMENTS_RECEIVED: "Документы приняты. Можно запустить проверку.",
    CaseStatus.OCR_DONE: "Текст распознан, идёт классификация.",
    CaseStatus.CLASSIFIED: "Типы документов определены.",
    CaseStatus.EXTRACTED: "Периоды собраны, выполняется сверка.",
    CaseStatus.AUDITED: "Найдены расхождения — готовим черновик.",
    CaseStatus.DRAFT_READY: "Черновик заявления готов к проверке.",
    CaseStatus.HUMAN_REVIEW: "Ждите ответа специалиста.",
    CaseStatus.COMPLETED: "Дело закрыто.",
    CaseStatus.FAILED: "Произошла ошибка при обработке.",
}

B2C_LABELS_RU: dict[str, str] = {
    "lead": "Заявка",
    "consent_accepted": "Согласие принято",
    "diagnostic_paid": "Диагностика оплачена",
    "contract_accepted": "Заказ принят",
    "service_paid": "Сопровождение оплачено",
    "package_delivered": "Пакет выдан",
    "awaiting_client_submission": "Ожидаем вашу подачу",
    "result_pending": "Ждём решение СФР",
    "result_confirmed": "Результат подтверждён",
    "success_fee_due": "Счёт за результат",
    "success_fee_paid": "Вознаграждение оплачено",
    "closed": "Закрыто",
}


def status_label_ru(status: CaseStatus | str | None) -> str:
    """Русское название статуса/этапа для пользователя."""
    if status is None:
        return "Неизвестно"
    raw = str(status)
    try:
        value = status if isinstance(status, CaseStatus) else CaseStatus(raw)
    except ValueError:
        return B2C_LABELS_RU.get(raw, raw)
    return STATUS_LABELS_RU.get(value, B2C_LABELS_RU.get(raw, raw))


def human_case_status(pipeline: str | None, b2c: str | None = None) -> str:
    """Короткий статус для пенсионера (без OCR / findings). Совпадает с senior в JSON."""
    p = (pipeline or "").lower()
    b = (b2c or "").lower()
    if "success_fee" in b or "result_confirmed" in b:
        return "Есть результат"
    if "service_paid" in b or "diagnostic_paid" in b:
        return "Оплата получена"
    if "draft" in p or "human_review" in p:
        return "Готов черновик / проверка специалиста"
    if "failed" in p:
        return "Нужна помощь специалиста"
    if any(x in p for x in ("ocr", "classif", "extract", "audit")):
        return "Идёт проверка"
    if "document" in p or "documents" in b:
        return "Документы получены"
    if "completed" in p or "closed" in b:
        return "Дело завершено"
    return "Нужны документы"


def status_labels_payload() -> dict[str, dict[str, str]]:
    """Общий пакет лейблов для /meta/status-labels и фронтов."""
    return {
        "labels": {s.value: STATUS_LABELS_RU[s] for s in CaseStatus},
        "hints": {s.value: STATUS_HINTS_RU[s] for s in CaseStatus},
        "b2c": dict(B2C_LABELS_RU),
        "senior": {
            "needs_documents": "Нужны документы",
            "documents_received": "Документы получены",
            "in_review": "Идёт проверка",
            "draft_or_expert": "Готов черновик / проверка специалиста",
            "needs_help": "Нужна помощь специалиста",
            "payment_received": "Оплата получена",
            "has_result": "Есть результат",
            "completed": "Дело завершено",
        },
    }

def next_status(current: CaseStatus) -> CaseStatus | None:
    """Следующий статус по happy-path или None, если конец / FAILED."""
    if current is CaseStatus.FAILED:
        return None
    try:
        idx = PIPELINE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(PIPELINE_ORDER):
        return None
    return PIPELINE_ORDER[idx + 1]
