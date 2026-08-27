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
        queued = sr.enqueue_quote(text=text, source="site", consent=True)
        assert queued and queued["queued"] is True
        assert sr.list_published() == []
        assert len(sr.list_pending()) == 1
        item_id = queued["id"]
        assert sr.set_status(item_id, "published")["ok"] is True
        published = sr.list_published()
        assert len(published) == 1
        assert published[0]["text"].startswith("Обращался")
        assert published[0]["source"] == "site"
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


def test_public_post_site_review_queues(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews_api.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)
    monkeypatch.setattr(
        "sfrfr.api.routes.public_site_reviews._require_captcha",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "sfrfr.api.routes.public_site_reviews.notify_site_review_queued",
        lambda **_kwargs: {"email": {"ok": True}, "max": {"ok": True}},
    )
    from fastapi.testclient import TestClient

    from sfrfr.api import create_app

    try:
        client = TestClient(create_app())
        text = (
            "Обращался в сервис Проверка стажа. Помогли сверить документы и "
            "подготовить план. Понятно, что в СФР подаю сам."
        )
        response = client.post(
            "/api/public/site-reviews",
            json={"text": text, "consent": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["queued"] is True
        assert len(sr.list_pending()) == 1
    finally:
        if store.exists():
            store.unlink()


def test_public_post_site_review_trusted_wp_skips_captcha(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews_cf7.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)
    monkeypatch.setenv("PUBLIC_LEAD_TOKEN", "test-wp-token")
    called = {"captcha": 0, "notify": 0}

    def _cap(**_kwargs):
        called["captcha"] += 1

    def _notify(**kwargs):
        called["notify"] += 1
        assert kwargs.get("send_email") is False
        assert kwargs.get("source") == "cf7"
        return {"email": None, "max": {"ok": True}}

    monkeypatch.setattr(
        "sfrfr.api.routes.public_site_reviews._require_captcha",
        _cap,
    )
    monkeypatch.setattr(
        "sfrfr.api.routes.public_site_reviews.notify_site_review_queued",
        _notify,
    )
    from fastapi.testclient import TestClient

    from sfrfr.api import create_app
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        text = (
            "Обращался в сервис Проверка стажа. Помогли сверить документы и "
            "подготовить план. Понятно, что в СФР подаю сам."
        )
        response = client.post(
            "/api/public/site-reviews",
            json={
                "text": text,
                "consent": True,
                "mail_already_sent": True,
                "source": "cf7",
            },
            headers={"X-Public-Lead-Token": "test-wp-token"},
        )
        assert response.status_code == 200
        assert called["captcha"] == 0
        assert called["notify"] == 1
    finally:
        get_settings.cache_clear()
        if store.exists():
            store.unlink()
