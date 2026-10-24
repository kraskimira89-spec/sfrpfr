"""Staff «Проверить документы»: persistable job (extract/classify/dupes/kit).

Без уведомлений клиенту. OCR/сканы — только при staff_docs_check_allow_ocr.
Юр.анализ LLM в этом модуле не запускается.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sfrfr.services.staff_document_check_result import (
    ACTIVE_STATUSES,
    JOB_TYPE,
    STATUS_LABELS_RU,
    attach_honest_brief,
    build_check_result,
    documents_fingerprint,
    is_embedded_text,
    next_staff_action,
    summarize_for_staff,
)

logger = logging.getLogger(__name__)

# Re-export для тестов и API.
__all__ = [
    "ACTIVE_STATUSES",
    "JOB_TYPE",
    "STATUS_LABELS_RU",
    "build_check_result",
    "documents_fingerprint",
    "enqueue_staff_document_check",
    "get_case_document_check",
    "is_embedded_text",
    "next_staff_action",
    "process_next_staff_document_check_job",
    "process_staff_document_check_job",
    "process_staff_document_check_job_safe",
    "summarize_for_staff",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _worker_id() -> str:
    return f"staff-docs-check:{os.getpid()}"


def _ocr_allowed() -> bool:
    from sfrfr.core.config import get_settings

    settings = get_settings()
    return bool(getattr(settings, "staff_docs_check_allow_ocr", False))


def _filename_of(doc: dict[str, Any]) -> str:
    for key in ("filename", "storage_path", "local_path", "ingest_artifact_path"):
        raw = str(doc.get(key) or "").strip()
        if raw:
            return Path(raw).name
    return "document"


def _extract_embedded_from_bytes(data: bytes, filename: str) -> str:
    """Только текстовый слой PDF/DOCX; без raster OCR."""
    import tempfile

    from sfrfr.ocr.engine import _extract_docx, _sniff_suffix

    suffix = _sniff_suffix(data, filename)
    if suffix in {".txt", ".md", ".csv"}:
        return data.decode("utf-8", errors="ignore").strip()
    if suffix == ".docx":
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as fh:
                fh.write(data)
                tmp = Path(fh.name)
            return _extract_docx(tmp)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
    if suffix == ".pdf":
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
                fh.write(data)
                tmp = Path(fh.name)
            from pypdf import PdfReader

            reader = PdfReader(str(tmp))
            chunks = [(page.extract_text() or "").strip() for page in reader.pages]
            return "\n".join(c for c in chunks if c).strip()
        except Exception as exc:  # noqa: BLE001
            return f"[ocr_error] pdf: {exc}"
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
    return ""


def _analyze_one(
    doc: dict[str, Any],
    *,
    ocr_allowed: bool,
) -> dict[str, Any]:
    from sfrfr.integrations.max.attachment_lifecycle import document_is_staff_openable
    from sfrfr.integrations.max.document_auto_type import guess_document_type

    filename = _filename_of(doc)
    available = document_is_staff_openable(doc)
    existing = str(doc.get("content_preview") or "")
    text = existing if is_embedded_text(existing) else ""
    needs_ocr = False
    needs_manual = False

    if available and not text:
        try:
            from sfrfr.services.ocr_source_resolver import resolve_ocr_bytes_ctx

            with resolve_ocr_bytes_ctx(doc, case_id=str(doc.get("case_id") or "")) as resolved:
                data = resolved.data
                if ocr_allowed:
                    from sfrfr.ocr.engine import extract_text_from_bytes

                    text = extract_text_from_bytes(data, filename) or ""
                else:
                    text = _extract_embedded_from_bytes(data, filename)
                    if not is_embedded_text(text):
                        suffix = Path(filename).suffix.lower()
                        if suffix in {
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".tif",
                            ".tiff",
                            ".bmp",
                            ".webp",
                        }:
                            needs_ocr = True
                            text = ""
                        elif suffix == ".pdf" or (data[:4] == b"%PDF"):
                            needs_ocr = True
                            text = ""
                        else:
                            needs_manual = True
                            text = ""
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "staff_docs_check extract skipped doc=%s err=%s",
                str(doc.get("id") or "")[:8],
                type(exc).__name__,
            )
            needs_manual = True

    text_ok = is_embedded_text(text)
    if available and not text_ok and not needs_ocr:
        needs_manual = True

    guessed = guess_document_type(filename=filename, text=text if text_ok else "")
    if guessed.doc_type == "other" and text_ok:
        needs_manual = True
    if not available:
        needs_manual = True

    return {
        "id": str(doc.get("id") or ""),
        "filename": filename,
        "doc_type": doc.get("doc_type"),
        "checksum_sha256": doc.get("checksum_sha256"),
        "original_available": available,
        "text_extracted": text_ok,
        "needs_ocr": needs_ocr,
        "needs_manual": needs_manual,
        "guessed_type": guessed.doc_type,
        "text_sample": (text[:200] if text_ok else ""),
    }


def _honest_brief_for_case(
    *,
    case_id: str,
    docs: list[dict[str, Any]],
    repo: Any,
) -> dict[str, Any] | None:
    """Честное бесплатное резюме для UI staff — без ложного «анализ идёт»."""
    try:
        from sfrfr.services import brief_analysis as ba
    except Exception:  # noqa: BLE001
        return None
    findings: list[dict[str, Any]] = []
    try:
        findings = list(repo.get_pipeline_findings(case_id) or [])
    except Exception:  # noqa: BLE001
        findings = []
    problem = ""
    try:
        row = repo.get_case_row(case_id) or {}
        problem = str(row.get("problem_text") or "").strip()
    except Exception:  # noqa: BLE001
        problem = ""
    intake = None
    if problem:
        intake = type(
            "I",
            (),
            {
                "q_answers": {"problem": problem},
                "problem_type": None,
                "goal": None,
            },
        )()
    result = ba.compute_brief_analysis(
        documents=docs,
        intake=intake,
        pipeline_findings=findings,
    )
    return ba.honest_brief_ui_payload(result)


def _orders_offer_gate(repo: Any, case_id: str) -> tuple[bool, bool]:
    """(block_offer, status_unknown).

    pending оплаты / активный заказ → block.
    Ошибка чтения заказов → status_unknown (не трактовать как «не оплачено»).
    """
    try:
        orders = list(repo.list_orders(case_id) or [])
    except Exception:  # noqa: BLE001
        return True, True
    for order in orders:
        if not isinstance(order, dict):
            continue
        status = str(order.get("status") or "").lower()
        if status in {
            "paid",
            "succeeded",
            "active",
            "in_progress",
            "completed",
            "pending",
            "waiting_for_capture",
            "waiting_payment",
        }:
            return True, False
        payments = order.get("payments") or []
        for pay in payments if isinstance(payments, list) else []:
            if not isinstance(pay, dict):
                continue
            pst = str(pay.get("status") or "").lower()
            if pst in {"succeeded", "paid", "pending", "waiting_for_capture"}:
                return True, False
    return False, False


def _client_declined_precheck_offer(repo: Any, case_id: str) -> bool:
    try:
        row = repo.get_case_row(case_id) or {}
        flags = row.get("flags") if isinstance(row.get("flags"), dict) else {}
        return bool(flags.get("precheck_offer_declined"))
    except Exception:  # noqa: BLE001
        return False


def _attach_primary_precheck(
    base: dict[str, Any],
    *,
    case_id: str,
    repo: Any,
    analyzed: list[dict[str, Any]],
) -> dict[str, Any]:
    """Добавить outcome/резюме/рекомендацию без второго pipeline."""
    from sfrfr.core.config import get_settings
    from sfrfr.services.precheck_period_sources import periods_for_precheck
    from sfrfr.services.primary_doc_precheck import run_primary_precheck

    row = repo.get_pipeline_row(case_id) or {}
    ils, labor, period_state, extract_error = periods_for_precheck(
        pipeline_row=row if isinstance(row, dict) else {},
        analyzed_documents=analyzed,
    )
    kit_missing = list(base.get("missing_for_task") or [])
    if period_state in {
        "extract_not_run",
        "extract_failed",
        "extract_empty_unreadable",
        "documents_missing",
    }:
        # Пустые периоды ≠ «расхождений нет».
        if "periods" not in kit_missing:
            kit_missing.append("извлечённые периоды стажа/ИЛС")
    settings = get_settings()
    amount = int(getattr(settings, "default_diagnostic_price_rub", 0) or 0) or None
    block_offer, order_unknown = _orders_offer_gate(repo, case_id)
    if order_unknown:
        amount = None  # не продавать при неизвестном статусе оплаты
    pre = run_primary_precheck(
        ils_periods=ils,
        labor_periods=labor,
        kit_missing=kit_missing,
        needs_ocr=int(base.get("needs_recognition") or 0),
        originals_missing=max(
            0,
            int(base.get("documents_checked") or 0)
            - int(base.get("originals_available") or 0),
        ),
        already_ordered_or_paid=block_offer,
        client_declined_offer=_client_declined_precheck_offer(repo, case_id),
        catalog_amount_rub=amount,
        catalog_label="Подробный анализ документов",
        package_code="diagnostic",
    )
    out = dict(base)
    primary = pre.as_dict()
    primary["period_source_state"] = period_state
    if extract_error:
        primary["period_extract_error"] = extract_error
    out["primary_precheck"] = primary
    out["precheck_outcome"] = pre.outcome.value
    out["client_summary"] = pre.client_summary
    out["checked_scope"] = list(pre.areas_checked)
    out["processor_version"] = str(primary.get("rules_version") or "")
    out["period_source_state"] = period_state
    if pre.outcome.value == "discrepancies_found" and out.get("status") == "completed":
        out["status"] = "needs_action"
        out["next_action"] = (
            "Есть расхождения источников — покажите клиенту резюме "
            "и при необходимости предложите подробный анализ."
        )
    elif period_state != "periods_ready" and pre.outcome.value == "no_discrepancies_found":
        # Защита: не оставлять ложный clear при пустых периодах.
        out["status"] = "needs_action"
        out["precheck_outcome"] = "insufficient_documents"
        out["client_summary"] = (
            "Периоды для сопоставления ещё не получены "
            f"(состояние: {period_state}). Это не вывод «расхождений нет»."
        )
        if isinstance(out.get("primary_precheck"), dict):
            out["primary_precheck"]["comparison_status"] = "inconclusive"
            out["primary_precheck"]["outcome"] = "insufficient_documents"
    return out


def _analyze_case_documents(case_id: str) -> dict[str, Any]:
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.message_dedupe import required_docs_missing

    repo = CaseRepository()
    docs = list(repo.list_documents(case_id) or [])
    ocr_allowed = _ocr_allowed()
    analyzed = [_analyze_one(d, ocr_allowed=ocr_allowed) for d in docs if isinstance(d, dict)]
    case = repo.get_case_row(case_id) or {"id": case_id, "documents": docs}
    if "documents" not in case or not case.get("documents"):
        case = {**case, "documents": docs}
    missing = required_docs_missing(case)
    base = build_check_result(
        documents=analyzed,
        missing_for_task=missing,
        ocr_allowed=ocr_allowed,
    )
    brief = _honest_brief_for_case(case_id=case_id, docs=docs, repo=repo)
    merged = attach_honest_brief(base, brief=brief)
    try:
        return _attach_primary_precheck(
            merged, case_id=case_id, repo=repo, analyzed=analyzed
        )
    except Exception:  # noqa: BLE001 — kit-check важнее падения сверки
        logger.warning("primary_precheck attach failed case=%s", case_id[:8], exc_info=True)
        return merged


def enqueue_staff_document_check(*, case_id: str, actor_id: str) -> dict[str, Any]:
    """Зарегистрировать задачу. Повтор на тот же набор — вернуть существующую."""
    from sfrfr.db.session import get_supabase_client

    cid = (case_id or "").strip()
    if not cid:
        raise ValueError("case_id required")
    client = get_supabase_client()
    # Только поля fingerprint: id+checksum. Не тянуть cloud_status —
    # колонки нет на prod → PostgREST 42703 → HTTP 500 без CORS → «Failed to fetch».
    docs = (
        client.table("documents")
        .select("id, checksum_sha256")
        .eq("case_id", cid)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    fp = documents_fingerprint(list(docs))
    if not docs:
        return {
            "ok": False,
            "job_id": "",
            "status": "rejected",
            "status_label": "нет документов",
            "documents_fingerprint": fp,
            "document_set_revision": fp,
            "deduped": False,
            "message": (
                "В деле нет документов для проверки. "
                "Загрузите файлы и повторите — фиктивный результат не создаём."
            ),
        }
    existing = (
        client.table("staff_document_check_jobs")
        .select("id, status, documents_fingerprint")
        .eq("case_id", cid)
        .in_("status", list(ACTIVE_STATUSES))
        .eq("documents_fingerprint", fp)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        row = existing[0]
        return {
            "ok": True,
            "job_id": str(row.get("id") or ""),
            "status": str(row.get("status") or "queued"),
            "status_label": STATUS_LABELS_RU.get(str(row.get("status") or ""), "ожидает"),
            "documents_fingerprint": fp,
            "document_set_revision": fp,
            "deduped": True,
            "message": "Проверка уже запущена для текущего набора документов.",
        }
    job_id = str(uuid4())
    client.table("staff_document_check_jobs").insert(
        {
            "id": job_id,
            "case_id": cid,
            "documents_fingerprint": fp,
            "status": "queued",
            "requested_by": actor_id,
            "current_stage": "queued",
            "job_type": JOB_TYPE,
        }
    ).execute()
    try:
        from sfrfr.db.case_repository import CaseRepository

        CaseRepository().audit(cid, actor_id, "staff_document_check_requested")
    except Exception:  # noqa: BLE001
        pass
    # Не стартуем анализ в процессе API здесь: daemon-thread на VPS (~2 GiB)
    # OOM-убивал uvicorn до ответа → в браузере «Failed to fetch» /
    # «Не удалось запустить проверку». Обработка — BackgroundTasks после
    # ответа или poll ingest-worker (`process_next_staff_document_check_job`).
    logger.info("staff_docs_check queued job=%s (deferred process)", job_id[:8])
    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "status_label": STATUS_LABELS_RU["queued"],
        "documents_fingerprint": fp,
        "document_set_revision": fp,
        "deduped": False,
        "message": "Проверка запущена.",
    }


def process_staff_document_check_job_safe(job_id: str) -> None:
    """Обёртка для BackgroundTasks / воркера: исключения не роняют HTTP."""
    try:
        process_staff_document_check_job(job_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "staff_docs_check bg process failed job=%s",
            str(job_id)[:8],
            exc_info=True,
        )


def process_staff_document_check_job(job_id: str) -> dict[str, Any]:
    from sfrfr.db.session import get_supabase_client
    from sfrfr.services.staff_document_check_lifecycle import (
        notify_already_recorded,
        result_already_finalized,
    )

    client = get_supabase_client()
    rows = (
        client.table("staff_document_check_jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise LookupError(f"staff docs check job not found: {job_id}")
    job = rows[0]
    if result_already_finalized(job):
        # Повтор worker/BackgroundTasks: не второй результат и не второй notify.
        return job
    attempts = int(job.get("attempts") or 0) + 1
    claimed = (
        client.table("staff_document_check_jobs")
        .update(
            {
                "status": "running",
                "attempts": attempts,
                "current_stage": "extract_classify_kit",
                "locked_by": _worker_id(),
                "locked_at": _now(),
                "updated_at": _now(),
            }
        )
        .eq("id", job_id)
        .in_("status", ["queued", "running"])
        .execute()
        .data
        or []
    )
    if not claimed and str(job.get("status")) not in {"queued", "running"}:
        return job
    try:
        case_id = str(job.get("case_id") or "")
        result = _analyze_case_documents(case_id)
        result["document_set_revision"] = str(job.get("documents_fingerprint") or "")
        result["check_id"] = job_id
        result["case_id"] = case_id
        result["started_at"] = job.get("created_at") or job.get("locked_at")
        result["completed_at"] = _now()
        final_status = str(result.get("status") or "completed")
        notify_meta: dict[str, Any] | None = None
        primary = result.get("primary_precheck")
        if (
            isinstance(primary, dict)
            and final_status in {"completed", "needs_action"}
            and not notify_already_recorded(job)
        ):
            try:
                from sfrfr.db.case_repository import CaseRepository
                from sfrfr.services.primary_doc_precheck_notify import (
                    enqueue_precheck_client_notify,
                )

                case_row = CaseRepository().get_case_row(case_id) or {}
                clients = case_row.get("clients") or {}
                if isinstance(clients, list):
                    clients = clients[0] if clients else {}
                mid = None
                if isinstance(clients, dict):
                    mid = clients.get("max_user_id")
                notify_meta = enqueue_precheck_client_notify(
                    case_id=case_id,
                    check_id=job_id,
                    primary=primary,
                    max_user_id=str(mid) if mid else None,
                )
                result = {**result, "client_notify": notify_meta}
            except Exception:  # noqa: BLE001
                logger.warning(
                    "precheck notify skipped job=%s", job_id[:8], exc_info=True
                )
        client.table("staff_document_check_jobs").update(
            {
                "status": final_status,
                "result": result,
                "current_stage": "done",
                "finished_at": _now(),
                "updated_at": _now(),
                "last_error": None,
                "locked_by": None,
                "locked_at": None,
            }
        ).eq("id", job_id).execute()
        return {"id": job_id, "status": final_status, "result": result}
    except Exception as exc:  # noqa: BLE001
        client.table("staff_document_check_jobs").update(
            {
                "status": "failed",
                "last_error": type(exc).__name__,
                "current_stage": "failed",
                "finished_at": _now(),
                "updated_at": _now(),
                "locked_by": None,
                "locked_at": None,
            }
        ).eq("id", job_id).execute()
        logger.warning("staff_docs_check failed job=%s err=%s", job_id[:8], type(exc).__name__)
        raise


def process_next_staff_document_check_job() -> dict[str, Any] | None:
    from sfrfr.db.session import get_supabase_client
    from sfrfr.services.staff_document_check_lifecycle import reclaim_stale_running_jobs

    reclaim_stale_running_jobs()
    client = get_supabase_client()
    jobs = (
        client.table("staff_document_check_jobs")
        .select("id")
        .eq("status", "queued")
        .order("created_at")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not jobs:
        return None
    return process_staff_document_check_job(str(jobs[0]["id"]))


def get_case_document_check(case_id: str) -> dict[str, Any] | None:
    """Последняя задача + stale, если набор документов изменился."""
    from sfrfr.db.session import get_supabase_client

    cid = (case_id or "").strip()
    if not cid:
        return None
    client = get_supabase_client()
    jobs = (
        client.table("staff_document_check_jobs")
        .select("*")
        .eq("case_id", cid)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not jobs:
        return None
    job = jobs[0]
    docs = (
        client.table("documents")
        .select("id, checksum_sha256")
        .eq("case_id", cid)
        .execute()
        .data
        or []
    )
    current_fp = documents_fingerprint(list(docs))
    job_fp = str(job.get("documents_fingerprint") or "")
    stale = bool(job_fp and current_fp and job_fp != current_fp)
    status = str(job.get("status") or "")
    raw_result = job.get("result") if isinstance(job.get("result"), dict) else None
    summary = summarize_for_staff(raw_result) if raw_result else None
    return {
        "job_id": str(job.get("id") or ""),
        "status": status,
        "status_label": STATUS_LABELS_RU.get(status, status),
        "stale": stale,
        "documents_fingerprint": job_fp,
        "current_documents_fingerprint": current_fp,
        "current_stage": job.get("current_stage"),
        "result": summary,
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
        "last_error": job.get("last_error"),
    }
