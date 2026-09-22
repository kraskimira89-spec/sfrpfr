"""Bot-owned funnel: findings, consent nudge, agree plan."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.intake import MaxIntakeRecord
from sfrfr.services.max_bot_funnel import (
    AGREE_PLAN_PAYLOAD,
    after_payment_confirmed,
    agree_plan_with_specialist,
    build_findings_message,
    handle_funnel_callback,
    notify_analysis_findings,
    nudge_consent_before_invoice,
    reset_funnel_cache,
)


def test_build_findings_message_bullets() -> None:
    text = build_findings_message(
        findings=[
            {"type": "missing_in_ils", "detail": "Период 1998–2001 не учтён в ИЛС", "severity": "warn"},
            {"type": "gap", "detail": "Есть разрыв стажа в трудовой", "severity": "warning"},
        ],
        missing_docs=["архивная справка по спорному периоду (если есть)"],
    )
    assert "1." in text
    assert "не учтён" in text.lower() or "илс" in text.lower()
    assert "архивная" in text.lower()
    assert "снилс" not in text.lower()
    assert "согласовать план" in text.lower()


def test_nudge_consent_when_no_consent(monkeypatch) -> None:
    reset_funnel_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.has_consent.return_value = False
    repo.get_case_row.return_value = {"id": "c-consent", "client_id": "cl1"}
    delivered: list[str] = []

    def _enqueue(**kwargs):
        delivered.append(kwargs.get("body") or "")
        return True

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.client_pdn_consent.ensure_case_consent_from_client",
            return_value=False,
        ),
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery", side_effect=_enqueue),
    ):
        out = nudge_consent_before_invoice(
            case_id="c-consent",
            max_user_id="55",
            intake=MaxIntakeRecord(id="1", max_user_id="55", status="started"),
        )
    assert out and out.get("nudged") == "consent_start"
    assert delivered and "начать" in delivered[0].lower()
    assert "кабинете" not in delivered[0].lower()


def test_nudge_offer_when_consent_ok(monkeypatch) -> None:
    reset_funnel_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.has_consent.return_value = True
    repo.get_case_row.return_value = {"id": "c-offer", "client_id": "cl1"}
    delivered: list[str] = []

    def _enqueue(**kwargs):
        delivered.append(kwargs.get("body") or "")
        return True

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.client_pdn_consent.ensure_case_consent_from_client",
            return_value=True,
        ),
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery", side_effect=_enqueue),
    ):
        out = nudge_consent_before_invoice(
            case_id="c-offer",
            max_user_id="55",
            intake=MaxIntakeRecord(id="1", max_user_id="55", status="started"),
        )
    assert out and out.get("nudged") == "offer"
    assert delivered and "условия" in delivered[0].lower()
    assert "согласие на обработку данных и принятие" not in delivered[0].lower()


def test_notify_findings_requires_diag_paid(monkeypatch) -> None:
    reset_funnel_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.get_case_row.return_value = {
        "id": "c2",
        "clients": {"max_user_id": "77"},
    }
    repo.list_orders.return_value = [{"package_code": "DIAG", "status": "draft"}]
    repo.get_pipeline_findings.return_value = [
        {"type": "missing_in_ils", "detail": "Период не отражён", "severity": "warn"}
    ]
    repo.list_documents.return_value = []

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.integrations.max.intake.get_intake_store",
            return_value=MagicMock(
                get_active=lambda _uid: MaxIntakeRecord(
                    id="1", max_user_id="77", status="started"
                )
            ),
        ),
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery") as enq,
    ):
        out = notify_analysis_findings(case_id="c2", force=False)
    assert out is None
    enq.assert_not_called()


def test_notify_findings_after_diag_paid(monkeypatch) -> None:
    reset_funnel_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.get_case_row.return_value = {
        "id": "c3",
        "clients": {"max_user_id": "78"},
    }
    repo.list_orders.return_value = [{"package_code": "DIAG", "status": "paid"}]
    repo.list_documents.return_value = [
        {"doc_type": "ils", "placement_suggestion": {"requirement_code": "ils"}},
        {"doc_type": "labor_book", "placement_suggestion": {"requirement_code": "labor_book"}},
    ]
    delivered: list[str] = []

    def _enqueue(**kwargs):
        delivered.append(kwargs.get("body") or "")
        return True

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.integrations.max.intake.get_intake_store",
            return_value=MagicMock(
                get_active=lambda _uid: MaxIntakeRecord(
                    id="1", max_user_id="78", status="started"
                )
            ),
        ),
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery", side_effect=_enqueue),
    ):
        out = notify_analysis_findings(
            case_id="c3",
            findings=[
                {
                    "type": "missing_in_ils",
                    "detail": "Период работы не отражён в ИЛС",
                    "severity": "warn",
                }
            ],
        )
    assert out and out.get("ok")
    assert delivered and "1." in delivered[0]
    assert "не отраж" in delivered[0].lower()


def test_agree_plan_creates_staff_task(monkeypatch) -> None:
    reset_funnel_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    store = MagicMock()
    rec = MaxIntakeRecord(id="1", max_user_id="88", status="started", case_id="c4")
    store.get_active.return_value = rec
    store.save = MagicMock()

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch("sfrfr.integrations.max.intake.get_intake_store", return_value=store),
        patch("sfrfr.services.finance_automation.ensure_staff_task", return_value=True) as task,
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery", return_value=True),
    ):
        out = agree_plan_with_specialist(case_id="c4", max_user_id="88", intake=rec)
        via_cb = handle_funnel_callback(
            case_id="c4",
            max_user_id="88",
            payload=AGREE_PLAN_PAYLOAD,
            intake=rec,
        )
    assert out.get("ok") and out.get("handed_to_operator")
    assert via_cb and via_cb.get("ok")
    assert task.called
    assert rec.status == "handed_to_operator"
    repo.update_next_action.assert_called()


def test_after_payment_diag_queues_next_step(monkeypatch) -> None:
    reset_funnel_cache()
    monkeypatch.setenv("MAX_BOT_OWNED_ENABLED", "1")
    get_settings.cache_clear()
    repo = MagicMock()
    repo.get_case_row.return_value = {
        "id": "c5",
        "clients": {"max_user_id": "90"},
    }
    bodies: list[str] = []

    def _enqueue(**kwargs):
        bodies.append(kwargs.get("body") or "")
        return True

    with (
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.integrations.max.intake.get_intake_store",
            return_value=MagicMock(
                get_active=lambda _uid: MaxIntakeRecord(
                    id="1", max_user_id="90", status="started"
                )
            ),
        ),
        patch("sfrfr.services.finance_automation.ensure_staff_task", return_value=True),
        patch("sfrfr.services.case_chat_delivery.enqueue_max_delivery", side_effect=_enqueue),
    ):
        out = after_payment_confirmed(case_id="c5", package_code="DIAG")
        again = after_payment_confirmed(case_id="c5", package_code="DIAG")
    assert out and out.get("ok")
    assert again is None  # idempotent
    assert bodies and "сверим" in bodies[0].lower()
