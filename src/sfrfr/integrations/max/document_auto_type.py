"""Авто-определение типа документа из MAX: имя файла + содержимое (OCR/текст).

Чек не определяем никогда (gate #151): чек — только явная оплата через receipt-flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TYPE_ILS = "ils"
TYPE_WORKBOOK = "workbook"
TYPE_SPRAVKA = "spravka"
TYPE_OTHER = "other"

# Человекочитаемые имена для клиента (как говорят люди, не канцелярит).
CLIENT_LABELS_RU: dict[str, str] = {
    TYPE_ILS: "выписка о стаже",
    TYPE_WORKBOOK: "трудовая книжка",
    TYPE_SPRAVKA: "справка",
    TYPE_OTHER: "другой документ",
}

_SUMMARIES_RU: dict[str, str] = {
    TYPE_ILS: "Внутри обычно — периоды работы и сведения о стаже из Социального фонда.",
    TYPE_WORKBOOK: "Внутри обычно — записи о местах работы, должностях и датах.",
    TYPE_SPRAVKA: "Внутри обычно — подтверждение работы или стажа от работодателя или архива.",
    TYPE_OTHER: "Точно определить тип не получилось — специалист посмотрит файл сам.",
}

_NAME_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("илс", "сзи", "ils", "szv", "сзв", "лицевой"), TYPE_ILS),
    (("трудов", "trud", "workbook", "labor"), TYPE_WORKBOOK),
    (("справк", "spravk"), TYPE_SPRAVKA),
]

# «ТК» как отдельный токен в имени файла (ТК_Иванов.docx, ТК Лопакова…).
_TK_NAME_RE = re.compile(r"(^|[^0-9a-zа-яё])тк([^0-9a-zа-яё]|$)", re.IGNORECASE)

_TEXT_HINTS: list[tuple[tuple[str, ...], str]] = [
    (
        (
            "индивидуального лицевого",
            "сзи-илс",
            "состоянии индивидуального",
            "страхового стажа",
            "индивидуальном лицевом",
        ),
        TYPE_ILS,
    ),
    (
        (
            "трудовая книжка",
            "трудовой книжки",
            "сведения о трудовой деятельности",
            "сведения о работе",
            "запись в трудовой",
        ),
        TYPE_WORKBOOK,
    ),
    (("справка о стаже", "справка выдана", "настоящая справка"), TYPE_SPRAVKA),
]


@dataclass(frozen=True)
class GuessedDocument:
    doc_type: str
    confidence: float

    @property
    def label_ru(self) -> str:
        return CLIENT_LABELS_RU.get(self.doc_type, "другой документ")

    @property
    def summary_ru(self) -> str:
        return _SUMMARIES_RU.get(self.doc_type, _SUMMARIES_RU[TYPE_OTHER])

    @property
    def certain(self) -> bool:
        return self.doc_type != TYPE_OTHER and self.confidence >= 0.5

    def confirm_text(self) -> str:
        if self.certain:
            return (
                f"Похоже, вы прислали: {self.label_ru}. {self.summary_ru} Правильно?"
            )
        return (
            "Похоже, это другой документ — точно определить не получилось. "
            f"{self.summary_ru} Правильно?"
        )


def _match_hints(haystack: str, hints: list[tuple[tuple[str, ...], str]]) -> str | None:
    for keys, doc_type in hints:
        if any(k in haystack for k in keys):
            return doc_type
    return None


def _normalize_ru(value: str) -> str:
    return (value or "").lower().replace("ё", "е")


def guess_document_type(*, filename: str, text: str = "") -> GuessedDocument:
    """Сначала содержимое (сильнее), потом имя файла. Чек не возвращаем."""
    clean_text = _normalize_ru(
        re.sub(r"\[ocr_(?:error|empty)[^\]]*\]", "", text or "", flags=re.I)
    )
    if clean_text.strip():
        hit = _match_hints(clean_text, _TEXT_HINTS)
        if hit:
            return GuessedDocument(hit, 0.8)
        try:
            from sfrfr.ai.agents.classifier import classify_document

            result = classify_document(clean_text[:4000])
            mapped = {"ils": TYPE_ILS, "labor_book": TYPE_WORKBOOK}.get(
                str(result.document_type.value)
            )
            if mapped and result.confidence >= 0.5:
                return GuessedDocument(mapped, float(result.confidence))
        except Exception:  # noqa: BLE001 — классификатор не должен ронять приём файла
            pass
    name = _normalize_ru(filename or "")
    hit = _match_hints(name, _NAME_HINTS)
    if hit:
        return GuessedDocument(hit, 0.65)
    if _TK_NAME_RE.search(name):
        return GuessedDocument(TYPE_WORKBOOK, 0.7)
    return GuessedDocument(TYPE_OTHER, 0.2)


def guess_from_bytes(*, filename: str, data: bytes) -> GuessedDocument:
    """Текст/OCR по байтам (best-effort) + имя файла. Ошибки не роняют приём."""
    text = ""
    if data:
        try:
            from sfrfr.ocr.engine import extract_text_from_bytes

            text = extract_text_from_bytes(data, filename) or ""
        except Exception:  # noqa: BLE001
            text = ""
    return guess_document_type(filename=filename, text=text)
