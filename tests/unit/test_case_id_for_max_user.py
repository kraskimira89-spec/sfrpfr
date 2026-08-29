"""Резолв case_id для MAX: фантомы из intake отбрасываем."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sfrfr.integrations.max import handler as max_handler


def test_case_id_for_max_user_clears_phantom_intake() -> None:
    intake = SimpleNamespace(case_id="41935a1d-eea2-4951-b700-65a1063ff5dc")
    store = MagicMock()
    store.get_active.return_value = intake

    with (
        patch.object(max_handler, "_resolve_case_id_by_max_user", return_value=None),
        patch.object(max_handler, "get_intake_store", return_value=store),
        patch.object(max_handler, "_case_exists_in_supabase", return_value=False),
    ):
        assert max_handler._case_id_for_max_user("max-1") is None

    assert intake.case_id is None
    store.save.assert_called_once_with(intake)


def test_case_id_for_max_user_keeps_real_intake() -> None:
    real = "32528a2d-b914-4463-b737-feba84cc45e1"
    intake = SimpleNamespace(case_id=real)
    store = MagicMock()
    store.get_active.return_value = intake

    with (
        patch.object(max_handler, "_resolve_case_id_by_max_user", return_value=None),
        patch.object(max_handler, "get_intake_store", return_value=store),
        patch.object(max_handler, "_case_exists_in_supabase", return_value=True),
    ):
        assert max_handler._case_id_for_max_user("max-1") == real

    store.save.assert_not_called()
