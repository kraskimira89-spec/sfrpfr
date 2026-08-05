"""Тесты portal pipeline run / findings schemas."""

from __future__ import annotations

from sfrfr.api.schemas.portal import FindingItem, PipelineRunResponse
from sfrfr.api.serializers import case_to_read
from sfrfr.core.case_store import CaseStore
from sfrfr.models.case_status import STATUS_LABELS_RU, CaseStatus


def test_pipeline_run_response_defaults() -> None:
    resp = PipelineRunResponse(ok=True, message="ok")
    assert resp.warning.startswith("Мы готовим документы и план")
    assert "Решение принимает СФР" in resp.warning
    assert resp.findings == []


def test_finding_item() -> None:
    item = FindingItem(type="missing_in_ils", detail="нет периода")
    assert item.severity == "info"


def test_case_to_read_includes_parity_fields() -> None:
    store = CaseStore()
    record = store.create(client_name="Тест", snils_masked="***-***-*** **")
    read = case_to_read(record)
    assert read.status is CaseStatus.INTAKE
    assert read.status_label == STATUS_LABELS_RU[CaseStatus.INTAKE]
    assert read.submission_instruction
    assert read.warning
    assert read.next_action
    assert read.analysis_notes is None


def test_case_context_roundtrip_analysis_notes() -> None:
    from sfrfr.ai.orchestrator import CaseContext
    from sfrfr.core.case_store import _ctx_from_dict, _ctx_to_dict
    from sfrfr.db.case_repository import CaseRepository

    ctx = CaseContext(case_id="c1", analysis_notes="Обоснование DeepSeek")
    restored = _ctx_from_dict(_ctx_to_dict(ctx))
    assert restored.analysis_notes == "Обоснование DeepSeek"
    snap = CaseRepository.snapshot_from_case_context(ctx)
    assert snap["analysis_notes"] == "Обоснование DeepSeek"
    read = case_to_read(
        CaseStore().create(client_name="Тест", snils_masked="***-***-*** **")
    )
    # свежий кейс без notes
    assert read.analysis_notes is None
