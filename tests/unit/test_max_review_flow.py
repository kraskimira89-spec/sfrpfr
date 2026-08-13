"""Тесты MAX review flow callbacks."""

from __future__ import annotations

from pathlib import Path

import sfrfr.integrations.max.review_flow as review_flow


def test_review_start_and_answers(monkeypatch) -> None:
    store = Path("var") / "test_max_review_sessions.json"
    if store.exists():
        store.unlink()
    monkeypatch.setattr(review_flow, "_DEFAULT_PATH", store)
    monkeypatch.setattr(
        review_flow,
        "build_review_draft",
        lambda answers, improve=None: {
            "ok": True,
            "draft": "Тестовый черновик отзыва.",
            "source": "template",
            "publish_url": "https://proverkastaza.ru/otzyv/",
        },
    )

    try:
        start = review_flow.handle_review_callback(user_id="u1", payload="review:start")
        assert start is not None
        assert "помогли" in start["text"].lower()

        a1 = review_flow.handle_review_callback(user_id="u1", payload="review:a:helped:plan")
        assert a1 is not None
        assert "понятно" in a1["text"].lower()

        a2 = review_flow.handle_review_callback(user_id="u1", payload="review:a:clarity:yes")
        assert a2 is not None

        a3 = review_flow.handle_review_callback(user_id="u1", payload="review:a:convenient:max")
        assert a3 is not None
        assert "Тестовый черновик" in a3["text"]
        assert a3["attachments"]
    finally:
        if store.exists():
            store.unlink()
