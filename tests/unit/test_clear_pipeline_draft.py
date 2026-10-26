"""clear_pipeline_draft передаёт draft=None в snapshot."""

from __future__ import annotations

from unittest.mock import MagicMock

from sfrfr.db.case_repository import CaseRepository


def test_clear_pipeline_draft_saves_null_draft() -> None:
    repo = CaseRepository.__new__(CaseRepository)
    repo.save_pipeline_snapshot = MagicMock(return_value={"case_id": "c1"})  # type: ignore[method-assign]
    repo.clear_pipeline_draft("c1")
    repo.save_pipeline_snapshot.assert_called_once_with("c1", {"draft": None})
