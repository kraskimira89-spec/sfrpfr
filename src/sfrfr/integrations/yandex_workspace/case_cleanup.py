"""Аудит и чистка папок SFRFR-cases на Яндекс.Диске.

Только служебные операции: дубли UUID-папок при наличии ФИО-папки,
legacy-файлы в корне (→ incoming/) и 8-hex префиксы в именах.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sfrfr.integrations.yandex_workspace.backfill_case_originals import remote_basename
from sfrfr.integrations.yandex_workspace.case_mirror import lookup_case_client_full_name
from sfrfr.integrations.yandex_workspace.disk import (
    CASE_CHAT_HISTORY_NAME,
    CASE_META_NAME,
    CASE_SUBFOLDERS,
    CASES_FOLDER,
    _safe_remote_name,
    build_case_meta_text,
    delete_case_path,
    ensure_case_layout,
    list_case_dir,
    move_case_path,
    upload_case_file,
)
from sfrfr.utils.case_folder_name import format_case_disk_folder_name

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
# Сгенерированные файлы — не считаем содержимым дела при сравнении папок.
_GENERATED = {CASE_META_NAME.lower(), CASE_CHAT_HISTORY_NAME.lower()}


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match((value or "").strip()))


def _case_root(folder: str) -> str:
    return f"{CASES_FOLDER}/{folder}"


def _normalized(name: str) -> str:
    """Имя без 8-hex префикса локального save_upload, lowercase."""
    return remote_basename(name).strip().lower()


def list_case_folders() -> list[str]:
    """Имена папок дел на Диске (без служебных метаданных)."""
    result = list_case_dir(CASES_FOLDER)
    if not result.get("ok"):
        return []
    return [
        str(item.get("name") or "")
        for item in result.get("items") or []
        if item.get("type") == "dir" and item.get("name")
    ]


def read_case_tree(folder: str) -> dict[str, list[str]]:
    """Файлы папки дела: {"_root": [...], "incoming": [...], ...}."""
    tree: dict[str, list[str]] = {"_root": []}
    root = list_case_dir(_case_root(folder))
    for item in root.get("items") or []:
        name = str(item.get("name") or "")
        if item.get("type") != "dir":
            if name:
                tree["_root"].append(name)
            continue
        key = name.lower()
        if key not in CASE_SUBFOLDERS:
            continue
        inner = list_case_dir(f"{_case_root(folder)}/{key}")
        tree[key] = [
            str(x.get("name") or "")
            for x in inner.get("items") or []
            if x.get("type") != "dir" and x.get("name")
        ]
    return tree


def _content_names(tree: dict[str, list[str]]) -> set[str]:
    """Реальные файлы дела без meta.txt/history.md."""
    names: set[str] = set()
    for key, values in tree.items():
        for name in values:
            if key == "_root" and name.lower() in _GENERATED:
                continue
            names.add(_normalized(name))
    return names


def audit_case_folders() -> dict[str, Any]:
    """Сводка по папкам: UUID vs ФИО, legacy-файлы в корне, префиксы."""
    folders: list[dict[str, Any]] = []
    for folder in list_case_folders():
        tree = read_case_tree(folder)
        root_files = tree.get("_root") or []
        sub_names = [k for k in tree if k != "_root"]
        prefixed = sorted(
            {
                name
                for key, values in tree.items()
                for name in values
                if remote_basename(name) != name
            }
        )
        folders.append(
            {
                "folder": folder,
                "is_uuid": _is_uuid(folder),
                "subfolders": sorted(sub_names),
                "legacy_root_files": sorted(root_files),
                "prefixed_names": prefixed,
                "file_count": sum(len(v) for v in tree.values()),
            }
        )
    return {
        "ok": True,
        "count": len(folders),
        "uuid_folders": sum(1 for f in folders if f["is_uuid"]),
        "legacy_folders": sum(1 for f in folders if not f["subfolders"]),
        "folders": folders,
    }


def cleanup_duplicate_uuid_folders(*, dry_run: bool = True) -> dict[str, Any]:
    """Удалить UUID-папку, если её файлы уже есть в ФИО-папке того же дела."""
    folders = list_case_folders()
    fio_folders = {f for f in folders if not _is_uuid(f)}
    actions: list[dict[str, Any]] = []
    for folder in folders:
        if not _is_uuid(folder):
            continue
        target = format_case_disk_folder_name(lookup_case_client_full_name(folder), case_id=folder)
        if target.lower() == folder.lower() or target not in fio_folders:
            continue
        missing = _content_names(read_case_tree(folder)) - _content_names(read_case_tree(target))
        if missing:
            actions.append(
                {
                    "action": "keep",
                    "folder": folder,
                    "reason": "files_not_in_fio_folder",
                    "missing_count": len(missing),
                }
            )
            continue
        if dry_run:
            actions.append({"action": "would_delete", "folder": folder, "duplicate_of": target})
            continue
        result = delete_case_path(_case_root(folder))
        actions.append(
            {
                "action": "deleted" if result.get("ok") else "delete_failed",
                "folder": folder,
                "duplicate_of": target,
                "detail": result.get("detail") or result.get("error"),
            }
        )
    return {
        "ok": True,
        "dry_run": dry_run,
        "deleted": sum(1 for a in actions if a["action"] in {"deleted", "would_delete"}),
        "actions": actions,
    }


def rename_uuid_folders_to_fio(*, dry_run: bool = True) -> dict[str, Any]:
    """Переименовать UUID-папку в ФИО, если ФИО-папки ещё нет."""
    folders = list_case_folders()
    folder_set = {f for f in folders}
    actions: list[dict[str, Any]] = []
    for folder in folders:
        if not _is_uuid(folder):
            continue
        target = format_case_disk_folder_name(lookup_case_client_full_name(folder), case_id=folder)
        if not target or target.lower() == folder.lower() or _is_uuid(target):
            actions.append(
                {
                    "action": "skip",
                    "folder": folder,
                    "reason": "no_fio_or_placeholder",
                }
            )
            continue
        if target in folder_set:
            continue  # есть дубль — это зона migrate/cleanup
        if dry_run:
            actions.append({"action": "would_rename", "folder": folder, "target": target})
            continue
        result = move_case_path(_case_root(folder), _case_root(target))
        if result.get("ok"):
            folder_set.discard(folder)
            folder_set.add(target)
        actions.append(
            {
                "action": "renamed" if result.get("ok") else "rename_failed",
                "folder": folder,
                "target": target,
                "detail": result.get("detail") or result.get("error"),
            }
        )
    return {
        "ok": True,
        "dry_run": dry_run,
        "renamed": sum(1 for a in actions if a["action"] in {"renamed", "would_rename"}),
        "actions": actions,
    }


def migrate_uuid_into_fio(*, dry_run: bool = True) -> dict[str, Any]:
    """Перенести уникальные файлы из UUID-папки в ФИО, затем удалить UUID."""
    folders = list_case_folders()
    fio_folders = {f for f in folders if not _is_uuid(f)}
    actions: list[dict[str, Any]] = []
    for folder in folders:
        if not _is_uuid(folder):
            continue
        target = format_case_disk_folder_name(lookup_case_client_full_name(folder), case_id=folder)
        if target.lower() == folder.lower() or target not in fio_folders:
            continue
        uuid_tree = read_case_tree(folder)
        fio_names = _content_names(read_case_tree(target))
        to_move = _unique_file_paths(uuid_tree, fio_names)
        if dry_run:
            actions.append(
                {
                    "action": "would_migrate",
                    "folder": folder,
                    "target": target,
                    "moved": to_move,
                }
            )
            continue
        layout = ensure_case_layout(folder, folder_name=target)
        if not layout.get("ok") and not layout.get("skipped"):
            actions.append(
                {
                    "action": "layout_failed",
                    "folder": folder,
                    "target": target,
                    "detail": layout.get("error"),
                }
            )
            continue
        moved: list[str] = []
        errors: list[str] = []
        for rel in to_move:
            clean = _safe_remote_name(remote_basename(rel.rsplit("/", 1)[-1]))
            sub = rel.rsplit("/", 1)[0] if "/" in rel else "_root"
            if sub == "_root":
                dest = f"{_case_root(target)}/incoming/{clean}"
            else:
                dest = f"{_case_root(target)}/{sub}/{clean}"
            src = f"{_case_root(folder)}/{rel}"
            result = move_case_path(src, dest)
            if result.get("ok"):
                moved.append(rel)
            else:
                errors.append(f"{rel}:{result.get('detail') or result.get('error')}")
        if errors:
            actions.append(
                {
                    "action": "migrate_partial",
                    "folder": folder,
                    "target": target,
                    "moved": moved,
                    "errors": errors,
                }
            )
            continue
        deleted = delete_case_path(_case_root(folder))
        actions.append(
            {
                "action": "migrated" if deleted.get("ok") else "delete_failed",
                "folder": folder,
                "target": target,
                "moved": moved,
                "detail": deleted.get("detail") or deleted.get("error"),
            }
        )
    return {
        "ok": True,
        "dry_run": dry_run,
        "migrated": sum(1 for a in actions if a["action"] in {"migrated", "would_migrate"}),
        "actions": actions,
    }


def _unique_file_paths(tree: dict[str, list[str]], already: set[str]) -> list[str]:
    """Относительные пути файлов UUID-папки, которых нет в ФИО (по нормализованному имени)."""
    paths: list[str] = []
    for key, values in tree.items():
        for name in values:
            if key == "_root" and name.lower() in _GENERATED:
                continue
            if _normalized(name) in already:
                continue
            paths.append(name if key == "_root" else f"{key}/{name}")
    return sorted(paths)


def normalize_legacy_folders(*, dry_run: bool = True) -> dict[str, Any]:
    """UUID-папки: файлы из корня → incoming/, префиксы убрать, meta.txt создать."""
    actions: list[dict[str, Any]] = []
    for folder in list_case_folders():
        if not _is_uuid(folder):
            continue
        tree = read_case_tree(folder)
        legacy_root = [
            name for name in tree.get("_root") or [] if name.lower() != CASE_META_NAME.lower()
        ]
        prefixed = [
            (key, name)
            for key, values in tree.items()
            if key != "_root"
            for name in values
            if remote_basename(name) != name
        ]
        need_meta = not any(n.lower() == CASE_META_NAME.lower() for n in tree.get("_root") or [])
        if not legacy_root and not prefixed and not need_meta:
            continue
        plan = {
            "folder": folder,
            "move_to_incoming": legacy_root,
            "rename_in_place": [f"{key}/{name}" for key, name in prefixed],
            "ensure_meta": need_meta,
        }
        if dry_run:
            actions.append({"action": "would_normalize", **plan})
            continue
        result = _normalize_one(folder, legacy_root=legacy_root, prefixed=prefixed)
        actions.append({**result, **plan})
    return {
        "ok": True,
        "dry_run": dry_run,
        "normalized": sum(1 for a in actions if a["action"] in {"normalized", "would_normalize"}),
        "actions": actions,
    }


def _normalize_one(
    folder: str,
    *,
    legacy_root: list[str],
    prefixed: list[tuple[str, str]],
) -> dict[str, Any]:
    layout = ensure_case_layout(folder)
    if not layout.get("ok") and not layout.get("skipped"):
        return {"action": "layout_failed", "detail": layout.get("error")}
    errors: list[str] = []
    moved = 0
    for name in legacy_root:
        target = f"{_case_root(folder)}/incoming/{_safe_remote_name(name)}"
        result = move_case_path(f"{_case_root(folder)}/{name}", target)
        if result.get("ok"):
            moved += 1
        else:
            errors.append(f"move:{name}:{result.get('detail') or result.get('error')}")
    renamed = 0
    for key, name in prefixed:
        clean = _safe_remote_name(remote_basename(name))
        if clean.lower() == name.lower():
            continue
        result = move_case_path(
            f"{_case_root(folder)}/{key}/{name}",
            f"{_case_root(folder)}/{key}/{clean}",
        )
        if result.get("ok"):
            renamed += 1
        else:
            errors.append(f"rename:{name}:{result.get('detail') or result.get('error')}")
    meta = upload_case_file(
        folder,
        remote_name=CASE_META_NAME,
        content=build_case_meta_text(folder, folder_name=folder).encode("utf-8"),
        overwrite=True,
    )
    if not meta.get("ok") and not meta.get("skipped"):
        errors.append(f"meta:{meta.get('detail') or meta.get('error')}")
    return {
        "action": "normalized" if not errors else "normalize_partial",
        "moved": moved,
        "renamed": renamed,
        "errors": errors,
    }
