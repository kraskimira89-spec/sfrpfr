"""DOCX обращения из подтверждённых полей draft дела (без выдуманных фактов)."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from docx import Document


def build_appeal_docx_bytes(
    *,
    title: str,
    body: str,
    case_ref: str | None = None,
) -> bytes:
    """Собрать простой DOCX: заголовок + абзацы body. Без ПДн сверх переданного текста."""
    doc = Document()
    heading = (title or "Проект обращения").strip() or "Проект обращения"
    doc.add_heading(heading, level=1)
    if case_ref:
        doc.add_paragraph(f"Дело (служебный ref): {case_ref}")
    doc.add_paragraph(
        "Документ подготовлен сервисом для самостоятельной подачи клиентом. "
        "Решение принимает СФР."
    )
    text = (body or "").strip()
    if not text:
        doc.add_paragraph("(Текст черновика пуст — заполните проект в карточке дела.)")
    else:
        for block in text.split("\n"):
            doc.add_paragraph(block if block.strip() else "")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def draft_payload_from_case(case: dict[str, Any]) -> tuple[str, str]:
    draft = case.get("draft") if isinstance(case.get("draft"), dict) else {}
    title = str(draft.get("title") or case.get("draft_title") or "Проект обращения")
    body = str(draft.get("body") or case.get("draft_body") or "")
    return title, body
