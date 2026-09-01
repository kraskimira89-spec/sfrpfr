"""Долговечная очередь обработки документов для ingest v2."""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sfrfr.db.session import get_supabase_client
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET
from sfrfr.services.document_ingest import sha256_hex
from sfrfr.services.document_ingest_v2 import run_document_ingest_v2
from sfrfr.services.document_requirements import active_scenario_codes
from sfrfr.services.document_upload import ensure_document_group, find_duplicate_checksum
from sfrfr.services.file_security import (
    AntivirusResult,
    antivirus_allows,
    scan_file_bytes,
    validate_file_bytes,
)

logger = logging.getLogger(__name__)

QUARANTINE_PREFIX = "quarantine"
VERIFIED_PREFIX = "verified"
ARTIFACT_PREFIX = "ingest"


def create_quarantine_document(
    *,
    case_id: str,
    filename: str,
    data: bytes,
    content_type: str,
    doc_type: str | None,
    uploaded_by: str | None,
    upload_batch_id: str | None = None,
    document_group_id: str | None = None,
    page_index: int | None = None,
    page_order: int = 0,
    upload_source: str = "cabinet",
    client_declared_signed: bool = False,
    scenario_rows: list[Any] | None = None,
) -> dict[str, Any]:
    """Сохранить оригинал в quarantine и поставить job, не запуская OCR в запросе."""
    allow_signed = (doc_type or "").strip().lower() in {
        "client_signed_application",
        "client_signed_appeal",
    }
    security = validate_file_bytes(
        data,
        filename=filename,
        declared_content_type=content_type,
        allow_signed=allow_signed,
    )
    if not security.ok:
        raise ValueError(security.client_message or "Файл не прошёл проверку.")
    checksum = sha256_hex(data)
    duplicate = find_duplicate_checksum(case_id, checksum)
    document_id = str(uuid4())
    safe_name = Path(filename or "document").name
    group_id = document_group_id
    if document_group_id or page_index is not None:
        group_id = ensure_document_group(
            case_id=case_id,
            group_id=document_group_id,
            doc_type=doc_type,
            requirement_code=None,
            title=safe_name,
        )
    quarantine_path = f"{QUARANTINE_PREFIX}/{case_id}/{document_id}/{safe_name}"
    client = get_supabase_client()
    try:
        client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
            quarantine_path,
            data,
            {
                "content-type": security.detected_mime or content_type,
                "x-upsert": "false",
            },
        )
        row = {
            "id": document_id,
            "case_id": case_id,
            "storage_path": quarantine_path,
            "doc_type": doc_type,
            "uploaded_by": uploaded_by,
            "upload_batch_id": upload_batch_id,
            "document_group_id": group_id,
            "page_index": page_index,
            "page_order": page_order,
            "upload_source": upload_source,
            "checksum_sha256": checksum,
            "duplicate_checksum": duplicate,
            "mime_verified": security.detected_mime,
            "ingest_status": "security_check",
            "progress_percent": 5,
            "current_stage": "security_check",
            "progress_message": "Файл получен. Проверяем безопасность.",
            "client_declared_signed": client_declared_signed,
            "antivirus_status": "pending",
            "ingest_review_required": False,
        }
        response = client.table("documents").insert(row).execute()
        saved = response.data[0] if response.data else row
    except Exception:
        try:
            client.storage.from_(PRIVATE_STORAGE_BUCKET).remove([quarantine_path])
        except Exception:  # noqa: BLE001
            pass
        raise

    job_id = enqueue_document_ingest_job(
        case_id=case_id,
        document_id=document_id,
    )
    return {**saved, "job_id": job_id}


