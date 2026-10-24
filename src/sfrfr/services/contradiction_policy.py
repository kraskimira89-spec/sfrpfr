"""Противоречия источников: сверка без обвинений и без подгонки стажа.

Не миграция БД — логическая модель (§25) поверх существующих полей/артефактов.
Слова клиента ≠ docs; OCR ≠ изображение; «не найдено в выписке» ≠ «официально не учтено».
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class ContradictionSubject(StrEnum):
    DATE = "date"
    ORGANIZATION = "organization"
    PERIOD = "period"
    DOCUMENT_OWNERSHIP = "document_ownership"
    OTHER = "other"


class SourceKind(StrEnum):
    CLIENT_WORDS = "client_words"
    LABOR = "labor"
    ILS = "ils"
    ARCHIVE_REF = "archive_ref"
    OCR_TEXT = "ocr_text"
    IMAGE = "image"
    OFFICIAL_REPLY = "official_reply"
    SERVICE_REPORT = "service_report"
    OTHER = "other"


class ReadQuality(StrEnum):
    CONFIRMED_BY_IMAGE = "confirmed_by_image"
    OCR_ONLY = "ocr_only"
    ILLEGIBLE = "illegible"
    UNKNOWN = "unknown"


class ContradictionStatus(StrEnum):
    DETECTED = "detected"
    CLARIFYING = "clarifying"
    RESOLVED = "resolved"
    NEEDS_SPECIALIST = "needs_specialist"


class ContradictionVariant(StrEnum):
    CLIENT_VS_DOC_PERIOD = "client_vs_doc_period"  # А
    LABOR_VS_ILS = "labor_vs_ils"  # Б
    TWO_DOCS_CONFLICT = "two_docs_conflict"  # В
    OCR_ERROR = "ocr_error"  # Г
    NAME_MISMATCH = "name_mismatch"  # Д
    HIDE_CONFLICT = "hide_conflict"  # Е
    NEW_DOC_AFTER_REPORT = "new_doc_after_report"  # Ж
    OFFICIAL_SAYS_COUNTED = "official_says_counted"  # З


_CLIENT_PERIOD_RE: Final = re.compile(
    r"я\s+работал.{0,40}(19\d{2}).{0,20}(19\d{2})|"
    r"почему\s+вы\s+указали\s+с\s+(19\d{2})",
    re.I | re.DOTALL,
)
_LABOR_ILS_RE: Final = re.compile(
    r"в\s+трудов.{0,40}выписк|в\s+выписк.{0,40}трудов|"
    r"в\s+трудовой\s+есть.{0,30}в\s+выписке\s+(их\s+)?нет|"
    r"точно\s+должны\s+прибавить",
    re.I | re.DOTALL,
)
_TWO_DOCS_RE: Final = re.compile(
    r"в\s+архивн.{0,30}трудов|трудов.{0,30}архивн|"
    r"какую\s+вы\s+поставите|какую\s+дату\s+поставите",
    re.I | re.DOTALL,
)
_OCR_RE: Final = re.compile(
    r"написано\s+[«\"]?\d{4}|прочитал[аи]?\s+[«\"]?\d{4}|"
    r"посмотрите\s+внимательнее|ocr|распозна",
    re.I,
)
_NAME_RE: Final = re.compile(
    r"девич(ью|ья)\s+фамил|смена\s+фамил|трудовая\s+на\s+.+\s+фамил|"
    r"это\s+моя.{0,20}зачем\s+вы\s+сомневаетесь",
    re.I | re.DOTALL,
)
_HIDE_RE: Final = re.compile(
    r"не\s+учитывайте|эту\s+справку\s+не|"
    r"по\s+трудовой\s+получается\s+больше|"
    r"так\s+и\s+напишите",
    re.I,
)
_NEW_DOC_RE: Final = re.compile(
    r"нашёл\s+ещё\s+(одну\s+)?справк|новый\s+документ|"
    r"вы\s+уже\s+написали.{0,40}не\s+подтвержд",
    re.I | re.DOTALL,
)
_OFFICIAL_COUNTED_RE: Final = re.compile(
    r"сфр\s+пишет.{0,30}учтён|стаж\s+учтён.{0,40}вы\s+говорили|"
    r"кто\s+прав",
    re.I | re.DOTALL,
)

def classify_contradiction_signal(text: str) -> ContradictionVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # Более специфичные раньше
    if _HIDE_RE.search(raw):
        return ContradictionVariant.HIDE_CONFLICT
    if _NEW_DOC_RE.search(raw):
        return ContradictionVariant.NEW_DOC_AFTER_REPORT
    if _OFFICIAL_COUNTED_RE.search(raw):
        return ContradictionVariant.OFFICIAL_SAYS_COUNTED
    if _NAME_RE.search(raw):
        return ContradictionVariant.NAME_MISMATCH
    if _OCR_RE.search(raw):
        return ContradictionVariant.OCR_ERROR
    if _TWO_DOCS_RE.search(raw):
        return ContradictionVariant.TWO_DOCS_CONFLICT
    if _LABOR_ILS_RE.search(raw):
        return ContradictionVariant.LABOR_VS_ILS
    if _CLIENT_PERIOD_RE.search(raw):
        return ContradictionVariant.CLIENT_VS_DOC_PERIOD
    return None


def may_pick_advantageous_date(*, earlier_start: bool, later_end: bool) -> bool:
    """Запрет выбирать дату ради увеличения стажа."""
    _ = earlier_start, later_end
    return False


def may_average_conflicting_dates() -> bool:
    return False


def may_promote_client_words_to_docs() -> bool:
    """Слова клиента не становятся evidence=docs."""
    return False


def may_treat_missing_ils_row_as_official_absence() -> bool:
    """Не найдено в доступной выписке ≠ официально не учтено."""
    return False


def may_merge_docs_on_similar_fio_alone() -> bool:
    return False


def may_silently_overwrite_prior_value() -> bool:
    return False


def ocr_vs_image_policy(
    *,
    image_readable: bool,
    ocr_value: str,
    image_value: str | None,
) -> dict[str, Any]:
    """До сверки с изображением OCR-дату не считать подтверждённой."""
    if not image_readable:
        return {
            "use_as_confirmed": False,
            "read_quality": ReadQuality.ILLEGIBLE.value,
            "action": "request_clearer_crop",
            "value": None,
        }
    if image_value and image_value != ocr_value:
        return {
            "use_as_confirmed": False,
            "read_quality": ReadQuality.CONFIRMED_BY_IMAGE.value,
            "action": "correct_ocr_then_invalidate_dependents",
            "value": image_value,
            "ocr_was": ocr_value,
        }
    if image_value and image_value == ocr_value:
        return {
            "use_as_confirmed": True,
            "read_quality": ReadQuality.CONFIRMED_BY_IMAGE.value,
            "action": "keep",
            "value": image_value,
        }
    return {
        "use_as_confirmed": False,
        "read_quality": ReadQuality.OCR_ONLY.value,
        "action": "verify_against_image",
        "value": ocr_value,
    }


def contradiction_record(
    *,
    subject: ContradictionSubject,
    source_a: SourceKind,
    value_a: str,
    source_b: SourceKind,
    value_b: str,
    read_quality: ReadQuality = ReadQuality.UNKNOWN,
    status: ContradictionStatus = ContradictionStatus.DETECTED,
    dependents: list[str] | None = None,
    next_step: str = "",
) -> dict[str, Any]:
    """Логическая карточка §25 — без новой миграции."""
    return {
        "subject": subject.value,
        "source_a": source_a.value,
        "value_a": value_a,
        "source_b": source_b.value,
        "value_b": value_b,
        "read_quality": read_quality.value,
        "status": status.value,
        "dependents": list(dependents or []),
        "next_step": next_step,
        "resolution": None,
        "client_accused": False,
        "advantageous_date_picked": False,
    }


def invalidate_dependents_after_correction(
    dependents: list[str],
) -> dict[str, str]:
    """После исправления OCR/даты — зависимые выводы требуют перепроверки."""
    return {d: "needs_recheck" for d in dependents}


def reply_has_banned_contradiction_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    # «исправлено» само по себе ок в успешном шаблоне; баним защитные/подгоночные.
    banned = (
        "вы врёте",
        "вы лжёте",
        "выгоднее поставить",
        "средняя дата",
        "гарантированный перерасчёт",
        "точно должны прибавить",
        "ошибка сфр подтверждена",
        "документ уже направлен с обращением",
    )
    return any(m in low for m in banned)


def block_independent_checks_on_one_dispute() -> bool:
    """Один спорный период не должен блокировать всё дело."""
    return False
