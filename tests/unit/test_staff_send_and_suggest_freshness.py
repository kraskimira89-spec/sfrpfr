"""P0: отправка специалиста в MAX не теряется за чужим outbox;
подсказки DeepSeek строятся по свежим сообщениям, а не по первым 40.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from sfrfr.services import case_chat_delivery as delivery


class _FakeQuery:
    def __init__(self, table: _FakeTable, mode: str, payload: dict | None = None):
        self.table = table
        self.mode = mode
        self.payload = payload or {}
        self.filters: dict[str, Any] = {}
        self.limit_n: int | None = None

    def select(self, *_a: Any, **_k: Any) -> _FakeQuery:
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def order(self, *_a: Any, **_k: Any) -> _FakeQuery:
        return self

    def limit(self, n: int) -> _FakeQuery:
        self.limit_n = n
        return self

    def execute(self) -> SimpleNamespace:
        rows = [
            r
            for r in self.table.rows
            if all(r.get(k) == v for k, v in self.filters.items())
        ]
        if self.mode == "update":
            for r in rows:
                r.update(self.payload)
            return SimpleNamespace(data=rows)
        rows = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
        if self.limit_n:
            rows = rows[: self.limit_n]
        return SimpleNamespace(data=[dict(r) for r in rows])


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def select(self, *_a: Any, **_k: Any) -> _FakeQuery:
        return _FakeQuery(self, "select")

    def update(self, payload: dict) -> _FakeQuery:
        return _FakeQuery(self, "update", payload)


class _FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = {k: _FakeTable(v) for k, v in tables.items()}

    def table(self, name: str) -> _FakeTable:
        return self.tables[name]


def _outbox_rows() -> list[dict]:
    return [
        {
            "id": "out-old",
            "case_id": "c1",
            "message_id": "msg-old",
            "max_user_id": "user-old",
            "body": "старое чужое сообщение",
            "attachments": [],
            "status": "pending",
            "attempts": 0,
            "created_at": "2026-10-20T10:00:00+00:00",
        },
        {
            "id": "out-new",
            "case_id": "c1",
            "message_id": "msg-new",
            "max_user_id": "user-new",
            "body": "свежий ответ специалиста",
            "attachments": [],
            "status": "pending",
            "attempts": 0,
            "created_at": "2026-10-20T11:00:00+00:00",
        },
    ]


def test_process_outbox_by_message_id_sends_exact_message() -> None:
    rows = _outbox_rows()
    fake = _FakeSupabase({"case_chat_outbox": rows, "case_messages": []})
    bot = MagicMock()
    bot.available = True
    bot.send_message.return_value = {"message": {"id": "ext-1"}}

    with (
        patch("sfrfr.db.session.get_supabase_client", return_value=fake),
        patch("sfrfr.integrations.max.client.MaxBotClient", return_value=bot),
    ):
        sent = delivery.process_pending_outbox(limit=1, message_id="msg-new")

    assert sent == 1
    bot.send_message.assert_called_once()
    kwargs = bot.send_message.call_args.kwargs
    assert kwargs.get("text") == "свежий ответ специалиста" or (
        bot.send_message.call_args.args
        and "свежий" in str(bot.send_message.call_args)
    )
    by_id = {r["id"]: r for r in rows}
    assert by_id["out-new"]["status"] == "sent"
    assert by_id["out-old"]["status"] == "pending"


def test_mirror_staff_processes_own_message_not_oldest() -> None:
    case = {"id": "case-1", "clients": {"max_user_id": "u-1"}}
    with (
        patch.object(delivery, "enqueue_max_delivery", return_value=True) as enqueue,
        patch.object(delivery, "process_pending_outbox") as process,
    ):
        delivery.mirror_staff_message_to_max(case, "Ответ клиенту", message_id="m-9")
    enqueue.assert_called_once()
    assert process.call_args.kwargs.get("message_id") == "m-9"


def test_suggest_replies_uses_latest_messages() -> None:
    from sfrfr.api.routes import admin_portal

    case = {
        "id": "12345678-1234-1234-1234-123456789012",
        "pipeline_status": "human_review",
        "b2c_status": "docs",
        "clients": {"full_name": "Иван Иванов"},
    }
    # БД при desc-порядке отдаёт от свежих к старым.
    db_rows_desc = [
        {"author_kind": "system", "body": "[Документ] ils.pdf · Выписка ИЛС", "created_at": "3"},
        {"author_kind": "client", "body": "прислал файл", "created_at": "2"},
        {"author_kind": "client", "body": "Здравствуйте", "created_at": "1"},
    ]
    order_kwargs: dict[str, Any] = {}
    chain = MagicMock()

    def _order(*_a: Any, **kw: Any) -> MagicMock:
        order_kwargs.update(kw)
        return chain

    table = MagicMock()
    table.select.return_value.eq.return_value.order.side_effect = _order
    chain.limit.return_value.execute.return_value.data = db_rows_desc
    sb = MagicMock()
    sb.table.return_value = table

    repo = MagicMock()
    repo.require_case.return_value = case
    captured: dict[str, Any] = {}

    def fake_suggest(**kw: Any) -> list[str]:
        captured.update(kw)
        return ["вариант"]

    with (
        patch.object(admin_portal, "_repo", return_value=repo),
        patch.object(admin_portal, "get_supabase_client", return_value=sb),
        patch.object(admin_portal, "suggest_staff_replies", side_effect=fake_suggest),
        patch(
            "sfrfr.services.case_chat_context.work_map_from_case",
            return_value={},
        ),
    ):
        out = admin_portal.suggest_case_replies(case["id"], principal=MagicMock())

    assert out["suggestions"] == ["вариант"]
    assert order_kwargs.get("desc") is True, "нужны последние сообщения, а не первые 40"
    bodies = [m["body"] for m in captured["messages"]]
    assert bodies == ["Здравствуйте", "прислал файл", "[Документ] ils.pdf · Выписка ИЛС"]
