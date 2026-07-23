"""Импорт диалогов → draft KnowledgeCase (с обезличиванием)."""

from __future__ import annotations

import re
from pathlib import Path

from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry
from sfrfr.ai.pii.depersonalize import depersonalize_text
from sfrfr.ai.schemas.knowledge_case import (
    ExpertAssessment,
    KnowledgeCase,
    KnowledgeQuality,
    SfrOutcome,
)

_DOC_HINTS: tuple[tuple[str, str], ...] = (
    ("илс", "ИЛС"),
    ("трудов", "трудовая книжка"),
    ("архивн", "архивная справка"),
    ("снилс", "СНИЛС (тип документа)"),
    ("паспорт", "паспорт (тип документа)"),
    ("справк", "справка"),
    ("военн", "военный билет"),
    ("заявлен", "заявление"),
)

_PROBLEM_HINTS: tuple[tuple[str, str], ...] = (
    ("стаж", "расхождение стажа"),
    ("илс", "расхождение ИЛС"),
    ("работодател", "работодатель / период"),
    ("едв", "ЕДВ"),
    ("перерасч", "перерасчёт пенсии"),
    ("фио", "расхождение ФИО"),
)

_OUTCOME_HINTS: tuple[tuple[str, SfrOutcome], ...] = (
    ("удовлетворен", SfrOutcome.GRANTED),
    ("одобрен", SfrOutcome.GRANTED),
    ("отказ", SfrOutcome.DENIED),
    ("отказан", SfrOutcome.DENIED),
    ("не завершен", SfrOutcome.PENDING),
    ("в работе", SfrOutcome.PENDING),
)


def read_dialog_text(path: Path) -> str:
    """Читает текстовый диалог; HTML — с грубым снятием тегов."""
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
    return text


def _read_dialog(path: Path) -> str:
    """Совместимость со старым именем."""
    return read_dialog_text(path)


def _guess_list(text: str, hints: tuple[tuple[str, str], ...]) -> list[str]:
    low = text.lower()
    found: list[str] = []
    for needle, label in hints:
        if needle in low and label not in found:
            found.append(label)
    return found


def _guess_outcome(text: str) -> SfrOutcome:
    low = text.lower()
    for needle, outcome in _OUTCOME_HINTS:
        if needle in low:
            return outcome
    return SfrOutcome.UNKNOWN


def _guess_problem(text: str) -> str:
    problems = _guess_list(text, _PROBLEM_HINTS)
    return "; ".join(problems) if problems else "не определено (draft)"


def _summary_from(text: str, *, max_len: int = 800) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1] + "…"


def import_dialog_to_case(
    path: Path,
    *,
    registry: KnowledgeCaseRegistry | None = None,
    client_name: str | None = None,
    case_id: str | None = None,
) -> KnowledgeCase:
    """
    Читает диалог (md/txt/json/html), обезличивает и сохраняет draft-кейс.

    PDF не парсится здесь — экспортируйте текст заранее.
    """
    registry = registry or KnowledgeCaseRegistry()
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".pdf":
        raise ValueError("PDF: сначала экспортируйте в TXT/MD/HTML, затем импортируйте")

    raw = _read_dialog(source)
    safe = depersonalize_text(raw, client_name=client_name)
    cid = case_id or registry.next_case_id()

    case = KnowledgeCase(
        case_id=cid,
        problem_type=_guess_problem(safe),
        documents=_guess_list(safe, _DOC_HINTS),
        discrepancy=(
            _guess_problem(safe)
            if "расхожд" in safe.lower() or "стаж" in safe.lower()
            else None
        ),
        prepared=_guess_list(
            safe,
            (
                ("заявлен", "заявление"),
                ("запрос", "запрос"),
                ("сопровод", "сопроводительное письмо"),
            ),
        ),
        sfr_outcome=_guess_outcome(safe),
        expert_assessment=ExpertAssessment.UNKNOWN,
        quality=KnowledgeQuality.DRAFT,
        source_file=source.name,
        summary=_summary_from(safe),
        notes="Автоимпорт: требуется проверка экспертом перед verified/template.",
    )
    registry.save(case)
    return case
