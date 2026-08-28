"""Тесты очереди цитат для главной."""

from __future__ import annotations

from pathlib import Path

import sfrfr.core.site_reviews as sr


def test_review_text_rejects_hint_boilerplate() -> None:
    text = (
        "«Стало понятнее, какие документы собрать» или "
        "«Понравилось, что объяснили порядок действий».\n"
        "Без фамилии в публикации. Не пишите СНИЛС, паспорт, суммы и детали документов."
    )
    assert sr.review_text_issue(text) == "hint_text"
    assert sr.enqueue_quote(text=text, source="cf7", consent=True)["queued"] is False


def test_review_text_accepts_real_experience() -> None:
    text = (
        "Обращался в сервис Проверка стажа. Помогли сверить документы и "
        "подготовить план. Понятно, что в СФР подаю сам."
    )
    assert sr.review_text_issue(text) is None


def test_enqueue_without_publish_consent_is_feedback(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews_feedback.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)
    try:
        text = (
            "Обращался в сервис Проверка стажа. Помогли сверить документы и "
            "подготовить план. Понятно, что в СФР подаю сам."
        )
        queued = sr.enqueue_quote(text=text, source="cf7", consent=True, publish_consent=False)
        assert queued and queued["queued"] is True
        assert queued.get("status") == "feedback"
        assert sr.list_pending() == []
        assert sr.list_published() == []
    finally:
        if store.exists():
            store.unlink()


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
        queued = sr.enqueue_quote(
            text=text,
            source="site",
            consent=True,
            publish_consent=True,
            author_label="Андрей",
        )
        assert queued and queued["queued"] is True
        assert queued.get("status") == "pending"
        assert sr.list_published() == []
        assert len(sr.list_pending()) == 1
        item_id = queued["id"]
        assert sr.set_status(item_id, "published")["ok"] is True
        published = sr.list_published()
        assert len(published) == 1
        assert published[0]["text"].startswith("Обращался")
        assert published[0]["source"] == "site"
        assert published[0]["byline"] == "Андрей · 28 августа 2026"
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
            json={
                "text": text,
                "consent": True,
                "publish_consent": True,
                "author_label": "Андрей",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["queued"] is True
        assert body.get("status") == "pending"
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
                "publish_consent": True,
                "mail_already_sent": True,
                "source": "cf7",
                "author_label": "Андрей",
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


def test_moderate_sig_and_link(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews_mod.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)
    monkeypatch.setenv("PUBLIC_LEAD_TOKEN", "mod-secret-token")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    from sfrfr.api.routes import public_site_reviews as psr

    text = (
        "Обращался в сервис Проверка стажа. Помогли сверить документы и "
        "подготовить план. Понятно, что в СФР подаю сам."
    )
    queued = sr.enqueue_quote(
        text=text,
        source="site",
        consent=True,
        publish_consent=True,
        author_label="Андрей",
    )
    assert queued and queued["queued"]
    item_id = queued["id"]
    assert psr.parse_site_review_callback(f"srev:p:{item_id}") == (item_id, "published")
    assert psr.parse_site_review_callback(f"srev:r:{item_id}") == (item_id, "rejected")
    urls = psr.moderation_urls(item_id)
    assert "status=published" in urls["published"]
    assert "sig=" in urls["published"]
    from fastapi.testclient import TestClient

    from sfrfr.api import create_app

    try:
        client = TestClient(create_app())
        bad = client.get(
            "/api/public/site-reviews/moderate",
            params={"id": item_id, "status": "published", "sig": "bad"},
        )
        assert bad.status_code == 403
        sig = psr.moderate_sig(item_id, "published")
        ok = client.get(
            "/api/public/site-reviews/moderate",
            params={"id": item_id, "status": "published", "sig": sig},
        )
        assert ok.status_code == 200
        assert "Отзыв опубликован. Проверьте на сайте." in ok.text
        assert f"?review={item_id}#review-{item_id}" in ok.text
        assert "Обращался в сервис" in ok.text
        assert len(sr.list_published()) == 1
    finally:
        get_settings.cache_clear()
        if store.exists():
            store.unlink()


def test_site_review_public_url() -> None:
    from sfrfr.api.routes import public_site_reviews as psr

    uid = "abc-123"
    assert psr.site_review_public_url(uid) == (
        "https://proverkastaza.ru/otzyvy/?review=abc-123#review-abc-123"
    )


def test_enqueue_publish_requires_author_label(monkeypatch) -> None:
    store = Path("var") / "test_site_reviews_label.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(sr, "_DEFAULT_PATH", store)
    try:
        text = (
            "Обращался в сервис Проверка стажа. Помогли сверить документы и "
            "подготовить план. Понятно, что в СФР подаю сам."
        )
        blocked = sr.enqueue_quote(text=text, source="site", consent=True, publish_consent=True)
        assert blocked and blocked.get("reason") == "author_label_required"
        queued = sr.enqueue_quote(
            text=text,
            source="site",
            consent=True,
            publish_consent=True,
            author_label="Сергей, Архангельск",
        )
        assert queued and queued["queued"] is True
        assert sr.set_status(queued["id"], "published")["ok"] is True
        assert sr.list_published()[0]["byline"] == "Сергей, Архангельск · 28 августа 2026"
    finally:
        if store.exists():
            store.unlink()


def test_review_byline_empty_without_label() -> None:
    item = {
        "author_label": "",
        "published_at": "2026-08-28T07:25:21.830295+00:00",
    }
    assert sr.review_byline(item) == ""


def test_review_byline_custom_label() -> None:
    item = {
        "author_label": "Андрей, Архангельск",
        "published_at": "2026-08-28T07:25:21+00:00",
    }
    assert sr.review_byline(item) == "Андрей, Архангельск · 28 августа 2026"


def test_review_byline_date_only_when_published() -> None:
    item = {"author_label": "Иван", "created_at": "2026-01-15T12:00:00+00:00"}
    assert sr.review_byline(item) == "Иван · 15 января 2026"


def test_build_site_review_moderation_reply_published() -> None:
    from sfrfr.api.routes.public_site_reviews import build_site_review_moderation_reply

    text, attachments, text_format = build_site_review_moderation_reply(
        item_id="abc-123",
        review_status="published",
        quote="Хороший сервис",
        ok=True,
    )
    assert "Отзыв опубликован. Проверьте на сайте." in text
    review_url = (
        "[Открыть этот отзыв]"
        "(https://proverkastaza.ru/otzyvy/?review=abc-123#review-abc-123)"
    )
    assert review_url in text
    assert "abc-123" not in text.split("](")[0]
    assert attachments is not None
    assert text_format == "markdown"


def test_build_site_review_moderation_reply_rejected() -> None:
    from sfrfr.api.routes.public_site_reviews import build_site_review_moderation_reply

    text, attachments, text_format = build_site_review_moderation_reply(
        item_id="abc-123",
        review_status="rejected",
        quote="Спам",
        ok=True,
    )
    assert "Отзыв отклонён. Проверьте на сайте." in text
    assert "[Страница отзывов]" in text
    assert "?review=" not in text
    assert attachments is not None
    assert text_format == "markdown"
