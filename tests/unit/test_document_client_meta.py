"""Метаданные документа из OCR-превью для таблицы в кабинете."""

from __future__ import annotations

from sfrfr.api.routes.portal import _meta_from_preview, _normalize_doc_date


def test_normalize_doc_date() -> None:
    assert _normalize_doc_date("5.08.2024") == "05.08.2024"
    assert _normalize_doc_date("12/01/23") == "12.01.2023"


def test_meta_from_ils_preview() -> None:
    preview = (
        "Сведения о состоянии индивидуального лицевого счёта. "
        "Выписка от 15.03.2024 по запросу гражданина."
    )
    inner_date, inner_title = _meta_from_preview(
        preview,
        filename="scan.pdf",
        type_label=None,
    )
    assert inner_date == "15.03.2024"
    assert inner_title == "Выписка ИЛС"


def test_meta_prefers_type_label() -> None:
    _date, title = _meta_from_preview(
        "любой текст от 01.01.2020",
        filename="x.pdf",
        type_label="Трудовая книжка",
    )
    assert title == "Трудовая книжка"