def enqueue_document_ingest_job(
    *,
    case_id: str,
    document_id: str,
) -> str:
    """Поставить один идемпотентный job на документ."""
    client = get_supabase_client()
    job_id = str(uuid4())
    payload = {
        "id": job_id,
        "case_id": case_id,
        "document_id": document_id,
        "job_type": "ingest",
        "status": "queued",
        "progress_percent": 5,
        "current_stage": "security_check",
    }
    try:
        response = client.table("document_ingest_jobs").insert(payload).execute()
        if response.data:
            return str(response.data[0].get("id") or job_id)
    except Exception as exc:  # noqa: BLE001
        existing = (
            client.table("document_ingest_jobs")
            .select("id")
            .eq("document_id", document_id)
            .eq("job_type", "ingest")
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing:
            return str(existing[0]["id"])
        raise exc
    return job_id


def process_document_ingest_job(job_id: str) -> dict[str, Any]:
    """Обработать job после quarantine; безопасно повторяется для queued job."""
    client = get_supabase_client()
    job = _one(
        client.table("document_ingest_jobs").select("*").eq("id", job_id).limit(1).execute().data
    )
    if not job:
        raise LookupError(f"ingest job not found: {job_id}")
    if str(job.get("status")) == "completed":
        return job
    document_id = str(job.get("document_id") or "")
    row = _one(
        client.table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("case_id", str(job.get("case_id") or ""))
        .limit(1)
        .execute()
        .data
    )
    if not row:
        _update_job(client, job_id, {"status": "failed", "last_error": "document_not_found"})
        raise LookupError(f"document not found: {document_id}")

    attempts = int(job.get("attempts") or 0) + 1
    _update_job(
        client,
        job_id,
        {
            "status": "running",
            "attempts": attempts,
            "progress_percent": 10,
            "current_stage": "security_check",
            "locked_by": _worker_id(),
            "locked_at": _now(),
        },
    )
    try:
        source_path = str(row.get("storage_path") or "")
        data = client.storage.from_(PRIVATE_STORAGE_BUCKET).download(source_path)
        filename = Path(source_path).name or "document"
        antivirus = (
            AntivirusResult("clean", "manual_expert_approval")
            if str(row.get("security_reason") or "") == "manual_expert_approval"
            else scan_file_bytes(data, filename)
        )
        security_fields = {
            "antivirus_status": antivirus.status,
            "security_reason": antivirus.reason,
            "security_checked_at": _now(),
        }
        if antivirus.status == "infected":
            _update_document(
                client,
                document_id,
                {
                    **security_fields,
                    "ingest_status": "blocked_security",
                    "progress_percent": 100,
                    "current_stage": "blocked_security",
                    "progress_message": "Файл заблокирован проверкой безопасности.",
                },
            )
            _update_job(
                client,
                job_id,
                {
                    "status": "failed",
                    "progress_percent": 100,
                    "current_stage": "blocked_security",
                    "last_error": "antivirus_detected_threat",
                },
            )
            return {"status": "blocked_security", "document_id": document_id}
        if not antivirus_allows(antivirus):
            _update_document(
                client,
                document_id,
                {
                    **security_fields,
                    "ingest_status": "manual_review",
                    "progress_percent": 25,
                    "current_stage": "security_review",
                    "progress_message": (
                        "Файл получен. Специалист завершит проверку безопасности перед обработкой."
                    ),
                },
            )
            _update_job(
                client,
                job_id,
                {
                    "status": "needs_review",
                    "progress_percent": 25,
                    "current_stage": "security_review",
                    "last_error": antivirus.reason,
                },
            )
            return {"status": "needs_review", "document_id": document_id}

        _update_document(
            client,
            document_id,
            {
                **security_fields,
                "progress_percent": 30,
                "current_stage": "quality_check",
                "progress_message": "Безопасность подтверждена. Проверяем читаемость.",
            },
        )
        scenarios = _scenario_codes(client, str(row.get("case_id") or ""))
        result = run_document_ingest_v2(
            data=data,
            filename=filename,
            content_type=str(row.get("mime_verified") or ""),
            doc_type=row.get("doc_type"),
            active_scenarios=scenarios,
            duplicate_checksum=bool(row.get("duplicate_checksum")),
            case_id=str(row.get("case_id") or ""),
            document_id=document_id,
        )
        verified_path = _verified_path(row, filename)
        _store_verified_copy(
            client,
            source_path,
            verified_path,
            data,
            str(row.get("mime_verified") or ""),
        )
        extracted_path, manifest_path = _store_artifacts(
            client,
            case_id=str(row.get("case_id") or ""),
            document_id=document_id,
            extracted_text=str(result.get("extracted_text") or ""),
            manifest=dict(result.get("manifest") or {}),
        )
        fields = {
            **security_fields,
            "storage_path": verified_path,
            "content_preview": str(result.get("extracted_text") or "")[:2000] or None,
            "ingest_status": result.get("ingest_status") or "under_review",
            "progress_percent": 100,
            "current_stage": result.get("current_stage") or result.get("ingest_status"),
            "progress_message": result.get("progress_message"),
            "placement_suggestion": result.get("placement_suggestion"),
            "quality_report": result.get("quality_report"),
            "ingest_review_required": bool(result.get("ingest_review_required")),
            "ingest_artifact_path": extracted_path,
            "ingest_manifest_path": manifest_path,
            "ingest_engine": result.get("ingest_engine"),
            "page_count": result.get("page_count"),
        }
        _update_document(client, document_id, fields)
        _store_labor_drafts(
            client,
            case_id=str(row.get("case_id") or ""),
            document_id=document_id,
            group_id=row.get("document_group_id"),
            drafts=list(result.get("labor_timeline_drafts") or []),
        )
        if result.get("ingest_status") != "blocked_security":
            _mirror_document_after_security(
                case_id=str(row.get("case_id") or ""),
                filename=filename,
                data=data,
                doc_type=row.get("doc_type"),
            )
            _process_payment_receipt(
                case_id=str(row.get("case_id") or ""),
                document_id=document_id,
                filename=filename,
                data=data,
                actor_id=row.get("uploaded_by"),
                doc_type=row.get("doc_type"),
            )
        job_status = "needs_review" if fields["ingest_review_required"] else "completed"
        _update_job(
            client,
            job_id,
            {
                "status": job_status,
                "progress_percent": 100,
                "current_stage": fields["current_stage"],
                "last_error": None,
            },
        )
        return {"status": job_status, "document_id": document_id}
    except Exception as exc:  # noqa: BLE001
        logger.exception("document ingest job failed: %s", job_id)
        failed = attempts >= int(job.get("max_attempts") or 3)
        _update_document(
            client,
            document_id,
            {
                "ingest_status": "manual_review" if failed else "security_check",
                "progress_percent": 25 if failed else 10,
                "current_stage": "manual_review" if failed else "security_check",
                "progress_message": (
                    "Обработка требует проверки специалистом."
                    if failed
                    else "Повторяем проверку файла."
                ),
                "ingest_review_required": failed,
            },
        )
        _update_job(
            client,
            job_id,
            {
                "status": "needs_review" if failed else "queued",
                "progress_percent": 25 if failed else 10,
                "current_stage": "manual_review" if failed else "security_check",
                "last_error": type(exc).__name__,
                "available_at": _future_retry(attempts),
            },
        )
        return {"status": "needs_review" if failed else "queued", "document_id": document_id}


def process_next_document_ingest_job() -> dict[str, Any] | None:
    """Забрать один доступный job; используется systemd worker-ом."""
    client = get_supabase_client()
    jobs = (
        client.table("document_ingest_jobs")
        .select("id")
        .eq("status", "queued")
        .lte("available_at", _now())
        .order("created_at")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not jobs:
        return None
    return process_document_ingest_job(str(jobs[0]["id"]))


def run_worker(*, once: bool = False, poll_seconds: float = 3.0) -> None:
    """Цикл одного процесса без параллельной обработки тяжёлых OCR-задач."""
    while True:
        result = process_next_document_ingest_job()
        if once or result is not None:
            if once:
                return
        time.sleep(poll_seconds)


def _store_verified_copy(
    client: Any,
    source_path: str,
    verified_path: str,
    data: bytes,
    content_type: str,
) -> None:
    if source_path == verified_path:
        return
    client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
        verified_path,
        data,
        {"content-type": content_type or "application/octet-stream", "x-upsert": "true"},
    )
    client.storage.from_(PRIVATE_STORAGE_BUCKET).remove([source_path])


def _store_artifacts(
    client: Any,
    *,
    case_id: str,
    document_id: str,
    extracted_text: str,
    manifest: dict[str, Any],
) -> tuple[str, str]:
    base = f"{ARTIFACT_PREFIX}/{case_id}/{document_id}"
    extracted_path = f"{base}/extracted.md"
    manifest_path = f"{base}/ingest.json"
    client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
        extracted_path,
        extracted_text.encode("utf-8"),
        {"content-type": "text/markdown; charset=utf-8", "x-upsert": "true"},
    )
    client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False).encode("utf-8"),
        {"content-type": "application/json", "x-upsert": "true"},
    )
    return extracted_path, manifest_path


