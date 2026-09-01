"""Единая загрузка документов: security, ingest, группы и batch."""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from sfrfr.db.session import get_supabase_client
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET
from sfrfr.services.document_ingest import (
    SIGNED_DOC_TYPES,
    run_ingest_pipeline,
    sha256_hex,
)
from sfrfr.services.document_requirements import active_scenario_codes
from sfrfr.services.file_security import (
    MAX_FILE_BYTES,
    is_downloadable_status,
    validate_upload_filename,
)

logger = logging.getLogger(__name__)

SIGNED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
STANDARD_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


def _allowed_content_types(doc_type: str | None) -> set[str]:
    if (doc_type or "").strip().lower() in SIGNED_DOC_TYPES:
        return SIGNED_CONTENT_TYPES | {"application/octet-stream"}
    return STANDARD_CONTENT_TYPES | {"image/webp", "image/tiff", "application/octet-stream"}


def _audit_access(case_id: str, document_id: str | None, actor_id: str | None, action: str) -> None:
    try:
        get_supabase_client().table("document_access_audit").insert(
            {
                "case_id": case_id,
                "document_id": document_id,
                "actor_id": actor_id,
                "action": action,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("document_access_audit skipped: %s", exc)


def find_duplicate_checksum(case_id: str, checksum: str) -> bool:
    if not checksum:
        return False
    try:
        rows = (
            get_supabase_client()
            .table("documents")
            .select("id")
            .eq("case_id", case_id)
            .eq("checksum_sha256", checksum)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(rows)
    except Exception:  # noqa: BLE001
        return False


def ensure_document_group(
    *,
    case_id: str,
    group_id: str | None,
    doc_type: str | None,
    requirement_code: str | None,
    title: str | None,
) -> str:
    client = get_supabase_client()
    if group_id:
        return group_id
    new_id = str(uuid4())
    client.table("document_groups").insert(
        {
            "id": new_id,
            "case_id": case_id,
            "doc_type": doc_type,
            "requirement_code": requirement_code,
            "title": title or "Документ",
        }
    ).execute()
    return new_id


def store_document(
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
    preview_text: str = "",
    scenario_rows: list[Any] | None = None,
    requirement_code: str | None = None,
) -> dict[str, Any]:
    name_check = validate_upload_filename(
        filename,
        allow_signed=(doc_type or "").strip().lower() in SIGNED_DOC_TYPES,
    )
    if not name_check.ok:
        raise ValueError(name_check.client_message or "invalid file")

    checksum = sha256_hex(data)
    duplicate = find_duplicate_checksum(case_id, checksum)
    scenarios = active_scenario_codes(scenario_rows)
    ingest = run_ingest_pipeline(
        data=data,
        filename=filename,
        content_type=content_type,
        doc_type=doc_type,
        preview_text=preview_text,
        active_scenarios=scenarios,
        duplicate_checksum=duplicate,
    )
    if ingest.get("ingest_status") == "blocked_security":
        raise ValueError(str(ingest.get("progress_message") or "Файл не прошёл проверку."))

    document_id = str(uuid4())
    safe_name = Path(filename or "document").name
    storage_path = f"{case_id}/{document_id}/{safe_name}"
    group_id = None
    if document_group_id or page_index is not None:
        group_id = ensure_document_group(
            case_id=case_id,
            group_id=document_group_id,
            doc_type=doc_type,
            requirement_code=requirement_code or ingest.get("placement_suggestion", {}).get(
                "requirement_code"
            ),
            title=safe_name,
        )

    client = get_supabase_client()
    client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
        storage_path,
        data,
        {"content-type": content_type, "x-upsert": "false"},
    )

    insert_row: dict[str, Any] = {
        "id": document_id,
        "case_id": case_id,
        "storage_path": storage_path,
        "doc_type": doc_type,
        "uploaded_by": uploaded_by,
        "upload_batch_id": upload_batch_id,
        "document_group_id": group_id,
        "page_index": page_index,
        "page_order": page_order,
        "upload_source": upload_source,
        "checksum_sha256": ingest.get("checksum_sha256"),
        "mime_verified": ingest.get("mime_verified"),
        "ingest_status": ingest.get("ingest_status"),
        "progress_percent": ingest.get("progress_percent"),
        "current_stage": ingest.get("current_stage"),
        "progress_message": ingest.get("progress_message"),
        "requirement_code": requirement_code
        or ingest.get("placement_suggestion", {}).get("requirement_code"),
        "placement_suggestion": ingest.get("placement_suggestion"),
        "quality_report": ingest.get("quality_report"),
        "client_declared_signed": client_declared_signed,
        "page_count": ingest.get("page_count"),
    }
    if preview_text:
        insert_row["content_preview"] = preview_text[:2000]

    response = client.table("documents").insert(insert_row).execute()
    row = response.data[0] if response.data else insert_row

    labor_rows = ingest.get("labor_timeline_drafts") or []
    if labor_rows:
        for draft in labor_rows:
            draft["case_id"] = case_id
            draft["document_id"] = document_id
            draft["document_group_id"] = group_id
        try:
            client.table("labor_timeline_drafts").insert(labor_rows).execute()
        except Exception as exc:  # noqa: BLE001
            logger.info("labor_timeline_drafts skipped: %s", exc)

    _audit_access(case_id, document_id, uploaded_by, "document_uploaded")
    return row


def build_zip_bytes(case_id: str, rows: list[dict[str, Any]]) -> bytes:
    client = get_supabase_client()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            path = str(row.get("storage_path") or "")
            if not path:
                continue
            group_id = str(row.get("document_group_id") or "")
            if group_id:
                grouped.setdefault(group_id, []).append(row)
                continue
            blob = client.storage.from_(PRIVATE_STORAGE_BUCKET).download(path)
            archive.writestr(_safe_archive_name(Path(path).name), blob)
        for pages in grouped.values():
            pages.sort(key=lambda row: int(row.get("page_order") or 0))
            if len(pages) > 1 and all(_is_image_row(row) for row in pages):
                pdf_name = _safe_archive_name(Path(str(pages[0]["storage_path"])).stem) + ".pdf"
                archive.writestr(pdf_name, build_group_pdf_bytes(pages))
                continue
            for row in pages:
                path = str(row.get("storage_path") or "")
                blob = client.storage.from_(PRIVATE_STORAGE_BUCKET).download(path)
                archive.writestr(_safe_archive_name(Path(path).name), blob)
    buffer.seek(0)
    return buffer.getvalue()


def filter_downloadable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if is_document_downloadable(row)]


def is_document_downloadable(row: dict[str, Any]) -> bool:
    return is_downloadable_status(
        str(row.get("ingest_status") or ""),
        antivirus_status=str(row.get("antivirus_status") or ""),
    )


def build_group_pdf_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Собрать страницы одной фото-группы в PDF без сохранения на диске."""
    from PIL import Image

    client = get_supabase_client()
    images: list[Image.Image] = []
    try:
        for row in sorted(rows, key=lambda item: int(item.get("page_order") or 0)):
            path = str(row.get("storage_path") or "")
            if not path:
                continue
            opened_image = Image.open(
                io.BytesIO(client.storage.from_(PRIVATE_STORAGE_BUCKET).download(path))
            )
            converted_image = opened_image.convert("RGB")
            opened_image.close()
            images.append(converted_image)
        if not images:
            raise ValueError("document group has no image pages")
        result = io.BytesIO()
        images[0].save(result, format="PDF", save_all=True, append_images=images[1:])
        result.seek(0)
        return result.getvalue()
    finally:
        for converted_image in images:
            converted_image.close()


def _is_image_row(row: dict[str, Any]) -> bool:
    mime = str(row.get("mime_verified") or "").lower()
    if mime.startswith("image/"):
        return True
    suffix = Path(str(row.get("storage_path") or "")).suffix.lower()
    return suffix in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def _safe_archive_name(name: str) -> str:
    safe = Path(name or "document").name.replace("\x00", "").strip()
    return safe or "document"


def validate_upload_size(data: bytes) -> None:
    if not data:
        raise ValueError("empty file")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("document exceeds 20 MiB")


def content_type_allowed(content_type: str, doc_type: str | None) -> bool:
    base = (content_type or "").split(";")[0].strip().lower()
    return base in _allowed_content_types(doc_type)
