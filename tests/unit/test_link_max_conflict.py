"""ТЗ-09 этап D: конфликт max_user_id → 409."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from sfrfr.db.client_channels import ClientChannelRepository


class _Resp:
    def __init__(self, data: Any):
        self.data = data


def test_link_max_conflict_other_user() -> None:
    repo = ClientChannelRepository.__new__(ClientChannelRepository)
    client = MagicMock()
    repo.client = client

    def get_by_max(max_user_id: str) -> dict[str, Any] | None:
        return {"id": "c1", "user_id": "user-A", "max_user_id": max_user_id}

    def get_by_user(user_id: str) -> dict[str, Any] | None:
        return None

    repo.get_by_max_user_id = get_by_max  # type: ignore[method-assign]
    repo.get_by_user_id = get_by_user  # type: ignore[method-assign]

    with pytest.raises(HTTPException) as exc:
        repo.link_max_to_user(user_id="user-B", max_user_id="999", email="b@example.com")
    assert exc.value.status_code == 409
    assert "already linked" in str(exc.value.detail).lower()


def test_link_max_conflict_client_has_other_max() -> None:
    repo = ClientChannelRepository.__new__(ClientChannelRepository)
    repo.client = MagicMock()
    repo.get_by_max_user_id = lambda _m: None  # type: ignore[method-assign]
    repo.get_by_user_id = lambda _u: {  # type: ignore[method-assign]
        "id": "c2",
        "user_id": "user-A",
        "max_user_id": "111",
    }

    with pytest.raises(HTTPException) as exc:
        repo.link_max_to_user(user_id="user-A", max_user_id="222", email="a@example.com")
    assert exc.value.status_code == 409
