"""Резолв case_id для MAX: фантомы из intake отбрасываем."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sfrfr.core.case_store import reset_case_store
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


def test_chat_case_id_rejects_phantom_preferred() -> None:
    phantom = "41935a1d-eea2-4951-b700-65a1063ff5dc"
    real = "32528a2d-b914-4463-b737-feba84cc45e1"

    with (
        patch.object(max_handler, "_case_exists_in_supabase", side_effect=lambda c: c == real),
        patch.object(max_handler, "_case_id_for_max_user", return_value=real) as resolve,
    ):
        assert max_handler._chat_case_id("max-1", preferred=phantom) == real
        resolve.assert_called_once_with("max-1")


def test_chat_case_id_keeps_valid_preferred() -> None:
    real = "32528a2d-b914-4463-b737-feba84cc45e1"

    with (
        patch.object(max_handler, "_case_exists_in_supabase", return_value=True),
        patch.object(max_handler, "_case_id_for_max_user") as resolve,
    ):
        assert max_handler._chat_case_id("max-1", preferred=real) == real
        resolve.assert_not_called()


def test_bind_max_exclusive_and_clear() -> None:
    from sfrfr.core import case_store as cs_mod

    path = Path("storage/test-case-store-bind/cases.json")
    store = reset_case_store(path)
    try:
        a = store.create(client_name="A", snils_masked="***")
        b = store.create(client_name="B", snils_masked="***")
        store.bind_max(a.case_id, max_user_id="max-9")
        store.bind_max(b.case_id, max_user_id="max-9")
        assert store.find_by_max_user("max-9").case_id == b.case_id
        assert store.get(a.case_id).ctx.max_user_id is None
        assert store.clear_max_binding("max-9") == 1
        assert store.find_by_max_user("max-9") is None
    finally:
        cs_mod._STORE = None
