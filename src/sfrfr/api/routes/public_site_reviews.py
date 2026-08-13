"""Публичные цитаты для главной + очередь (без рейтинга)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from sfrfr.core.site_reviews import list_published

router = APIRouter()


@router.get("/site-reviews")
def public_site_reviews(limit: int = 6) -> dict[str, Any]:
    """Только published — для блока на главной."""
    items = list_published(limit=limit)
    return {
        "ok": True,
        "items": items,
        "note": "Рейтинг только на Яндекс Картах; здесь модерируемые цитаты.",
    }
