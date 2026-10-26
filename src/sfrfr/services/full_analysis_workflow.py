"""Версии подробного разбора (этап 5): черновик → проверка → отправка → согласование.

Хранение: ``storage/full_analysis/{case_id}.json`` (без ПДн сверх текста разбора).
Генерация файла или подстановка в чат сами по себе этап не закрывают.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sfrfr.core.config import get_settings

_LOCK = threading.Lock()

Status = str  # draft|staff_reviewed|sent|approved|remarks|superseded


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_store_root() -> Path:
    root = Path(get_settings().storage_local_path).resolve()
    if root.name:
        # обычно …/storage/uploads → parent = storage
        parent = root.parent if root.name.lower() in {"uploads", "local"} else root
    else:
        parent = root
    return parent / "full_analysis"


class FullAnalysisWorkflow:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_store_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, case_id: str) -> Path:
        safe = "".join(c for c in (case_id or "") if c.isalnum() or c in "-_")[:80]
        if not safe:
            raise ValueError("invalid_case_id")
        return self.root / f"{safe}.json"

    def _load(self, case_id: str) -> dict[str, Any]:
        path = self._path(case_id)
        if not path.is_file():
            return {"case_id": case_id, "versions": [], "current_id": None}
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"case_id": case_id, "versions": [], "current_id": None}
        versions = raw.get("versions")
        if not isinstance(versions, list):
            versions = []
        return {
            "case_id": case_id,
            "versions": [v for v in versions if isinstance(v, dict)],
            "current_id": raw.get("current_id"),
        }

    def _save(self, case_id: str, data: dict[str, Any]) -> None:
        path = self._path(case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        payload = {
            "case_id": case_id,
            "versions": data.get("versions") or [],
            "current_id": data.get("current_id"),
            "updated_at": _now(),
        }
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)

    def create_version(
        self,
        case_id: str,
        *,
        markdown: str,
        source: str = "ai",
        based_on: str | None = None,
    ) -> dict[str, Any]:
        with _LOCK:
            data = self._load(case_id)
            versions: list[dict[str, Any]] = list(data["versions"])
            for old in versions:
                if old.get("status") in {"draft", "staff_reviewed", "sent", "remarks"}:
                    if based_on and old.get("id") == based_on:
                        old["status"] = "superseded"
                    elif not based_on and old.get("status") != "approved":
                        # новая основная версия — предыдущие незакрытые помечаем
                        if old.get("id") == data.get("current_id"):
                            old["status"] = "superseded"
            n = 1 + max((int(v.get("n") or 0) for v in versions), default=0)
            ver = {
                "id": str(uuid.uuid4()),
                "n": n,
                "status": "draft",
                "markdown": (markdown or "").strip(),
                "source": source,
                "based_on": based_on,
                "docx_document_id": None,
                "client_revision_document_id": None,
                "client_revision_note": None,
                "sent_via": None,
                "sent_at": None,
                "delivery_error": None,
                "approved_at": None,
                "remarks": None,
                "remarks_at": None,
                "reviewed_at": None,
                "created_at": _now(),
            }
            versions.append(ver)
            data["versions"] = versions
            data["current_id"] = ver["id"]
            self._save(case_id, data)
            return dict(ver)

    def _mutate(
        self,
        case_id: str,
        version_id: str,
        fn: Any,
    ) -> dict[str, Any]:
        with _LOCK:
            data = self._load(case_id)
            found: dict[str, Any] | None = None
            for v in data["versions"]:
                if v.get("id") == version_id:
                    found = v
                    break
            if found is None:
                raise KeyError("version_not_found")
            fn(found, data)
            self._save(case_id, data)
            return dict(found)

    def update_markdown(self, case_id: str, version_id: str, markdown: str) -> dict[str, Any]:
        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            if v.get("status") in {"approved", "superseded"}:
                raise ValueError("version_locked")
            v["markdown"] = (markdown or "").strip()
            if v.get("status") == "sent":
                # правка после отправки → снова черновик к проверке
                v["status"] = "draft"
                v["sent_at"] = None
                v["sent_via"] = None

        return self._mutate(case_id, version_id, _fn)

    def mark_reviewed(self, case_id: str, version_id: str) -> dict[str, Any]:
        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            if v.get("status") in {"approved", "superseded"}:
                raise ValueError("version_locked")
            v["status"] = "staff_reviewed"
            v["reviewed_at"] = _now()
            v["delivery_error"] = None

        return self._mutate(case_id, version_id, _fn)

    def mark_sent(
        self,
        case_id: str,
        version_id: str,
        *,
        channel: str,
    ) -> dict[str, Any]:
        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            if v.get("status") not in {"staff_reviewed", "sent", "remarks"}:
                raise ValueError("not_reviewed")
            v["status"] = "sent"
            v["sent_via"] = channel
            v["sent_at"] = _now()
            v["delivery_error"] = None

        return self._mutate(case_id, version_id, _fn)

    def mark_delivery_error(
        self,
        case_id: str,
        version_id: str,
        *,
        error: str,
    ) -> dict[str, Any]:
        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            v["delivery_error"] = (error or "delivery_failed")[:200]
            # не ставим sent

        return self._mutate(case_id, version_id, _fn)

    def record_decision(
        self,
        case_id: str,
        version_id: str,
        *,
        decision: str,
        remarks: str | None = None,
    ) -> dict[str, Any]:
        dec = (decision or "").strip().lower()
        if dec not in {"approved", "remarks"}:
            raise ValueError("invalid_decision")

        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            if v.get("status") not in {"sent", "remarks", "staff_reviewed"}:
                raise ValueError("not_ready_for_decision")
            if dec == "approved":
                v["status"] = "approved"
                v["approved_at"] = _now()
                v["remarks"] = None
            else:
                v["status"] = "remarks"
                v["remarks"] = (remarks or "").strip() or "Замечания клиента"
                v["remarks_at"] = _now()
                v["approved_at"] = None

        return self._mutate(case_id, version_id, _fn)

    def attach_client_revision(
        self,
        case_id: str,
        version_id: str,
        *,
        document_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            v["client_revision_document_id"] = document_id
            v["client_revision_note"] = (note or "").strip() or None
            if v.get("status") == "approved":
                # новая правка клиента снимает согласование
                v["status"] = "remarks"
                v["approved_at"] = None
                v["remarks"] = v.get("remarks") or "Клиент прислал свою версию"
                v["remarks_at"] = _now()

        return self._mutate(case_id, version_id, _fn)

    def set_docx_document(
        self,
        case_id: str,
        version_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        def _fn(v: dict[str, Any], _data: dict[str, Any]) -> None:
            v["docx_document_id"] = document_id

        return self._mutate(case_id, version_id, _fn)

    def get_state(self, case_id: str) -> dict[str, Any]:
        data = self._load(case_id)
        versions = list(data["versions"])
        current = None
        cid = data.get("current_id")
        for v in versions:
            if v.get("id") == cid:
                current = v
                break
        if current is None and versions:
            current = versions[-1]
        strip = _status_strip(current)
        return {
            "case_id": case_id,
            "versions": versions,
            "current": current,
            "current_id": current.get("id") if current else None,
            "status_strip": strip,
        }


def _status_strip(current: dict[str, Any] | None) -> dict[str, Any]:
    if not current:
        return {
            "file": "нет",
            "reviewed": "нет",
            "sent": "нет",
            "approved": "нет",
            "delivery_error": None,
        }
    st = current.get("status")
    return {
        "file": "готов" if (current.get("markdown") or current.get("docx_document_id")) else "нет",
        "reviewed": "да" if st in {"staff_reviewed", "sent", "approved", "remarks"} else "нет",
        "sent": "да" if st in {"sent", "approved"} or current.get("sent_at") else "нет",
        "approved": "да" if st == "approved" else "нет",
        "delivery_error": current.get("delivery_error"),
        "version_n": current.get("n"),
        "status": st,
        "sent_via": current.get("sent_via"),
    }


def stage_work_from_state(state: dict[str, Any]) -> dict[str, str]:
    """Факты для case-funnel: delivered только после согласования актуальной версии."""
    current = state.get("current") if isinstance(state, dict) else None
    if not isinstance(current, dict):
        return {"state": "not_started", "releaseReady": "no"}
    st = current.get("status")
    if st == "approved":
        return {"state": "delivered", "releaseReady": "yes"}
    if st in {"sent", "remarks", "staff_reviewed"}:
        return {"state": "ready", "releaseReady": "no"}
    if current.get("markdown"):
        return {"state": "working", "releaseReady": "no"}
    return {"state": "not_started", "releaseReady": "no"}
