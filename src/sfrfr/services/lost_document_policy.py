"""Утраченные / неизвестные документы: движение по делу без обещания восстановления.

Логический план поиска (§27) без новой миграции БД.
Отсутствие документа ≠ отсутствие работы и ≠ доказанность периода.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class LostDocVariant(StrEnum):
    LOST_LABOR = "lost_labor"  # А
    EMPLOYER_CLOSED = "employer_closed"  # Б
    FUZZY_MEMORY = "fuzzy_memory"  # В
    PHOTO_ONLY = "photo_only"  # Г
    PARTIAL_LOSS = "partial_loss"  # Д
    ARCHIVE_NEGATIVE = "archive_negative"  # Е
    WITNESS_SUBSTITUTE = "witness_substitute"  # Ж
    SERVICE_LOST_FILES = "service_lost_files"  # З
    CLIENT_PAUSE = "client_pause"  # И


class SearchPlanStatus(StrEnum):
    NEEDS_CLARIFY = "needs_clarify"
    REQUEST_PREPARED = "request_prepared"
    REQUEST_SENT = "request_sent"
    REPLY_RECEIVED = "reply_received"


class SearchResult(StrEnum):
    FOUND = "found"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    NEEDS_MORE_SEARCH = "needs_more_search"
    UNKNOWN = "unknown"


class KnownPrecision(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


_LOST_LABOR_RE: Final = re.compile(
    r"трудов(ую|ая).{0,30}потерял|потерял.{0,30}трудов|"
    r"трудовой\s+нет|без\s+трудовой|"
    r"ничем\s+не\s+поможете",
    re.I | re.DOTALL,
)
_EMPLOYER_CLOSED_RE: Final = re.compile(
    r"завод(а)?\s+давно\s+нет|организаци[яи].{0,20}закрыл|"
    r"где\s+(я\s+)?теперь\s+возьму\s+справк|предприяти[ея].{0,20}нет",
    re.I | re.DOTALL,
)
_FUZZY_RE: Final = re.compile(
    r"каком[- ]?то\s+сму|ничего\s+больше\s+не\s+помню|"
    r"примерно\s+в\s+восьмидесят|не\s+помню\s+(точн|название|даты)",
    re.I | re.DOTALL,
)
_PHOTO_RE: Final = re.compile(
    r"оригинала\s+нет|только\s+(старая\s+)?фотограф|"
    r"копи[яи].{0,20}(страниц|трудов)|это\s+бесполезно",
    re.I | re.DOTALL,
)
_PARTIAL_RE: Final = re.compile(
    r"трудовая\s+есть.{0,40}справк.{0,30}потеря|"
    r"справк[аи]\s+о\s+зарплате.{0,30}потеря|"
    r"нужно\s+восстанавливать\s+вс[её]",
    re.I | re.DOTALL,
)
_ARCHIVE_NEG_RE: Final = re.compile(
    r"архив\s+(ответил|написал).{0,30}(ничего\s+нет|не\s+найден)|"
    r"ничего\s+нет.{0,20}вс[её]\s+пропало|"
    r"документы\s+не\s+найдены",
    re.I | re.DOTALL,
)
_WITNESS_RE: Final = re.compile(
    r"со\s+мной\s+люди\s+работали|люди\s+работали|"
    r"пусть\s+подтвердят|свидетел|"
    r"знакомые?\s+подтверд",
    re.I,
)
_SERVICE_LOST_RE: Final = re.compile(
    r"вы\s+(их\s+)?потеряли|я\s+вам\s+вс[её]\s+загрузил.{0,40}нет|"
    r"документов\s+нет.{0,20}загрузил|пропали\s+из\s+(кабинета|списка)",
    re.I | re.DOTALL,
)
_PAUSE_RE: Final = re.compile(
    r"не\s+буду\s+бегать|сил\s+нет|хочу\s+паузу|"
    r"больше\s+не\s+буду.{0,20}справк|устала?\s+искать",
    re.I | re.DOTALL,
)

BANNED_LOST_DOC_REPLY: Final[tuple[str, ...]] = (
    "без трудовой ничего сделать нельзя",
    "другой архив точно найдёт",
    "восстановим стаж",
    "обязательно подтвердим период",
    "документы точно в архиве",
    "потеряете пенсию",
    "сделаем вам справку",
    "ничего не потеряно",
    "гарантируем находку",
)


def classify_lost_document_signal(text: str) -> LostDocVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _SERVICE_LOST_RE.search(raw):
        return LostDocVariant.SERVICE_LOST_FILES
    if _PAUSE_RE.search(raw):
        return LostDocVariant.CLIENT_PAUSE
    if _WITNESS_RE.search(raw):
        return LostDocVariant.WITNESS_SUBSTITUTE
    if _ARCHIVE_NEG_RE.search(raw):
        return LostDocVariant.ARCHIVE_NEGATIVE
    if _PARTIAL_RE.search(raw):
        return LostDocVariant.PARTIAL_LOSS
    if _PHOTO_RE.search(raw):
        return LostDocVariant.PHOTO_ONLY
    if _FUZZY_RE.search(raw):
        return LostDocVariant.FUZZY_MEMORY
    if _EMPLOYER_CLOSED_RE.search(raw):
        return LostDocVariant.EMPLOYER_CLOSED
    if _LOST_LABOR_RE.search(raw):
        return LostDocVariant.LOST_LABOR
    return None


def may_treat_missing_doc_as_no_work() -> bool:
    return False


def may_treat_missing_doc_as_proven_period() -> bool:
    return False


def may_invent_archive_addressee() -> bool:
    return False


def may_promote_approximate_to_exact() -> bool:
    """«Примерно 1984–1986» не становится точными датами."""
    return False


def may_equate_photo_with_official_proof() -> bool:
    return False


def may_fabricate_document() -> bool:
    return False


def may_duplicate_identical_request_without_cause() -> bool:
    return False


def may_pressure_after_pause() -> bool:
    return False


def may_claim_files_safe_without_check() -> bool:
    return False


def block_case_on_one_missing_doc() -> bool:
    """Одна отсутствующая справка не останавливает независимые проверки."""
    return False


def normalize_client_period_precision(
    *,
    years_text: str,
    claimed_exact: bool,
) -> KnownPrecision:
    low = (years_text or "").casefold()
    if any(m in low for m in ("примерно", "около", "восьмидесят", "не помн")):
        return KnownPrecision.APPROXIMATE
    if claimed_exact and re.search(r"19\d{2}", years_text or ""):
        return KnownPrecision.EXACT
    if re.search(r"19\d{2}", years_text or ""):
        return KnownPrecision.APPROXIMATE
    return KnownPrecision.UNKNOWN


def search_plan_record(
    *,
    question: str,
    known: str,
    known_precision: KnownPrecision,
    missing: str,
    why_needed: str,
    already_checked: str = "",
    possible_source: str = "",
    source_is_confirmed: bool = False,
    next_step: str = "",
    actor: str = "client",
    status: SearchPlanStatus = SearchPlanStatus.NEEDS_CLARIFY,
) -> dict[str, Any]:
    """Логическая карточка §27 — без новой таблицы БД."""
    source_kind = "confirmed" if source_is_confirmed else "assumption"
    if not possible_source.strip():
        source_kind = "unknown"
    return {
        "question": question,
        "known": known,
        "known_precision": known_precision.value,
        "missing": missing,
        "why_needed": why_needed,
        "already_checked": already_checked,
        "possible_source": possible_source,
        "source_kind": source_kind,
        "next_step": next_step,
        "actor": actor,
        "status": status.value,
        "confirmation": None,
        "result": SearchResult.UNKNOWN.value,
        "request_prepared_is_not_sent": True,
        "sent_is_not_reply": True,
        "found_doc_is_not_auto_proof": True,
    }


def archive_reply_meaning(raw_status: str) -> str:
    """Не сливать разные отрицательные формулировки в один статус."""
    low = (raw_status or "").casefold()
    if "не поступал" in low or "не поступали" in low:
        return "not_deposited"
    if "недостаточн" in low:
        return "insufficient_data"
    if "не обнаруж" in low or "не найден" in low or "ничего нет" in low:
        return "not_found_in_search"
    return "unspecified_negative"


def invalidate_dependents_after_new_find(
    dependents: list[str],
) -> dict[str, str]:
    return {d: "needs_recheck" for d in dependents}


def reply_has_banned_lost_document_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_LOST_DOC_REPLY)
