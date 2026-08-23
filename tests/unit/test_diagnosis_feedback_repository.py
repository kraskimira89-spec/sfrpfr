"""Тесты репозитория diagnosis_feedback (без живого Supabase)."""

from __future__ import annotations

from typing import Any


class _FakeTable:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self.store = store
        self._eq: str | None = None
        self._payload: dict[str, Any] | None = None
        self._op = "select"

    def select(self, *_a: Any, **_k: Any) -> _FakeTable:
        self._op = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeTable:
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> _FakeTable:
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, _col: str, value: str) -> _FakeTable:
        self._eq = value
        return self

    def limit(self, *_a: Any, **_k: Any) -> _FakeTable:
        return self

    def execute(self) -> Any:
        class R:
            data: list[dict[str, Any]]

        r = R()
        if self._op == "select":
            row = self.store.get(self._eq or "")
            r.data = [row] if row else []
        elif self._op == "insert":
            assert self._payload is not None
            cid = str(self._payload["case_id"])
            self.store[cid] = dict(self._payload)
            r.data = [self.store[cid]]
        else:
            assert self._payload is not None
            cid = self._eq or ""
            self.store.setdefault(cid, {"case_id": cid})
            self.store[cid].update(self._payload)
            r.data = [self.store[cid]]
        return r


class _FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def table(self, _name: str) -> _FakeTable:
        return _FakeTable(self.store)


def test_mark_pdf_issued_sets_nav_pending_and_touch_due() -> None:
    from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository

    client = _FakeClient()
    repo = DiagnosisFeedbackRepository(client=client)
    row = repo.mark_pdf_issued("case-1")
    assert row["feedback_status"] == "nav_pending"
    assert row.get("pdf_issued_at")
    assert row.get("touch2_due_at")
    assert row.get("touch3_due_at")
    # повторно не перезаписывает
    again = repo.mark_pdf_issued("case-1")
    assert again["pdf_issued_at"] == row["pdf_issued_at"]


def test_patch_filters_unknown_fields() -> None:
    from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository

    client = _FakeClient()
    repo = DiagnosisFeedbackRepository(client=client)
    repo.mark_pdf_issued("case-2")
    out = repo.patch(
        "case-2",
        {
            "clarity_score": 4,
            "expectation_match": "yes",
            "hack": "no",
            "feedback_status": "understood",
        },
    )
    assert out["clarity_score"] == 4
    assert out["feedback_status"] == "understood"
    assert "hack" not in out
