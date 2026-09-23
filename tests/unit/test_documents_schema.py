"""Тесты совместимости схемы documents и normalize uploaded_by."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sfrfr.services import documents_schema
from sfrfr.services.documents_schema import normalize_uploaded_by


def test_normalize_uploaded_by_rejects_max_prefix() -> None:
    assert normalize_uploaded_by("max:abc-case-id") is None
    assert normalize_uploaded_by("not-a-uuid") is None
    assert normalize_uploaded_by("") is None
    assert normalize_uploaded_by(None) is None


def test_normalize_uploaded_by_accepts_uuid() -> None:
    uid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert normalize_uploaded_by(uid) == uid


class _SchemaError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"schema error {code}")
        self.code = code


def test_documents_schema_inspection_fails_closed_on_unknown_error(monkeypatch) -> None:
    client = SimpleNamespace(
        table=lambda _name: SimpleNamespace(
            select=lambda *_fields: SimpleNamespace(
                limit=lambda _limit: SimpleNamespace(
                    execute=lambda: (_ for _ in ()).throw(ConnectionError("temporary outage"))
                )
            )
        )
    )
    monkeypatch.setattr(documents_schema, "get_supabase_client", lambda: client)
    documents_schema.clear_documents_schema_cache()

    with pytest.raises(ConnectionError):
        documents_schema.documents_has_ingest_columns()


def test_documents_schema_inspection_allows_known_missing_column(monkeypatch) -> None:
    client = SimpleNamespace(
        table=lambda _name: SimpleNamespace(
            select=lambda *_fields: SimpleNamespace(
                limit=lambda _limit: SimpleNamespace(
                    execute=lambda: (_ for _ in ()).throw(_SchemaError("42703"))
                )
            )
        )
    )
    monkeypatch.setattr(documents_schema, "get_supabase_client", lambda: client)
    documents_schema.clear_documents_schema_cache()

    assert documents_schema.documents_has_ingest_columns() is False
