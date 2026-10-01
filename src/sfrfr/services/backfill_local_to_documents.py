"""Backfill: storage/uploads/{case}/ → documents + pension-docs (учёт).

Чинит рассинхрон после silent-local / schema lag: файлы на диске VPS есть,
строк в documents нет.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _strip_local_prefix(name: str) -> str:
    raw = (name or "").strip()
    if "_" in raw:
        prefix, rest = raw.split("_", 1)
        if len(prefix) == 8 and all(c in "0123456789abcdefABCDEF" for c in prefix):
            return rest or raw
    return raw


def _case_has_registered_basename(case_id: str, basename: str) -> bool:
    """True, если в documents уже есть файл с тем же именем (minimal schema без checksum)."""
    from sfrfr.db.session import get_supabase_client

    want = (basename or "").strip().lower()
    if not want:
        return False
    try:
        rows = (
            get_supabase_client()
            .table("documents")
            .select("storage_path")
            .eq("case_id", case_id)
            .limit(100)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        return False
    for row in rows:
        path = str(row.get("storage_path") or "")
        if path.lower().endswith("/" + want) or path.lower().endswith(want):
            return True
    return False


def backfill_local_uploads_to_documents(
    *,
    case_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Зарегистрировать локальные uploads в documents (+ Storage), идемпотентно."""
    from sfrfr.db.session import get_supabase_client
    from sfrfr.services.document_ingest import sha256_hex
    from sfrfr.services.document_ingest_worker import create_quarantine_document
    from sfrfr.services.document_upload import find_duplicate_checksum
    from sfrfr.services.file_security import align_filename_to_content
    from sfrfr.storage.local import uploads_root

    root = uploads_root()
    if not root.exists():
        return {"ok": False, "error": "uploads_root_missing", "path": str(root)}

    sb = get_supabase_client()
    case_dirs: list[Path]
    if case_id:
        cid = case_id.strip().lower()
        if not _UUID_RE.match(cid):
            return {"ok": False, "error": "invalid_case_id"}
        case_dirs = [root / cid]
    else:
        case_dirs = sorted(p for p in root.iterdir() if p.is_dir() and _UUID_RE.match(p.name))

    uploaded = 0
    skipped = 0
    missing_case = 0
    errors: list[dict[str, str]] = []

    for cdir in case_dirs:
        if not cdir.is_dir():
            continue
        cid = cdir.name.lower()
        try:
            exists = (
                sb.table("cases").select("id").eq("id", cid).limit(1).execute().data or []
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"case_id": cid, "error": f"cases_lookup:{type(exc).__name__}"})
            continue
        if not exists:
            missing_case += 1
            logger.info("backfill skip orphan uploads case=%s", cid[:8])
            continue

        for path in sorted(cdir.iterdir()):
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                errors.append({"case_id": cid, "file": path.name, "error": str(exc)[:120]})
                continue
            if not data:
                skipped += 1
                continue
            digest = sha256_hex(data)
            safe_name = align_filename_to_content(_strip_local_prefix(path.name), data)
            if find_duplicate_checksum(cid, digest) or _case_has_registered_basename(
                cid, safe_name
            ):
                skipped += 1
                continue
            if dry_run:
                uploaded += 1
                continue
            try:
                create_quarantine_document(
                    case_id=cid,
                    filename=safe_name,
                    data=data,
                    content_type="application/octet-stream",
                    doc_type=None,
                    uploaded_by=None,
                    upload_source="backfill_local",
                )
                uploaded += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "case_id": cid,
                        "file": path.name,
                        "error": str(exc)[:200],
                    }
                )

    return {
        "ok": not errors,
        "dry_run": dry_run,
        "registered": uploaded,
        "skipped": skipped,
        "orphan_upload_dirs": missing_case,
        "errors": errors,
    }
