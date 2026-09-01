"""ТЗ-09: уведомления о статусе + единый словарь лейблов."""

from __future__ import annotations

from sfrfr.integrations.client_channels.notifications import (
    cabinet_case_url,
    format_status_change_message,
    notification_channel_links,
)
from sfrfr.models.case_status import human_case_status, status_labels_payload


def test_cabinet_case_url_canonical() -> None:
    url = cabinet_case_url("11111111-2222-3333-4444-555555555555")
    assert "/cases/11111111-2222-3333-4444-555555555555" in url
    assert "?case=" not in url


def test_notification_links_use_cases_path() -> None:
    payload = notification_channel_links(
        preferred_channel="web_cabinet",
        max_linked=True,
        case_id="11111111-2222-3333-4444-555555555555",
    )
    web = next(item for item in payload["links"] if item["channel"] == "web_cabinet")
    assert "/cases/" in web["url"]
    assert payload["links"][0]["channel"] == "web_cabinet"


def test_status_message_website_cabinet_only() -> None:
    text = format_status_change_message(
        status_value="human_review",
        preferred_channel="max_miniapp",
        max_linked=True,
        case_id="11111111-2222-3333-4444-555555555555",
    )
    assert "На проверке специалиста" in text
    assert "единый чат" in text.lower()
    assert "Мини-приложение MAX" not in text
    assert "Веб-кабинет" not in text


def test_shared_status_labels_payload() -> None:
    payload = status_labels_payload()
    assert payload["labels"]["human_review"] == "На проверке специалиста"
    assert "result_confirmed" in payload["b2c"]
    assert payload["senior"]["in_review"] == "Идёт проверка"
    assert human_case_status("ocr_done", "lead") == "Идёт проверка"
    assert human_case_status("intake", "lead") == "Нужны документы"


def test_soft_review_ask_message_is_optional_and_once() -> None:
    from sfrfr.integrations.client_channels.notifications import (
        format_soft_review_ask_message,
        maybe_send_soft_review_ask,
    )

    text = format_soft_review_ask_message(
        review_url="https://yandex.ru/maps/org/proverka_stazha/82469923047/reviews/?add-review=true"
    )
    assert "необязательно" in text.lower() or "не хотите" in text.lower()
    assert "больше не будем напоминать" in text.lower()
    assert "кнопкам" in text.lower() or "черновик" in text.lower()
    assert "5 звёзд" not in text.lower()
    assert "скидк" not in text.lower()
    # URL публикации — в кнопках MAX, не обязательно в тексте
    assert "add-review=true" not in text

    skipped = maybe_send_soft_review_ask(
        case_id="11111111-2222-3333-4444-555555555555",
        status_value="draft_ready",
        client={"max_user_id": "1"},
    )
    assert skipped["skipped"] is True
    assert skipped["reason"] == "not_completed"

    no_max = maybe_send_soft_review_ask(
        case_id="11111111-2222-3333-4444-555555555555",
        status_value="completed",
        client={},
    )
    assert no_max["skipped"] is True
    assert no_max["reason"] == "no_max_user"


def test_soft_review_ask_idempotent(monkeypatch) -> None:
    from sfrfr.integrations.client_channels import notifications as n

    monkeypatch.setattr(n, "_review_ask_already_sent", lambda _cid: True)
    again = n.maybe_send_soft_review_ask(
        case_id="11111111-2222-3333-4444-555555555555",
        status_value="completed",
        client={"max_user_id": "99"},
    )
    assert again["skipped"] is True
    assert again["reason"] == "already_sent"


def test_openapi_has_representatives_routes() -> None:
    from sfrfr.api import create_app

    paths = set(create_app().openapi()["paths"])
    assert "/api/portal/admin/cases/{case_id}/representatives" in paths
    assert "/api/portal/cases/{case_id}/representatives" in paths
