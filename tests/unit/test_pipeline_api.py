"""Тесты OCR + store + API upload/run."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sfrfr.ai.orchestrator import CaseContext, CaseOrchestrator
from sfrfr.api import create_app
from sfrfr.core.case_store import reset_case_store
from sfrfr.models.case_status import CaseStatus
from sfrfr.ocr.engine import extract_text


def test_extract_text_from_txt(tmp_path: Path) -> None:
    path = tmp_path / "ils.txt"
    path.write_text("Выписка ИЛС индивидуальный лицевой счет", encoding="utf-8")
    assert "ИЛС" in extract_text(path)


def test_orchestrator_ocr_from_document_paths(tmp_path: Path) -> None:
    ils = tmp_path / "ils.txt"
    labor = tmp_path / "labor.txt"
    ils.write_text("ИЛС СФР индивидуальный лицевой счет", encoding="utf-8")
    labor.write_text("Трудовая книжка стаж 01.01.2010 31.12.2015", encoding="utf-8")

    ctx = CaseContext(
        case_id="files",
        client_name="Тест",
        document_paths=[str(ils), str(labor)],
    )
    CaseOrchestrator().run_until(ctx, stop_at=CaseStatus.HUMAN_REVIEW)
    assert ctx.status is CaseStatus.HUMAN_REVIEW
    assert len(ctx.ocr_texts) == 2
    assert ctx.draft is not None


def test_orchestrator_blocks_intake_without_docs() -> None:
    ctx = CaseContext(case_id="empty")
    result = CaseOrchestrator().advance(ctx)
    assert result.ok is False
    assert ctx.status is CaseStatus.INTAKE


def test_orchestrator_blocks_without_ocr() -> None:
    ctx = CaseContext(case_id="empty", status=CaseStatus.DOCUMENTS_RECEIVED)
    result = CaseOrchestrator().advance(ctx)
    assert result.ok is False
    assert ctx.status is CaseStatus.DOCUMENTS_RECEIVED


def test_api_upload_and_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")

    client = TestClient(create_app())
    created = client.post(
        "/api/cases",
        json={"client_name": "Иванов", "snils_masked": "***-***-111 11", "consent_given": True},
    )
    assert created.status_code == 200
    case_id = created.json()["id"]

    files = {
        "file": ("ils.txt", "Выписка ИЛС индивидуальный лицевой счет".encode(), "text/plain"),
    }
    data = {"case_id": case_id}
    up = client.post("/api/documents/upload", data=data, files=files)
    assert up.status_code == 200
    assert up.json()["status"] == "documents_received"
    assert up.json()["document_count"] == 1

    files2 = {
        "file": (
            "labor.txt",
            "Трудовая книжка стаж с 01.01.2010 по 31.12.2015".encode(),
            "text/plain",
        ),
    }
    up2 = client.post("/api/documents/upload", data={"case_id": case_id}, files=files2)
    assert up2.status_code == 200

    ran = client.post(f"/api/cases/{case_id}/run")
    assert ran.status_code == 200
    body = ran.json()
    assert body["status"] == "human_review"
    assert body["draft"] is not None
    assert body["ocr_count"] == 2

    done = client.post(f"/api/cases/{case_id}/complete")
    assert done.status_code == 200
    assert done.json()["case"]["status"] == "completed"

    get_settings.cache_clear()
