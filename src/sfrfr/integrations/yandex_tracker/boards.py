"""Доски Яндекс Трекера: list / create / ensure."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from sfrfr.integrations.yandex_tracker import API_BASE, _headers, _safe_error_detail

logger = logging.getLogger(__name__)


def board_url(*, queue: str, board_id: int | str) -> str:
    return f"https://tracker.yandex.ru/{queue}/agile/{board_id}"


def list_boards(*, per_page: int = 100) -> list[dict[str, Any]]:
    """Все доски организации (без токена в логах)."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{API_BASE}/boards",
                headers=_headers(),
                params={"perPage": per_page, "page": 1},
            )
        if resp.status_code != 200:
            logger.warning("tracker_list_boards_failed status=%s", resp.status_code)
            return []
        data = resp.json() if resp.content else []
        return data if isinstance(data, list) else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("tracker_list_boards_failed err=%s", type(exc).__name__)
        return []


def create_board(
    *,
    name: str,
    queue: str,
    query: str | None = None,
    board_type: str = "kanban",
) -> dict[str, Any]:
    """Создать доску и сразу PATCH имя/очередь/фильтр.

    На части тарифов POST игнорирует name/defaultQueue и запрещает ``query`` —
    поэтому после create всегда делаем PATCH.
    """
    body: dict[str, Any] = {
        "name": name[:255],
        "defaultQueue": queue,
        "boardType": board_type,
        "useRanking": False,
    }
    if query is not None and query.strip():
        body["query"] = query.strip()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{API_BASE}/boards/", headers=_headers(), json=body)
        data: Any
        try:
            data = resp.json() if resp.content else {}
        except Exception:  # noqa: BLE001
            data = {"text": (resp.text or "")[:200]}
        if (
            resp.status_code not in (200, 201)
            or not isinstance(data, dict)
            or data.get("id") is None
        ):
            return {
                "ok": False,
                "status_code": resp.status_code,
                "error": _safe_error_detail(data),
            }
        bid = data["id"]
        patched = patch_board(
            board_id=bid,
            version=data.get("version"),
            name=name,
            queue=queue,
        )
        if not patched.get("ok"):
            # доска уже есть — вернём id, чтобы ensure не плодил дубликаты
            return {
                "ok": True,
                "id": bid,
                "name": name,
                "url": board_url(queue=queue, board_id=bid),
                "patch_error": patched.get("error"),
            }
        return {
            "ok": True,
            "id": bid,
            "name": patched.get("name") or name,
            "url": board_url(queue=queue, board_id=bid),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def patch_board(
    *,
    board_id: int | str,
    version: Any,
    name: str,
    queue: str,
) -> dict[str, Any]:
    """Переименовать доску и привязать defaultQueue + filter по очереди."""
    if version is None:
        got = get_board(board_id)
        if not got.get("ok"):
            return got
        version = got.get("version")
        if version is None:
            return {"ok": False, "error": "no_version"}
    headers = dict(_headers())
    headers["If-Match"] = f'"{version}"'
    body = {
        "name": name[:255],
        "defaultQueue": queue,
        "filter": {"queue": queue},
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.patch(
                f"{API_BASE}/boards/{board_id}",
                headers=headers,
                json=body,
            )
        data: Any
        try:
            data = resp.json() if resp.content else {}
        except Exception:  # noqa: BLE001
            data = {"text": (resp.text or "")[:200]}
        if resp.status_code == 200 and isinstance(data, dict):
            return {
                "ok": True,
                "id": data.get("id", board_id),
                "name": data.get("name") or name,
                "version": data.get("version"),
            }
        return {
            "ok": False,
            "status_code": resp.status_code,
            "error": _safe_error_detail(data),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def get_board(board_id: int | str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(f"{API_BASE}/boards/{board_id}", headers=_headers())
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and isinstance(data, dict):
            return {"ok": True, **data}
        return {"ok": False, "status_code": resp.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}
