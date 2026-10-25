from __future__ import annotations

from typing import Any

import pytest

from sfrfr.services.staff_document_delete import DocumentDeleteError, delete_case_document


class _Query:
    def __init__(self, db: _FakeDb, table: str) -> None:
        self.db, self.table_name = db, table
        self.filters: list[tuple[str, Any]] = []
        self.op = "select"
        self.payload: dict[str, Any] | None = None

    def select(self, *_a: Any, **_k: Any) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self.filters.append((col, val))
        return self

    def limit(self, *_a: Any) -> _Query:
        return self

    def delete(self) -> _Query:
        self.op = "delete"
        return self

    def update(self, payload: dict[str, Any]) -> _Query:
        self.op, self.payload = "update", payload
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        return all(row.get(c) == v for c, v in self.filters)

    def execute(self) -> Any:
        rows = self.db.tables.setdefault(self.table_name, [])
        hit = [r for r in rows if self._match(r)]
        if self.op == "delete":
            self.db.tables[self.table_name] = [r for r in rows if not self._match(r)]
        elif self.op == "update" and self.payload:
            for r in hit:
                r.update(self.payload)
        return type("R", (), {"data": hit})()


class _Bucket:
    def __init__(self, db: _FakeDb) -> None:
        self.db = db

    def remove(self, paths: list[str]) -> None:
        self.db.removed.extend(paths)


class _Storage:
    def __init__(self, db: _FakeDb) -> None:
        self.db = db

    def from_(self, _bucket: str) -> _Bucket:
        return _Bucket(self.db)


class _FakeDb:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.removed: list[str] = []
        self.storage = _Storage(self)

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _db(**extra: list[dict[str, Any]]) -> _FakeDb:
    tables: dict[str, list[dict[str, Any]]] = {
        "documents": [
            {"id": "d1", "case_id": "c1", "storage_path": "c1/scan.png", "doc_type": "other"},
            {"id": "d2", "case_id": "c1", "storage_path": "c1/x.pdf", "replaces_document_id": "d1"},
        ],
        "document_ingest_jobs": [{"id": "j1", "document_id": "d1"}],
        "case_document_checksums": [{"case_id": "c1", "document_id": "d1"}],
        "labor_timeline_drafts": [{"id": "l1", "document_id": "d1"}],
        "document_access_audit": [{"id": "a1", "document_id": "d1"}],
        "result_evidence": [],
        "diagnostic_results": [],
    }
    tables.update(extra)
    return _FakeDb(tables)


def test_delete_removes_file_row_and_derived_keeps_audit() -> None:
    db = _db()
    out = delete_case_document(db, case_id="c1", document_id="d1")
    assert out["deleted"] == "d1"
    assert [r["id"] for r in db.tables["documents"]] == ["d2"]
    assert db.tables["documents"][0]["replaces_document_id"] is None
    assert db.tables["document_ingest_jobs"] == []
    assert db.tables["case_document_checksums"] == []
    assert db.tables["labor_timeline_drafts"] == []
    assert db.tables["document_access_audit"] != []  # журнал доступа сохраняем
    assert db.removed == ["c1/scan.png"]


def test_refuses_when_used_as_result_evidence() -> None:
    db = _db(result_evidence=[{"id": "e1", "document_id": "d1"}])
    with pytest.raises(DocumentDeleteError) as err:
        delete_case_document(db, case_id="c1", document_id="d1")
    assert err.value.status == 409
    assert [r["id"] for r in db.tables["documents"]] == ["d1", "d2"]


def test_refuses_diagnosis_report() -> None:
    db = _db()
    db.tables["documents"][0]["doc_type"] = "diagnosis_report"
    with pytest.raises(DocumentDeleteError) as err:
        delete_case_document(db, case_id="c1", document_id="d1")
    assert err.value.status == 409


def test_missing_document_is_404() -> None:
    with pytest.raises(DocumentDeleteError) as err:
        delete_case_document(_db(), case_id="c1", document_id="nope")
    assert err.value.status == 404
