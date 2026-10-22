"""Краткий разбор → soft-ask → оффер 3 000 ₽ (без обхода старым diag:yes)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from test_max_intake import _cb, _setup

import sfrfr.services.brief_analysis as ba
from sfrfr.core.config import get_settings
from sfrfr.integrations.max import diag_choice as dc
from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store
from sfrfr.services import diag_offer_gate as gate

_KIT = [
    {"id": "d1", "doc_type": "ils", "checksum_sha256": "a" * 64},
    {"id": "d2", "doc_type": "workbook", "checksum_sha256": "b" * 64},
]


def _rec(**answers: str) -> MaxIntakeRecord:
    return MaxIntakeRecord(
        id="r1",
        max_user_id="u1",
        case_id="c1",
        q_answers=dict(answers),
    )


def test_no_analysis_means_no_offer_flags() -> None:
    flags = ba.gate_flags_from_intake(_rec())
    assert flags["has_completed_brief_analysis"] is False
    d = gate.evaluate_diag_offer(
        **flags,
        settings=SimpleNamespace(max_diag_offer_ef_open=True),
    )
    assert not d.allowed
    assert d.reason == gate.DENY_NO_ANALYSIS


def test_no_discrepancy_no_offer() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(problem="Всё в порядке, просто проверка"),
        pipeline_findings=[],
    )
    assert result.ok
    assert not result.has_justified_discrepancy
    assert "не выявила очевидных расхождений" in result.summary.lower()


def test_questionnaire_themes_are_careful_possible() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(problem="Не учли северный стаж"),
        pipeline_findings=[],
    )
    assert result.has_justified_discrepancy
    blob = result.summary.lower()
    assert "возможн" in blob
    assert "не учли северный стаж" not in blob or "возможн" in blob
    assert "гарант" not in blob
    assert "перерасчёт" not in blob


def test_findings_drive_discrepancy() -> None:
    result = ba.compute_brief_analysis(
        documents=_KIT,
        intake=_rec(problem="ок"),
        pipeline_findings=[
            {"type": "missing_in_ils", "detail": "Период есть в трудовой, нет в ИЛС"},
        ],
    )
    assert result.has_justified_discrepancy
    assert "илс" in result.summary.lower() or "трудов" in result.summary.lower()


def test_discrepancy_without_consent_no_pay_button_path(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(q, "save_questionnaire", lambda **_kw: True)
    handle_max_update(
        {
            "callback": {
                "user": {"user_id": 501, "first_name": "А", "last_name": "Б"},
                "chat_id": 1,
                "payload": "start_dialog",
            }
        },
        bot=bot,
    )
    for upd in (
        _cb(501, "q:exp:gt20"),
        {"message": {"sender": {"user_id": 501}, "body": {"text": "+79091234567"}}},
        _cb(501, q.SKIP_EMAIL),
        {"message": {"sender": {"user_id": 501}, "body": {"text": "Не учли стаж"}}},
    ):
        handle_max_update(upd, bot=bot)
    rec = get_intake_store().get_active("501")
    assert rec is not None
    result = ba.compute_brief_analysis(documents=_KIT, intake=rec, pipeline_findings=[])
    ba.persist_brief_to_intake(rec, result)
    ba.mark_summary_shown(rec)
    # Есть расхождения и summary, но нет согласия на подробный разбор.
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    bot.sent.clear()
    res = handle_max_update(_cb(501, dc.YES), bot=bot)
    assert res.action == "diag_yes_gated"
    assert started == []
    get_settings.cache_clear()


def test_full_path_soft_ask_then_offer(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "1")
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    store = get_intake_store()
    rec = store.upsert_started("502")
    rec.case_id = "case-502"
    rec.q_answers = {"problem": "Не учли северный стаж"}
    store.save(rec)
    result = ba.compute_brief_analysis(documents=_KIT, intake=rec, pipeline_findings=[])
    ba.persist_brief_to_intake(rec, result)
    ba.mark_summary_shown(rec)
    assert ba.is_detail_pending(rec)

    bot.sent.clear()
    res = handle_max_update(_cb(502, ba.DETAIL_YES), bot=bot)
    assert res.action == "diag_detail_yes_offer"
    assert "3 000" in (res.reply or "")
    assert "подробн" in (res.reply or "").lower()

    # Оплата: handler без Supabase не резолвит case_id — проверяем handle напрямую.
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    rec2 = get_intake_store().get_active("502")
    assert rec2 is not None
    replies: list[str] = []

    def _reply(msg: str, _kb) -> None:
        replies.append(msg)

    action, _body = dc.handle(
        rec2,
        _reply,
        payload=dc.YES,
        case_id="case-502",
        max_user_id="502",
        log_event=lambda _m: None,
    )
    assert action == "diag_yes"
    assert started and started[0]["case_id"] == "case-502"
    get_settings.cache_clear()


def test_old_diag_yes_without_brief_still_gated(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "1")
    get_settings.cache_clear()
    store = get_intake_store()
    rec = store.upsert_started("503")
    rec.case_id = "case-503"
    store.save(rec)
    started: list[dict] = []
    monkeypatch.setattr(
        dc, "start_diag_payment", lambda **kw: started.append(kw) or {"ok": True}
    )
    res = handle_max_update(_cb(503, dc.YES), bot=bot)
    assert res.action == "diag_yes_gated"
    assert started == []
    get_settings.cache_clear()


def test_run_brief_delivers_soft_ask(monkeypatch) -> None:
    delivered: list[dict] = []

    class _Repo:
        def list_documents(self, _cid: str):
            return list(_KIT)

        def get_pipeline_findings(self, _cid: str):
            return []

        def get_case_row(self, _cid: str):
            return {"clients": {"max_user_id": "u9"}}

    store = MagicMock()
    rec = MaxIntakeRecord(
        id="r9",
        max_user_id="u9",
        case_id="c9",
        q_answers={"problem": "Не учли стаж на севере"},
    )
    store.get_active.return_value = rec
    store.save.side_effect = lambda r: None

    monkeypatch.setattr(
        "sfrfr.db.case_repository.CaseRepository", lambda: _Repo()
    )
    monkeypatch.setattr(
        "sfrfr.integrations.max.intake.get_intake_store", lambda: store
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.fetch_recent_case_messages",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_context.staff_dialog_active",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.case_chat_delivery.enqueue_max_delivery",
        lambda **kw: delivered.append(kw) or True,
    )

    out = ba.run_brief_after_kit(case_id="c9", max_user_id="u9")
    assert out is not None and out.has_justified_discrepancy
    assert delivered
    assert delivered[0].get("attachments")
    assert "3 000" in delivered[0]["body"] or "подробн" in delivered[0]["body"].lower()


def test_ef_kill_switch_still_blocks(monkeypatch) -> None:
    monkeypatch.setenv("MAX_DIAG_OFFER_EF_OPEN", "0")
    get_settings.cache_clear()
    rec = _rec(
        **{
            ba.STATUS_KEY: ba.STATUS_COMPLETED,
            ba.OK_KEY: "1",
            ba.CURRENT_KEY: "1",
            ba.DISCREPANCY_KEY: "1",
            ba.SUMMARY_SHOWN_KEY: "1",
            ba.DETAIL_CONSENT_KEY: "1",
        }
    )
    d = gate.evaluate_diag_offer(**ba.gate_flags_from_intake(rec))
    assert d.reason == gate.DENY_EF_CLOSED
    get_settings.cache_clear()