def _store_labor_drafts(
    client: Any,
    *,
    case_id: str,
    document_id: str,
    group_id: str | None,
    drafts: list[dict[str, Any]],
) -> None:
    if not drafts:
        return
    rows = []
    for draft in drafts:
        rows.append(
            {
                **draft,
                "id": draft.get("id") or str(uuid4()),
                "case_id": case_id,
                "document_id": document_id,
                "document_group_id": group_id,
            }
        )
    client.table("labor_timeline_drafts").insert(rows).execute()


def _mirror_document_after_security(
    *,
    case_id: str,
    filename: str,
    data: bytes,
    doc_type: str | None,
) -> None:
    try:
        from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe

        mirror_case_document_safe(case_id, filename, data, doc_type=doc_type)
    except Exception as exc:  # noqa: BLE001
        logger.info("document yandex disk mirror skipped: %s", exc)


def _process_payment_receipt(
    *,
    case_id: str,
    document_id: str,
    filename: str,
    data: bytes,
    actor_id: str | None,
    doc_type: str | None,
) -> None:
    if str(doc_type or "").strip().lower() != "payment_receipt":
        return
    try:
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.ocr import extract_text_from_bytes
        from sfrfr.services.payment_receipt import handle_uploaded_receipt

        handle_uploaded_receipt(
            CaseRepository(),
            case_id=case_id,
            ocr_text=extract_text_from_bytes(data, filename),
            document_id=document_id,
            actor_id=actor_id,
            doc_type=doc_type,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("payment receipt check skipped: %s", exc)


def _scenario_codes(client: Any, case_id: str) -> set[str]:
    rows = (
        client.table("case_scenarios")
        .select("scenario_code, active")
        .eq("case_id", case_id)
        .execute()
        .data
        or []
    )
    return active_scenario_codes(rows)


def _verified_path(row: dict[str, Any], filename: str) -> str:
    return f"{VERIFIED_PREFIX}/{row.get('case_id')}/{row.get('id')}/{Path(filename).name}"


def _update_document(client: Any, document_id: str, fields: dict[str, Any]) -> None:
    client.table("documents").update(fields).eq("id", document_id).execute()


def _update_job(client: Any, job_id: str, fields: dict[str, Any]) -> None:
    fields = {**fields, "updated_at": _now()}
    client.table("document_ingest_jobs").update(fields).eq("id", job_id).execute()


def _one(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    return rows[0] if rows else None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _future_retry(attempts: int) -> str:
    delay = min(60, max(3, 2**attempts))
    return (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"
