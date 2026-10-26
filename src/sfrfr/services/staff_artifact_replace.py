"""Замена сгенерированных артефактов (draft / notes) из загруженного файла."""

from __future__ import annotations

from io import BytesIO


def text_from_upload(*, filename: str, data: bytes) -> str:
    """Извлечь текст из .txt/.md/.csv или .docx. Иначе ValueError."""
    name = (filename or "").lower()
    if name.endswith((".txt", ".md", ".csv")) or not name:
        return data.decode("utf-8", errors="replace").strip()
    if name.endswith(".docx"):
        from docx import Document

        doc = Document(BytesIO(data))
        parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n".join(parts).strip()
    raise ValueError("Нужен .txt, .md, .csv или .docx")
