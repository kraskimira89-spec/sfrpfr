"""Пост-диагностика: рекомендации и отдельные обращения в СФР."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.core.config import get_settings
from sfrfr.services.max_post_diagnosis import (
    brief_recommendations_from_findings,
    build_docs_invoice_after_appeals_text,
    build_post_diagnosis_next_steps_text,
    maybe_send_post_diagnosis_next_steps,
    reset_post_diagnosis_cache,
    sanitize_finding_line,
)


def test_sanitize_strips_snils_like() -> None:
    assert "123" not in sanitize_finding_line("СНИЛС 123-456-789 00 не учтён период")
    assert "…" in sanitize_finding_line("СНИЛС 123-456-789 00 не учтён период")


def test_brief_from_findings() -> None:
    rows = [
        {"type": "discrepancy", "severity": "warn", "detail": "Период 1998–1999 не отражён в ИЛС"},
        {"type": "info", "severity": "info", "detail": "Общая справка"},
        {"type": "gap", "detail": "Нет архивной справки по северному стажу"},
    ]
    out = brief_recommendations_from_findings(rows, limit=3)
    assert any("1998" in x for x in out)
    assert any("северн" in x.lower() for x in out)


def test_next_steps_text_mentions_separate_appeals() -> None:
    text = build_post_diagnosis_next_steps_text(
        recommendations=["Период не отражён в ИЛС", "Нужна архивная справка"]
    )
    assert "отдельных" in text.lower() or "несколько простых" in text.lower()
    assert "составить обращения" in text.lower()
    assert "5000" not in text and "5 000" not in text


def test_invoice_text_after_consent() -> None:
    text = build_docs_invoice_after_appeals_text(amount=5000, cabinet_url="https://example/")
    assert "5000" in text or "5 000" in text
    assert "одному вопросу" in text.lower() or "по одному" in text.lower()


def test_post_diagnosis_does_not_create_order(monkeypatch) -> None:
    repo = MagicMock()
    repo.has_consent.return_value = True
    repo.get_case_row.return_value = {
        "id": "c1",
        "b2c_status": "diagnostic_paid",
        "clients": {"max_user_id": "99"},
        "diagnosis_delivered": True,
    }
    repo.list_orders.return_value = [{"package_code": "DIAG", "status": "paid"}]
    repo.get_pipeline_findings.return_value = [
        {"type": "discrepancy", "detail": "Расхождение по периоду 2001"}
    ]
    reset_post_diagnosis_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery", return_value=True) as enq,
    ):
        out = maybe_send_post_diagnosis_next_steps(
            case_id="c1",
            case={
                "id": "c1",
                "b2c_status": "diagnostic_paid",
                "clients": {"max_user_id": "99"},
                "diagnosis_delivered": True,
            },
        )
    assert out and out.get("sent")
    repo.create_order.assert_not_called()
    assert enq.called
    body = enq.call_args.kwargs.get("body") or ""
    assert "обращен" in body.lower()
    assert "5 000" not in body and "5000" not in body
