"""ensure_case: при сбое create не слать emergency, если дело уже есть в БД."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sfrfr.integrations.max import handler as h


def test_ensure_case_recovers_existing_case_skips_emergency() -> None:
    """Таймаут create + дело уже в Postgres → case_id и без emergency notify."""
    case_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    intake = SimpleNamespace(
        case_id=None,
        client_id=None,
        goal=None,
        max_first_name="Иван",
        max_last_name="",
    )
    store = MagicMock()
    store.find_by_max_user.return_value = None
    store.create.return_value = SimpleNamespace(case_id=case_id)

    with (
        patch.object(h, "get_settings") as gs,
        patch.object(h, "get_intake_store") as gis,
        patch.object(h, "_try_create_supabase_case", return_value=None),
        patch.object(h, "_resolve_case_id_by_max_user", return_value=case_id),
        patch.object(h, "_client_row_by_max", return_value={"id": "client-1"}),
        patch(
            "sfrfr.services.lead_emergency_buffer.capture_max_lead_db_down"
        ) as emergency,
        patch(
            "sfrfr.integrations.max.case_chat_log.flush_pending_case_chat"
        ),
    ):
        gs.return_value = SimpleNamespace(
            supabase_url="https://supabase2.example",
            supabase_service_role_key="service-role",
        )
        intake_store = MagicMock()
        intake_store.save = MagicMock()
        gis.return_value = intake_store
        got = h._ensure_case_for_intake(
            user_id="114092740",
            chat_id=1,
            intake=intake,
            store=store,
            timeout=1.0,
        )

    assert got == case_id
    emergency.assert_not_called()
    store.bind_max.assert_called_once()


def test_ensure_case_emergency_only_when_no_case() -> None:
    intake = SimpleNamespace(
        case_id=None,
        client_id=None,
        goal=None,
        max_first_name="Пётр",
        max_last_name="",
    )
    store = MagicMock()
    store.find_by_max_user.return_value = None

    with (
        patch.object(h, "get_settings") as gs,
        patch.object(h, "get_intake_store") as gis,
        patch.object(h, "_try_create_supabase_case", return_value=None),
        patch.object(h, "_resolve_case_id_by_max_user", return_value=None),
        patch(
            "sfrfr.services.lead_emergency_buffer.capture_max_lead_db_down",
            return_value={"id": "buf"},
        ) as emergency,
    ):
        gs.return_value = SimpleNamespace(
            supabase_url="https://supabase2.example",
            supabase_service_role_key="service-role",
        )
        gis.return_value = MagicMock()
        got = h._ensure_case_for_intake(
            user_id="999",
            chat_id=None,
            intake=intake,
            store=store,
            timeout=1.0,
        )

    assert got == ""
    emergency.assert_called_once()


def test_try_create_logs_distinct_timeout_vs_error() -> None:
    from concurrent.futures import TimeoutError as FuturesTimeout

    intake = SimpleNamespace(goal=None)

    with (
        patch.object(h, "get_settings") as gs,
        patch.object(h, "_ensure_client_row", side_effect=RuntimeError("boom")),
        patch("sfrfr.integrations.max.handler.logger") as log,
    ):
        gs.return_value = SimpleNamespace(
            supabase_url="https://supabase2.example",
            supabase_service_role_key="service-role",
        )
        assert h._try_create_supabase_case(user_id="1", intake=intake, timeout=None) is None
        assert any(
            "ensure_case_supabase_error" in str(c)
            for c in log.warning.call_args_list
        )

    with (
        patch.object(h, "get_settings") as gs,
        patch(
            "concurrent.futures.ThreadPoolExecutor"
        ) as pool_cls,
        patch("sfrfr.integrations.max.handler.logger") as log,
    ):
        gs.return_value = SimpleNamespace(
            supabase_url="https://supabase2.example",
            supabase_service_role_key="service-role",
        )
        pool = MagicMock()
        pool_cls.return_value = pool
        fut = MagicMock()
        fut.result.side_effect = FuturesTimeout()
        pool.submit.return_value = fut
        assert h._try_create_supabase_case(user_id="1", intake=intake, timeout=0.01) is None
        assert any(
            "ensure_case_supabase_timeout" in str(c)
            for c in log.warning.call_args_list
        )
        pool.shutdown.assert_called_with(wait=False, cancel_futures=True)
