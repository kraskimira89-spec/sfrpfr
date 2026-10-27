"""DocsOrderSlotConflict: unique conflict → понятная ошибка."""

from postgrest.exceptions import APIError

from sfrfr.db.case_repository import CaseRepository, DocsOrderSlotConflict


def test_create_order_maps_unique_violation_to_docs_conflict(monkeypatch) -> None:
    repo = CaseRepository.__new__(CaseRepository)

    class _FakeTable:
        def insert(self, *_a, **_k):  # noqa: ANN001
            return self

        def execute(self):  # noqa: ANN201
            raise APIError({"code": "23505", "message": "duplicate"})

    class _FakeClient:
        def table(self, _name: str) -> _FakeTable:
            return _FakeTable()

    repo.client = _FakeClient()  # type: ignore[assignment]

    try:
        repo.create_order(
            "case-1",
            package_code="ACCOMP",
            amount_rub=5000,
            status_value="pending",
        )
        raise AssertionError("expected DocsOrderSlotConflict")
    except DocsOrderSlotConflict as exc:
        assert "уже есть" in str(exc)
