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


def status_label_ru(status: CaseStatus | str | None) -> str:
    """Русское название статуса/этапа для пользователя."""
    if status is None:
        return "Неизвестно"
    try:
        value = status if isinstance(status, CaseStatus) else CaseStatus(str(status))
    except ValueError:
        return str(status)
    return STATUS_LABELS_RU.get(value, str(value))


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
