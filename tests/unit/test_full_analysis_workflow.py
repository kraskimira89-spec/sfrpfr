"""Версии подробного разбора: отправка ≠ согласование; этап закрыт только approve."""

from __future__ import annotations

from pathlib import Path

from sfrfr.services.full_analysis_workflow import (
    FullAnalysisWorkflow,
    stage_work_from_state,
)


def test_create_version_and_status_strip(tmp_path: Path) -> None:
    wf = FullAnalysisWorkflow(root=tmp_path)
    v = wf.create_version(
        "case-1",
        markdown="# Разбор\n\nПериод 2004.\n\nРешение принимает СФР.",
        source="ai",
    )
    assert v["n"] == 1
    assert v["status"] == "draft"
    state = wf.get_state("case-1")
    assert state["status_strip"]["file"] == "готов"
    assert state["status_strip"]["reviewed"] == "нет"
    assert state["status_strip"]["sent"] == "нет"
    assert state["status_strip"]["approved"] == "нет"
    assert state["status_strip"]["delivery_error"] is None


def test_sent_is_not_approved(tmp_path: Path) -> None:
    wf = FullAnalysisWorkflow(root=tmp_path)
    v = wf.create_version("c", markdown="x" * 130 + "\nРешение принимает СФР.", source="ai")
    wf.mark_reviewed("c", v["id"])
    wf.mark_sent("c", v["id"], channel="email")
    state = wf.get_state("c")
    assert state["current"]["status"] == "sent"
    assert state["status_strip"]["sent"] == "да"
    assert state["status_strip"]["approved"] == "нет"
    work = stage_work_from_state(state)
    assert work["state"] == "ready"
    assert work["releaseReady"] == "no"


def test_approved_closes_stage(tmp_path: Path) -> None:
    wf = FullAnalysisWorkflow(root=tmp_path)
    v = wf.create_version("c", markdown="ok text " * 20, source="template")
    wf.mark_reviewed("c", v["id"])
    wf.mark_sent("c", v["id"], channel="yadisk")
    wf.record_decision("c", v["id"], decision="approved")
    state = wf.get_state("c")
    assert state["current"]["status"] == "approved"
    work = stage_work_from_state(state)
    assert work["state"] == "delivered"
    assert work["releaseReady"] == "yes"


def test_remarks_requires_new_version(tmp_path: Path) -> None:
    wf = FullAnalysisWorkflow(root=tmp_path)
    v1 = wf.create_version("c", markdown="v1 " * 40, source="ai")
    wf.mark_reviewed("c", v1["id"])
    wf.mark_sent("c", v1["id"], channel="email")
    wf.record_decision("c", v1["id"], decision="remarks", remarks="Неверная дата 2005")
    v2 = wf.create_version(
        "c",
        markdown="v2 исправлено " * 20,
        source="staff",
        based_on=v1["id"],
    )
    assert v2["n"] == 2
    state = wf.get_state("c")
    assert state["current"]["id"] == v2["id"]
    assert state["current"]["status"] == "draft"
    assert state["versions"][0]["status"] == "superseded"
    work = stage_work_from_state(state)
    assert work["state"] != "delivered"


def test_delivery_error_not_marked_sent(tmp_path: Path) -> None:
    wf = FullAnalysisWorkflow(root=tmp_path)
    v = wf.create_version("c", markdown="err " * 40, source="ai")
    wf.mark_reviewed("c", v["id"])
    wf.mark_delivery_error("c", v["id"], error="smtp_auth_failed")
    state = wf.get_state("c")
    assert state["current"]["status"] == "staff_reviewed"
    assert state["status_strip"]["sent"] == "нет"
    assert state["status_strip"]["delivery_error"] == "smtp_auth_failed"


def test_client_revision_attached(tmp_path: Path) -> None:
    wf = FullAnalysisWorkflow(root=tmp_path)
    v = wf.create_version("c", markdown="rev " * 40, source="ai")
    wf.attach_client_revision("c", v["id"], document_id="doc-99", note="правки ФИО")
    state = wf.get_state("c")
    assert state["current"]["client_revision_document_id"] == "doc-99"
    assert "правки ФИО" in (state["current"].get("client_revision_note") or "")
