"""Файловое хранилище кейсов (MVP до Postgres): storage/cases.json."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sfrfr.ai.orchestrator import CaseContext, CaseOrchestrator, StepResult
from sfrfr.ai.schemas.agents import ClassifyResult, DraftResult, Finding
from sfrfr.core.config import get_settings
from sfrfr.models.case_status import CaseStatus


def default_store_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "cases.json"


@dataclass
class CaseRecord:
    """Карточка кейса + контекст пайплайна."""

    case_id: str
    client_name: str
    snils_masked: str
    consent_given: bool = True
    ctx: CaseContext = field(default_factory=lambda: CaseContext(case_id=""))

    def __post_init__(self) -> None:
        if not self.ctx.case_id:
            self.ctx.case_id = self.case_id
        if self.ctx.client_name is None:
            self.ctx.client_name = self.client_name


def _ctx_to_dict(ctx: CaseContext) -> dict[str, Any]:
    return {
        "case_id": ctx.case_id,
        "status": str(ctx.status),
        "client_name": ctx.client_name,
        "max_user_id": ctx.max_user_id,
        "max_chat_id": ctx.max_chat_id,
        "document_paths": list(ctx.document_paths),
        "ocr_texts": list(ctx.ocr_texts),
        "classifications": [c.model_dump(mode="json") for c in ctx.classifications],
        "ils_periods": list(ctx.ils_periods),
        "labor_periods": list(ctx.labor_periods),
        "findings": [f.model_dump(mode="json") for f in ctx.findings],
        "draft": ctx.draft.model_dump(mode="json") if ctx.draft else None,
        "error": ctx.error,
    }


def _ctx_from_dict(data: dict[str, Any]) -> CaseContext:
    draft_raw = data.get("draft")
    return CaseContext(
        case_id=data["case_id"],
        status=CaseStatus(data.get("status", CaseStatus.INTAKE)),
        client_name=data.get("client_name"),
        max_user_id=data.get("max_user_id"),
        max_chat_id=data.get("max_chat_id"),
        document_paths=list(data.get("document_paths") or []),
        ocr_texts=list(data.get("ocr_texts") or []),
        classifications=[ClassifyResult.model_validate(c) for c in data.get("classifications") or []],
        ils_periods=list(data.get("ils_periods") or []),
        labor_periods=list(data.get("labor_periods") or []),
        findings=[Finding.model_validate(f) for f in data.get("findings") or []],
        draft=DraftResult.model_validate(draft_raw) if draft_raw else None,
        error=data.get("error"),
    )


def _record_to_dict(record: CaseRecord) -> dict[str, Any]:
    return {
        "case_id": record.case_id,
        "client_name": record.client_name,
        "snils_masked": record.snils_masked,
        "consent_given": record.consent_given,
        "ctx": _ctx_to_dict(record.ctx),
    }


def _record_from_dict(data: dict[str, Any]) -> CaseRecord:
    return CaseRecord(
        case_id=data["case_id"],
        client_name=data["client_name"],
        snils_masked=data["snils_masked"],
        consent_given=bool(data.get("consent_given", True)),
        ctx=_ctx_from_dict(data.get("ctx") or {"case_id": data["case_id"]}),
    )


class CaseStore:
    """Потокобезопасный store с JSON-персистенцией для API/CLI."""

    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._path = path or default_store_path()
        self._cases: dict[str, CaseRecord] = {}
        self._orch = CaseOrchestrator()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        cases = raw.get("cases") if isinstance(raw, dict) else None
        if not isinstance(cases, dict):
            return
        loaded: dict[str, CaseRecord] = {}
        for case_id, payload in cases.items():
            try:
                loaded[case_id] = _record_from_dict(payload)
            except (KeyError, ValueError, TypeError):
                continue
        self._cases = loaded

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cases": {cid: _record_to_dict(rec) for cid, rec in self._cases.items()}}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def create(self, *, client_name: str, snils_masked: str, consent_given: bool = True) -> CaseRecord:
        case_id = str(uuid.uuid4())
        record = CaseRecord(
            case_id=case_id,
            client_name=client_name,
            snils_masked=snils_masked,
            consent_given=consent_given,
            ctx=CaseContext(case_id=case_id, client_name=client_name, status=CaseStatus.INTAKE),
        )
        with self._lock:
            self._cases[case_id] = record
            self._save()
        return record

    def get(self, case_id: str) -> CaseRecord | None:
        with self._lock:
            self._load()
            return self._cases.get(case_id)

    def require(self, case_id: str) -> CaseRecord:
        record = self.get(case_id)
        if record is None:
            raise KeyError(case_id)
        return record

    def find_by_max_user(self, max_user_id: str) -> CaseRecord | None:
        with self._lock:
            self._load()
            for record in self._cases.values():
                if record.ctx.max_user_id == max_user_id:
                    return record
        return None

    def bind_max(
        self,
        case_id: str,
        *,
        max_user_id: str,
        max_chat_id: str | None = None,
    ) -> CaseRecord:
        with self._lock:
            self._load()
            record = self._cases[case_id]
            record.ctx.max_user_id = max_user_id
            record.ctx.max_chat_id = max_chat_id
            self._save()
            return record

    def add_document(self, case_id: str, path: str) -> CaseRecord:
        with self._lock:
            self._load()
            record = self._cases[case_id]
            record.ctx.document_paths.append(path)
            if record.ctx.status is CaseStatus.INTAKE:
                record.ctx.status = CaseStatus.DOCUMENTS_RECEIVED
            self._save()
            return record

    def advance(self, case_id: str) -> tuple[CaseRecord, StepResult]:
        with self._lock:
            self._load()
            record = self._cases[case_id]
            result = self._orch.advance(record.ctx)
            self._save()
            return record, result

    def run_until(
        self,
        case_id: str,
        *,
        stop_at: CaseStatus = CaseStatus.HUMAN_REVIEW,
    ) -> CaseRecord:
        with self._lock:
            self._load()
            record = self._cases[case_id]
            self._orch.run_until(record.ctx, stop_at=stop_at)
            self._save()
            return record

    def complete(self, case_id: str) -> tuple[CaseRecord, StepResult]:
        with self._lock:
            self._load()
            record = self._cases[case_id]
            result = self._orch.complete_after_review(record.ctx)
            self._save()
            return record, result


_STORE: CaseStore | None = None


def get_case_store() -> CaseStore:
    global _STORE
    if _STORE is None:
        _STORE = CaseStore()
    return _STORE


def reset_case_store(path: Path) -> CaseStore:
    """Для тестов: новый store на указанный JSON-файл."""
    global _STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    _STORE = CaseStore(path=path)
    return _STORE
