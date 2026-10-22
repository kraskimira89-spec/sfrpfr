"""Выпуск 2: staff «Проверить документы» — persistable job, extract, kit, без клиента."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.staff_document_check import (
    JOB_TYPE,
    STATUS_LABELS_RU,
    build_check_result,
    documents_fingerprint,
    enqueue_staff_document_check,
    is_embedded_text,
    next_staff_action,
    process_staff_document_check_job,
    summarize_for_staff,
)


def test_fingerprint_stable_and_order_independent() -> None:
    a = [
        {"id": "d2", "checksum_sha256": "bb"},
        {"id": "d1", "checksum_sha256": "aa"},
    ]
    b = [
        {"id": "d1", "checksum_sha256": "aa"},
        {"id": "d2", "checksum_sha256": "bb"},
    ]
    assert documents_fingerprint(a) == documents_fingerprint(b)
    assert documents_fingerprint(a) != documents_fingerprint(
        [{"id": "d1", "checksum_sha256": "aa"}, {"id": "d2", "checksum_sha256": "cc"}]
    )


def test_is_embedded_text_rejects_ocr_markers() -> None:
    assert is_embedded_text("Страховой стаж 12 лет")
    assert not is_embedded_text("")
    assert not is_embedded_text("[ocr_empty] PDF без текстового слоя")
    assert not is_embedded_text("[ocr_error] pypdf: broken")


def test_build_check_result_counts_and_dupes() -> None:
    docs = [
        {
            "id": "1",
            "filename": "ils.pdf",
            "doc_type": "ils",
            "checksum_sha256": "aaa",
            "original_available": True,
            "text_extracted": True,
            "needs_ocr": False,
            "needs_manual": False,
            "guessed_type": "ils",
            "text_sample": "индивидуального лицевого счёта",
        },
        {
            "id": "2",
            "filename": "ils_copy.pdf",
            "doc_type": "ils",
            "checksum_sha256": "aaa",
            "original_available": True,
            "text_extracted": True,
            "needs_ocr": False,
            "needs_manual": False,
            "guessed_type": "ils",
            "text_sample": "индивидуального лицевого счёта",
        },
        {
            "id": "3",
            "filename": "scan.png",
            "doc_type": None,
            "checksum_sha256": "bbb",
            "original_available": True,
            "text_extracted": False,
            "needs_ocr": True,
            "needs_manual": True,
            "guessed_type": "other",
            "text_sample": "",
        },
        {
            "id": "4",
            "filename": "missing.bin",
            "doc_type": None,
            "checksum_sha256": "ccc",
            "original_available": False,
            "text_extracted": False,
            "needs_ocr": False,
            "needs_manual": True,
            "guessed_type": "other",
            "text_sample": "",
        },
    ]
    result = build_check_result(
        documents=docs,
        missing_for_task=["трудовая / сведения о стаже"],
        ocr_allowed=False,
    )
    assert result["documents_checked"] == 4
    assert result["originals_available"] == 3
    assert result["text_extracted"] == 2
    assert result["needs_recognition"] == 1
    assert result["needs_manual_review"] == 2
    assert "ils" in result["types_found"]
    assert result["exact_duplicate_groups"] == 1
    assert result["missing_for_task"] == ["трудовая / сведения о стаже"]
    assert result["status"] == "needs_action"
    # Приоритет: сначала недоступные оригиналы (doc 4).
    assert "оригинал" in result["next_action"].lower()


def test_build_check_result_completed_when_kit_ok_no_ocr_needed() -> None:
    docs = [
        {
            "id": "1",
            "filename": "ils.pdf",
            "checksum_sha256": "a",
            "original_available": True,
            "text_extracted": True,
            "needs_ocr": False,
            "needs_manual": False,
            "guessed_type": "ils",
            "text_sample": "x",
        },
        {
            "id": "2",
            "filename": "tk.docx",
            "checksum_sha256": "b",
            "original_available": True,
            "text_extracted": True,
            "needs_ocr": False,
            "needs_manual": False,
            "guessed_type": "workbook",
            "text_sample": "y",
        },
    ]
    result = build_check_result(documents=docs, missing_for_task=[], ocr_allowed=False)
    assert result["status"] == "completed"
    assert "специалист" in result["next_action"].lower() or "диагност" in result[
        "next_action"
    ].lower()


def test_next_staff_action_priority() -> None:
    assert "оригинал" in next_staff_action(
        originals_missing=1, needs_ocr=0, missing_kit=["ИЛС"], needs_manual=0
    ).lower()
    assert "распознаван" in next_staff_action(
        originals_missing=0, needs_ocr=2, missing_kit=[], needs_manual=0
    ).lower()
    assert "трудовая" in next_staff_action(
        originals_missing=0, needs_ocr=0, missing_kit=["трудовая"], needs_manual=0
    ).lower()


def test_status_labels_cover_ui() -> None:
    for key in ("queued", "running", "completed", "needs_action", "failed"):
        assert key in STATUS_LABELS_RU
        assert STATUS_LABELS_RU[key]


def test_summarize_does_not_expose_old_pipeline_findings() -> None:
    summary = summarize_for_staff(
        {
            "status": "completed",
            "documents_checked": 2,
            "originals_available": 2,
            "text_extracted": 2,
            "needs_recognition": 0,
            "needs_manual_review": 0,
            "types_found": ["ils", "workbook"],
            "missing_for_task": [],
            "missing_explanations": [],
            "next_action": "Проверьте результат и перейдите к диагностике.",
            "exact_duplicate_groups": 0,
        }
    )
    assert "findings" not in summary
    assert "analysis_notes" not in summary
    assert "draft" not in summary
    assert summary["documents_checked"] == 2


@patch("sfrfr.services.staff_document_check.process_staff_document_check_job")
@patch("sfrfr.db.session.get_supabase_client")
def test_enqueue_does_not_process_inline(
    mock_sb: MagicMock, mock_process: MagicMock
) -> None:
    """Enqueue только ставит queued — без in-process thread (OOM/Failed to fetch)."""
    client = MagicMock()
    mock_sb.return_value = client
    jobs = MagicMock()
    docs_t = MagicMock()

    def table(name: str) -> MagicMock:
        if name == "staff_document_check_jobs":
            return jobs
        if name == "documents":
            return docs_t
        return MagicMock()

    client.table.side_effect = table
    docs_t.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "d1", "checksum_sha256": "aa", "storage_path": "a.pdf", "doc_type": "ils"}
    ]
    chain = jobs.select.return_value.eq.return_value.in_.return_value.eq.return_value
    chain.limit.return_value.execute.return_value.data = []
    jobs.insert.return_value.execute.return_value.data = [{"id": "new-job"}]
    with patch(
        "sfrfr.services.staff_document_check.documents_fingerprint", return_value="fp"
    ):
        out = enqueue_staff_document_check(
            case_id="00000000-0000-4000-8000-000000000001",
            actor_id="staff-1",
        )
    assert out["deduped"] is False
    assert out["status"] == "queued"
    mock_process.assert_not_called()
    # Prod: documents.cloud_status нет → 42703 → UI «Failed to fetch».
    select_cols = str(docs_t.select.call_args.args[0])
    assert "cloud_status" not in select_cols
    assert "checksum_sha256" in select_cols


@patch("sfrfr.db.session.get_supabase_client")
def test_enqueue_dedupes_active_same_fingerprint(mock_sb: MagicMock) -> None:
    client = MagicMock()
    mock_sb.return_value = client
    jobs = MagicMock()
    docs_t = MagicMock()

    def table(name: str) -> MagicMock:
        if name == "staff_document_check_jobs":
            return jobs
        if name == "documents":
            return docs_t
        return MagicMock()

    client.table.side_effect = table
    docs_t.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "d1", "checksum_sha256": "aa", "storage_path": "a.pdf", "doc_type": "ils"}
    ]
    chain = jobs.select.return_value.eq.return_value.in_.return_value.eq.return_value
    chain.limit.return_value.execute.return_value.data = [
        {"id": "existing-job", "status": "queued", "documents_fingerprint": "fp"}
    ]
    with patch(
        "sfrfr.services.staff_document_check.documents_fingerprint", return_value="fp"
    ):
        out = enqueue_staff_document_check(
            case_id="00000000-0000-4000-8000-000000000001",
            actor_id="staff-1",
        )
    assert out["job_id"] == "existing-job"
    assert out["deduped"] is True
    jobs.insert.assert_not_called()


@patch("sfrfr.services.staff_document_check._analyze_case_documents")
@patch("sfrfr.db.session.get_supabase_client")
def test_process_job_saves_result_no_client_notify(
    mock_sb: MagicMock, mock_analyze: MagicMock
) -> None:
    client = MagicMock()
    mock_sb.return_value = client
    jobs = MagicMock()
    client.table.return_value = jobs
    jobs.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "job-1",
            "case_id": "case-1",
            "status": "queued",
            "documents_fingerprint": "fp",
            "attempts": 0,
        }
    ]
    mock_analyze.return_value = build_check_result(
        documents=[
            {
                "id": "1",
                "filename": "ils.pdf",
                "checksum_sha256": "a",
                "original_available": True,
                "text_extracted": True,
                "needs_ocr": False,
                "needs_manual": False,
                "guessed_type": "ils",
                "text_sample": "x",
            },
            {
                "id": "2",
                "filename": "tk.pdf",
                "checksum_sha256": "b",
                "original_available": True,
                "text_extracted": True,
                "needs_ocr": False,
                "needs_manual": False,
                "guessed_type": "workbook",
                "text_sample": "y",
            },
        ],
        missing_for_task=[],
        ocr_allowed=False,
    )
    with patch(
        "sfrfr.services.staff_document_check.notify_kit_status_after_ingest",
        create=True,
    ) as notify:
        result = process_staff_document_check_job("job-1")
    assert result["status"] in {"completed", "needs_action"}
    assert "result" in result
    # обновления job: running + final
    assert jobs.update.call_count >= 2
    notify.assert_not_called()
    assert JOB_TYPE == "staff_docs_check"
