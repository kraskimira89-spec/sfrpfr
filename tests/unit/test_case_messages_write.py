"""Тесты insert_case_message при отсутствии колонок схемы."""

from __future__ import annotations

from sfrfr.db import case_messages_write as cmw


class _FakeTable:
    def __init__(self, parent: "_FakeSB") -> None:
        self._parent = parent

    def insert(self, row: dict):
        self._parent.last_row = row
        return self

    def execute(self):
        if "channel_origin" in self._parent.last_row:
            raise RuntimeError(
                "Could not find the 'channel_origin' column of 'case_messages' in the schema cache"
            )
        return type("R", (), {"data": [{"id": "msg-1", **self._parent.last_row}]})()


class _FakeSB:
    def __init__(self) -> None:
        self.last_row: dict = {}

    def table(self, name: str) -> _FakeTable:
        assert name == "case_messages"
        return _FakeTable(self)


def test_insert_strips_missing_optional_columns(monkeypatch) -> None:
    fake = _FakeSB()
    monkeypatch.setattr(cmw, "get_supabase_client", lambda: fake)
    row = cmw.insert_case_message(
        {
            "case_id": "c1",
            "author_kind": "staff",
            "body": "hello",
            "channel_origin": "admin",
        }
    )
    assert row["id"] == "msg-1"
    assert "channel_origin" not in fake.last_row
