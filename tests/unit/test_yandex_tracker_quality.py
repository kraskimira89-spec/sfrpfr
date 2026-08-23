"""Unit-тесты санитарного фильтра и case_ref для Tracker STAZH."""

from __future__ import annotations

from sfrfr.integrations.yandex_tracker import (
    case_ref_for,
    find_pii_violations,
    sanitize_description,
    summary_for_issue,
    tags_for_issue,
)


def test_case_ref_stable_and_short() -> None:
    a = case_ref_for("11111111-1111-1111-1111-111111111111", secret="salt-a")
    b = case_ref_for("11111111-1111-1111-1111-111111111111", secret="salt-a")
    c = case_ref_for("11111111-1111-1111-1111-111111111111", secret="salt-b")
    assert a == b
    assert len(a) == 12
    assert a != c
    assert "-" not in a


def test_find_pii_blocks_phone_email_snils_uuid_urls() -> None:
    text = (
        "Клиент +7 916 123-45-67, mail@example.com, "
        "СНИЛС 123-456-789-01, "
        "дело aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee "
        "https://cabinet.proverkastaza.ru/x"
    )
    hits = find_pii_violations(text)
    assert "phone" in hits
    assert "email" in hits
    assert "snils" in hits
    assert "case_uuid" in hits
    assert "cabinet_url" in hits


def test_sanitize_redacts() -> None:
    out = sanitize_description("Позвонить +79161234567 на test@mail.ru")
    assert "+79161234567" not in out
    assert "test@mail.ru" not in out
    assert "[phone]" in out
    assert "[email]" in out


def test_tags_and_summary() -> None:
    tags = tags_for_issue(
        issue_type="sla_incident",
        direction="ops",
        source="cabinet",
        channel="max",
        repeatability="recurring",
    )
    assert "type:sla_incident" in tags
    assert "ch:max" in tags
    assert "rep:recurring" in tags
    s = summary_for_issue(issue_type="bug", case_ref="abcdef123456", title_hint="sync fail")
    assert "abcdef123456" in s
    assert "Ошибка" in s or "bug" in s.lower() or "[" in s
