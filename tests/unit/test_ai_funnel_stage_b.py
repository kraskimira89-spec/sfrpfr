"""Этап B (ТЗ-35): трудовая всегда HITL; LLM не идёт дальше, пока HITL открыт."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sfrfr.ai.orchestrator import CaseContext, CaseOrchestrator
from sfrfr.models.case_status import CaseStatus
from sfrfr.services import document_ingest_v2
from sfrfr.services.document_ingest import is_labor_document, run_ingest_pipeline


def test_is_labor_document_codes() -> None:
    assert is_labor_document("labor_book") is True
    assert is_labor_document("labor") is True
    assert is_labor_document("workbook") is True
    assert is_labor_document(None, requirement_code="labor_book") is True
    assert is_labor_document(None, requirement_code="трудовая книжка") is True
    assert is_labor_document("ils") is False
    assert is_labor_document("passport") is False


def test_labor_book_always_requires_ingest_review_even_with_good_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Трудовая с нормальным OCR всё равно уходит в HITL."""
    monkeypatch.setattr(
        document_ingest_v2,
        "_extract_pages",
        lambda data, filename, detected_mime: [
            {
                "page": 1,
                "source": "text_layer",
                "char_count": 400,
                "engine": None,
                "error": None,
                "text": "Трудовая книжка. Принят 01.01.2010 ООО Тест. Уволен 31.12.2015.",
            }
        ],
    )
    monkeypatch.setattr(
        document_ingest_v2,
        "get_settings",
        lambda: SimpleNamespace(ocr_engine="auto", tesseract_lang="rus+eng"),
    )

    result = document_ingest_v2.run_document_ingest_v2(
        data=b"%PDF-1.4 labor",
        filename="trudovaya.pdf",
        content_type="application/pdf",
        doc_type="labor_book",
        active_scenarios=set(),
        duplicate_checksum=False,
        case_id="case-labor",
        document_id="doc-labor",
    )

    assert result["ingest_review_required"] is True
    assert result["ingest_status"] == "manual_review"
    assert result["manifest"]["needs_ingest_review"] is True
    assert "трудов" in (result.get("progress_message") or "").lower()


def test_run_ingest_pipeline_marks_labor_for_hitl() -> None:
    preview = "Трудовая книжка: приём 01.01.2010 увольнение 31.12.2015"
    data = b"%PDF-1.4\n" + preview.encode("utf-8")
    result = run_ingest_pipeline(
        data=data,
        filename="labor.pdf",
        content_type="application/pdf",
        doc_type="labor_book",
        preview_text=preview,
        active_scenarios=set(),
        duplicate_checksum=False,
    )
    assert result["ingest_review_required"] is True
    assert result["ingest_status"] == "manual_review"


def test_orchestrator_blocks_classify_while_hitl_pending() -> None:
    ctx = CaseContext(
        case_id="hitl-gate",
        status=CaseStatus.OCR_DONE,
        ocr_texts=["Трудовая книжка текст"],
        block_llm_until_hitl=True,
    )
    result = CaseOrchestrator().advance(ctx)
    assert result.ok is True
    assert ctx.status is CaseStatus.OCR_DONE
    assert "HITL" in result.message or "специалист" in result.message.lower()
    assert ctx.classifications == []


def test_pipeline_run_stays_on_human_review_when_hitl_open() -> None:
    """Supabase /run: при открытом HITL — human_review и явный текст, без «анализа готов»."""
    from sfrfr.db.case_repository import CaseRepository

    class _Repo:
        def __init__(self) -> None:
            self.status_updates: list[tuple[str, str]] = []
            self.audit_actions: list[str] = []

        def _case(self, case_id: str):
            status_now = self.status_updates[-1][1] if self.status_updates else "documents_received"
            return {
                "id": case_id,
                "pipeline_status": status_now,
                "documents": [
                    {
                        "id": "d1",
                        "doc_type": "ils",
                        "storage_path": "ils.pdf",
                        "ingest_review_required": False,
                    },
                    {
                        "id": "d2",
                        "doc_type": "labor_book",
                        "storage_path": "labor.pdf",
                        "ingest_review_required": True,
                    },
                ],
            }

        def update_case_status(self, case_id, status_value, actor_id, *, notify=True):
            self.status_updates.append((case_id, status_value))
            return {"id": case_id, "pipeline_status": status_value}

        def audit(self, case_id, actor_id, action) -> None:
            self.audit_actions.append(action)

        def get_pipeline_findings(self, case_id: str):
            return []

        def get_pipeline_analysis_notes(self, case_id: str):
            return None

        def get_pipeline_draft(self, case_id: str):
            return None

    repo = _Repo()
    result = CaseRepository.request_pipeline_run(repo, "case-1", "user-1")  # type: ignore[arg-type]
    assert result["ok"] is True
    assert result["pipeline_status"] == "human_review"
    assert result.get("hitl_pending") is True
    assert "специалист" in result["message"].lower() or "проверк" in result["message"].lower()
    assert repo.status_updates[-1][1] == "human_review"


def test_pipeline_run_rejects_llm_skip_while_hitl_if_forced_analysis_status() -> None:
    """Нельзя «перескочить» HITL, если кто-то пытается оставить classify при открытом review."""
    from sfrfr.db.case_repository import CaseRepository

    class _Repo:
        def __init__(self) -> None:
            self.status_updates: list[tuple[str, str]] = []
            self.audit_actions: list[str] = []

        def _case(self, case_id: str):
            status_now = self.status_updates[-1][1] if self.status_updates else "ocr_done"
            return {
                "id": case_id,
                "pipeline_status": status_now,
                "documents": [
                    {
                        "id": "d2",
                        "doc_type": "labor_book",
                        "storage_path": "labor.pdf",
                        "ingest_review_required": True,
                    },
                    {
                        "id": "d1",
                        "doc_type": "ils",
                        "storage_path": "ils.pdf",
                        "ingest_review_required": False,
                    },
                ],
            }

        def update_case_status(self, case_id, status_value, actor_id, *, notify=True):
            self.status_updates.append((case_id, status_value))
            return {"id": case_id, "pipeline_status": status_value}

        def audit(self, case_id, actor_id, action) -> None:
            self.audit_actions.append(action)

        def get_pipeline_findings(self, case_id: str):
            return [{"type": "should_not", "detail": "leak"}]

        def get_pipeline_analysis_notes(self, case_id: str):
            return "secret notes"

        def get_pipeline_draft(self, case_id: str):
            return {"body": "no"}

    repo = _Repo()
    result = CaseRepository.request_pipeline_run(repo, "case-1", "user-1")  # type: ignore[arg-type]
    assert result["hitl_pending"] is True
    assert result["pipeline_status"] == "human_review"
    assert result["findings"] == []
    assert result["analysis_notes"] is None
    assert result["draft"] is None
