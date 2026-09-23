"""Backfill уже загруженных файлов → local uploads + Disk SFRFR-cases/{ФИО}/incoming.

Источники: storage/uploads/{case_id}/ и bucket pension-docs.
Идемпотентность: state по sha256 (без имён/ПДн в логах) + skip повторного mirror.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_STATE_NAME = "backfill_fio_seen.json"


def remote_basename(filename: str) -> str:
    """Убрать 8-hex префикс local save_upload, если он есть."""
    name = (filename or "").strip()
    if "_" in name:
        prefix, rest = name.split("_", 1)
        if len(prefix) == 8 and all(c in "0123456789abcdefABCDEF" for c in prefix):
            return rest or name
    return name


def local_has_sha256(case_dir: Path, digest: str) -> bool:
    """Есть ли в каталоге дела файл с тем же sha256."""
    if not case_dir.is_dir():
        return False
    want = (digest or "").strip().lower()
    if not want:
        return False
    for path in case_dir.iterdir():
        if not path.is_file():
            continue
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() == want:
                return True
        except OSError:
            continue
    return False


def _state_path() -> Path:
    from sfrfr.storage.local import uploads_root

    return uploads_root().parent / _STATE_NAME


def _load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, dict):
        return {str(k) for k, v in raw.items() if v}
    return set()


def _save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=0) + "\n",
        encoding="utf-8",
    )


def _seen_key(case_id: str, digest: str) -> str:
    return f"{case_id.lower()}:{digest.lower()}"


def _iter_local_blobs(
    *,
    case_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    from sfrfr.storage.local import uploads_root

    root = uploads_root()
    if not root.exists():
        return
    case_dirs = (
        [root / case_id]
        if case_id
        else sorted(p for p in root.iterdir() if p.is_dir())
    )
    for cdir in case_dirs:
        if not cdir.is_dir():
            continue
        cid = cdir.name
        if not _UUID_RE.match(cid):
            continue
        for path in sorted(cdir.iterdir()):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            yield {
                "case_id": cid,
                "filename": remote_basename(path.name),
                "source": "local",
                "path": path,
                "persist_local": False,
            }


def _iter_storage_blobs(
    *,
    case_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Обход bucket pension-docs: {case}/{doc_id}/{file} и quarantine/verified."""
    from sfrfr.db.session import get_supabase_client
    from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

    client = get_supabase_client()
    bucket = client.storage.from_(PRIVATE_STORAGE_BUCKET)

    def list_prefix(prefix: str) -> list[dict[str, Any]]:
        try:
            return list(bucket.list(prefix) or [])
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "storage list skipped prefix_len=%s err=%s",
                len(prefix),
                type(exc).__name__,
            )
            return []

    roots = list_prefix("")
    for top in roots:
        top_name = str(top.get("name") or "").strip()
        if not top_name:
            continue
        if top_name in {"quarantine", "verified", "ingest"}:
            for mid in list_prefix(top_name):
                mid_name = str(mid.get("name") or "").strip()
                if not _UUID_RE.match(mid_name):
                    continue
                if case_id and mid_name.lower() != case_id.lower():
                    continue
                yield from _walk_case_storage(
                    case_id=mid_name,
                    prefix=f"{top_name}/{mid_name}",
                    list_prefix=list_prefix,
                )
            continue
        if not _UUID_RE.match(top_name):
            continue
        if case_id and top_name.lower() != case_id.lower():
            continue
        yield from _walk_case_storage(
            case_id=top_name,
            prefix=top_name,
            list_prefix=list_prefix,
        )


def _walk_case_storage(
    *,
    case_id: str,
    prefix: str,
    list_prefix: Any,
) -> Iterator[dict[str, Any]]:
    for item in list_prefix(prefix):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        meta = item.get("metadata")
        full = f"{prefix}/{name}"
        if meta:
            yield {
                "case_id": case_id,
                "filename": remote_basename(name),
                "source": "storage",
                "storage_path": full,
                "persist_local": True,
            }
            continue
        for child in list_prefix(full):
            cname = str(child.get("name") or "").strip()
            if not cname:
                continue
            cmeta = child.get("metadata")
            child_path = f"{full}/{cname}"
            if cmeta:
                yield {
                    "case_id": case_id,
                    "filename": remote_basename(cname),
                    "source": "storage",
                    "storage_path": child_path,
                    "persist_local": True,
                }


def _read_blob(item: dict[str, Any]) -> bytes | None:
    path = item.get("path")
    if isinstance(path, Path):
        try:
            return path.read_bytes()
        except OSError:
            return None
    storage_path = str(item.get("storage_path") or "").strip()
    if not storage_path:
        return None
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

        blob = (
            get_supabase_client()
            .storage.from_(PRIVATE_STORAGE_BUCKET)
            .download(storage_path)
        )
        return bytes(blob) if blob is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.info("storage download skipped err=%s", type(exc).__name__)
        return None


def backfill_case_originals_to_fio(
    *,
    case_id: str | None = None,
    dry_run: bool = False,
    include_storage: bool = True,
) -> dict[str, Any]:
    """Сохранить уже загруженные файлы как новые оригиналы в канон ФИО-зеркала."""
    from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe

    items: list[dict[str, Any]] = list(_iter_local_blobs(case_id=case_id))
    if include_storage:
        try:
            items.extend(list(_iter_storage_blobs(case_id=case_id)))
        except Exception as exc:  # noqa: BLE001
            logger.info("storage source skipped err=%s", type(exc).__name__)

    state_file = _state_path()
    seen = _load_seen(state_file)
    uploaded = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    cases: set[str] = set()
    processed_keys: set[str] = set()

    for item in items:
        cid = str(item.get("case_id") or "").strip()
        filename = str(item.get("filename") or "document.bin").strip() or "document.bin"
        if not cid or not _UUID_RE.match(cid):
            continue
        cases.add(cid.lower())

        if dry_run:
            key = (
                f"dry:{cid}:{item.get('source')}:{filename}:"
                f"{item.get('storage_path') or item.get('path')}"
            )
            if key in processed_keys:
                skipped += 1
                continue
            processed_keys.add(key)
            uploaded += 1
            continue

        data = _read_blob(item)
        if not data:
            errors.append(
                {
                    "case_id": cid,
                    "error": "read_failed",
                    "source": str(item.get("source")),
                }
            )
            continue
        digest = hashlib.sha256(data).hexdigest()
        key = _seen_key(cid, digest)
        if key in seen or key in processed_keys:
            skipped += 1
            continue
        processed_keys.add(key)

        persist_local = bool(item.get("persist_local"))
        result = mirror_case_document_safe(
            cid,
            filename,
            data,
            persist_local=persist_local,
        )
        if result.get("ok"):
            uploaded += 1
            seen.add(key)
        elif result.get("skipped"):
            skipped += 1
            seen.add(key)
        else:
            errors.append(
                {
                    "case_id": cid,
                    "error": str(
                        result.get("error") or result.get("detail") or "mirror_failed"
                    )[:120],
                    "source": str(item.get("source")),
                }
            )

    if not dry_run:
        try:
            _save_seen(state_file, seen)
        except OSError as exc:
            logger.info("backfill state save skipped err=%s", type(exc).__name__)

    return {
        "ok": not errors,
        "uploaded": uploaded,
        "skipped": skipped,
        "errors": errors,
        "cases": len(cases),
        "files": uploaded + skipped if dry_run else uploaded + skipped + len(errors),
        "dry_run": dry_run,
        "include_storage": include_storage,
    }
