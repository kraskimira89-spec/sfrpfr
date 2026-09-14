"""Тесты portal pipeline run / findings schemas."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

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


class _RunRepo:
    """Мок репозитория для контракта клиентского /run (без Supabase)."""

    def __init__(self, case: dict) -> None:
        self._case_row = case
        self.status_updates: list[tuple[str, str]] = []
        self.audit_actions: list[str] = []

    def _case(self, case_id: str):  # type: ignore[no-untyped-def]
        row = dict(self._case_row)
        row.setdefault("id", case_id)
        if self.status_updates:
            row["pipeline_status"] = self.status_updates[-1][1]
        return row

    def update_case_status(self, case_id, status_value, actor_id, *, notify=True):  # type: ignore[no-untyped-def]
        self.status_updates.append((case_id, status_value))
        return {"id": case_id, "pipeline_status": status_value}

    def audit(self, case_id, actor_id, action) -> None:  # type: ignore[no-untyped-def]
        self.audit_actions.append(action)

    def get_pipeline_findings(self, case_id: str):  # type: ignore[no-untyped-def]
        return []

    def get_pipeline_analysis_notes(self, case_id: str):  # type: ignore[no-untyped-def]
        return None

    def get_pipeline_draft(self, case_id: str):  # type: ignore[no-untyped-def]
        return None


def _doc(doc_type: str) -> dict:
    return {"id": f"doc-{doc_type}", "doc_type": doc_type, "storage_path": f"{doc_type}.pdf"}


def test_pipeline_run_requires_full_required_docs() -> None:
    """Клиентский /run: без полного обязательного набора — 400 с русским текстом."""
    from sfrfr.db.case_repository import CaseRepository

    repo = _RunRepo({"pipeline_status": "intake", "documents": [_doc("ils")]})
    with pytest.raises(HTTPException) as exc:
        CaseRepository.request_pipeline_run(repo, "case-1", "user-1")  # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert "не хватает" in str(exc.value.detail)
    assert "трудовая" in str(exc.value.detail)


def test_pipeline_run_advances_documents_received_to_human_review() -> None:
    """Клиентский /run: полный набор (ИЛС + трудовая) → human_review, findings в ответе."""
    from sfrfr.db.case_repository import CaseRepository

    repo = _RunRepo(
        {
            "pipeline_status": "documents_received",
            "documents": [_doc("ils"), _doc("labor")],
        }
    )
    result = CaseRepository.request_pipeline_run(repo, "case-1", "user-1")  # type: ignore[arg-type]
    assert result["ok"] is True
    assert result["pipeline_status"] == "human_review"
    assert "проверку специалисту" in result["message"]
    assert repo.status_updates == [("case-1", "human_review")]
    assert repo.audit_actions == ["pipeline_run_requested"]


def test_require_consent_gates_client_run() -> None:
    """Consent-гейт: клиент без согласия получает 403 до запуска проверки."""
    from sfrfr.api.routes.portal import _require_consent_for_upload
    from sfrfr.db.case_repository import CaseRepository

    class _NoConsentRepo(_RunRepo):
        def has_consent(self, case_id: str) -> bool:
            return False

    repo = _NoConsentRepo({"pipeline_status": "intake", "documents": [_doc("ils"), _doc("labor")]})
    with pytest.raises(HTTPException) as exc:
        _require_consent_for_upload(repo, "case-1")  # type: ignore[arg-type]
    assert exc.value.status_code == 403
    assert "consent" in str(exc.value.detail)
