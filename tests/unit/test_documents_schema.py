"""Тесты совместимости схемы documents и normalize uploaded_by."""

from __future__ import annotations

from sfrfr.services.documents_schema import normalize_uploaded_by


def test_normalize_uploaded_by_rejects_max_prefix() -> None:
    assert normalize_uploaded_by("max:abc-case-id") is None
    assert normalize_uploaded_by("not-a-uuid") is None
    assert normalize_uploaded_by("") is None
    assert normalize_uploaded_by(None) is None


def test_normalize_uploaded_by_accepts_uuid() -> None:
    uid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert normalize_uploaded_by(uid) == uid
