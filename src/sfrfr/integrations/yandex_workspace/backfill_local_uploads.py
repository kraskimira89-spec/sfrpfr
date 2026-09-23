"""CLI: залить локальные uploads дела на Яндекс.Диск → incoming/."""

from __future__ import annotations

from typing import Any


def backfill_local_uploads_to_disk(
    *,
    case_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Скопировать storage/uploads/{case}/файл → Disk incoming/ (оригинал байт)."""
    from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe
    from sfrfr.storage.local import uploads_root

    root = uploads_root()
    if not root.exists():
        return {"ok": False, "error": "uploads_root_missing", "path": str(root)}

    case_dirs = (
        [root / case_id]
        if case_id
        else sorted(p for p in root.iterdir() if p.is_dir())
    )
    uploaded = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    for cdir in case_dirs:
        if not cdir.is_dir():
            continue
        cid = cdir.name
        for path in sorted(cdir.iterdir()):
            if not path.is_file():
                continue
            # Имя на диске: без uuid-префикса локального save_upload
            remote_name = path.name
            if "_" in remote_name and len(remote_name.split("_", 1)[0]) == 8:
                remote_name = remote_name.split("_", 1)[1]
            data = path.read_bytes()
            if dry_run:
                uploaded += 1
                continue
            result = mirror_case_document_safe(cid, remote_name, data)
            if result.get("ok"):
                uploaded += 1
            elif result.get("skipped"):
                skipped += 1
            else:
                errors.append(
                    {
                        "case_id": cid,
                        "file": path.name,
                        "error": str(result.get("error") or result.get("detail") or result),
                    }
                )
    return {
        "ok": not errors,
        "uploaded": uploaded,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }
