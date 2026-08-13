"""Тесты очереди цитат для главной."""

from __future__ import annotations

from pathlib import Path

import sfrfr.core.site_reviews as sr


def test_enqueue_and_publish(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)

    try:
        assert sr.enqueue_quote(text="коротко", source="anketa", consent=True)["queued"] is False
        text = (
            "Обращался в сервис Проверка стажа. Помогли сверить документы и "
            "подготовить план. Понятно, что в СФР подаю сам."
        )
        queued = sr.enqueue_quote(text=text, source="anketa", consent=True)
        assert queued and queued["queued"] is True
        assert sr.list_published() == []
        assert len(sr.list_pending()) == 1
        item_id = queued["id"]
        assert sr.set_status(item_id, "published")["ok"] is True
        published = sr.list_published()
        assert len(published) == 1
        assert published[0]["text"].startswith("Обращался")
    finally:
        if store.exists():
            store.unlink()


def test_no_consent_skips(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews2.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)
    try:
        assert (
            sr.enqueue_quote(
                text="Достаточно длинный безопасный текст для цитаты на сайте сервиса проверки.",
                consent=False,
            )
            is None
        )
    finally:
        if store.exists():
            store.unlink()
