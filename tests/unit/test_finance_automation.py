"""Автосоздание черновика счёта и ежедневный tick сроков."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sfrfr.services.finance_automation import (
    CHECK_PAYMENT_TITLE,
    ensure_agreement_draft_invoice,
    on_order_fully_paid,
    run_due_tick,
    suggest_agreement_draft,
)


class FakeRepo:
    def __init__(self, case: dict, orders: list[dict] | None = None) -> None:
        self.case = case
        self.orders = list(orders or [])
        self.audits: list[str] = []
        self.tasks: list[str] = []
        self.updated_fields: dict[str, dict] = {}
        self.pipeline: str | None = None
        self.next_action: str | None = None

    def get_case_row(self, case_id: str) -> dict:
        row = dict(self.case)
        row["id"] = case_id
        row["checklist_items"] = [
            {"title": t, "status": "open"} for t in self.tasks
        ]
        return row

    def list_orders(self, _case_id: str) -> list[dict]:
        return self.orders

    def list_all_orders(self) -> list[dict]:
        return self.orders

    def create_order(self, case_id: str, **kwargs) -> dict:
        row = {"id": f"ord-{len(self.orders)+1}", "case_id": case_id, **kwargs}
        row["status"] = kwargs.get("status_value", "draft")
        self.orders.append(row)
        return row

    def update_next_action(self, _case_id: str, _actor, **kwargs) -> dict:
        self.next_action = kwargs.get("next_action")
        return {}

    def update_case_status(self, _case_id: str, status: str, _actor, notify=False) -> dict:
        self.pipeline = status
        return {}

    def update_order_fields(self, order_id: str, **kwargs) -> dict:
        self.audits.append(str(kwargs.get("action")))
        self.updated_fields[order_id] = kwargs.get("fields") or {}
        return {"id": order_id, **self.updated_fields[order_id]}

    def list_finance_audit(self, _order_id: str) -> list[dict]:
        return [{"action": a} for a in self.audits]

    def upsert_checklist_item(self, _case_id: str, **kwargs) -> dict:
        self.tasks.append(str(kwargs.get("title")))
        return {}


def test_suggest_diag_when_no_orders() -> None:
    case = {"b2c_status": "contract_accepted", "clients": {"full_name": "Сергей"}}
    out = suggest_agreement_draft(case, [])
    assert out is not None
    assert out["package_code"] == "DIAG"
    assert out["amount_rub"] == 3000


def test_suggest_docs_after_paid_diag_and_contract() -> None:
    case = {"b2c_status": "contract_accepted", "clients": {"full_name": "Сергей"}}
    orders = [{"package_code": "DIAG", "status": "paid"}]
    out = suggest_agreement_draft(case, orders)
    assert out is not None
    assert out["package_code"] == "ACCOMP"
    assert out["amount_rub"] == 5000


def test_suggest_docs_after_webhook_sets_diagnostic_paid() -> None:
    case = {"b2c_status": "diagnostic_paid", "clients": {"full_name": "Сергей"}}
    orders = [{"package_code": "DIAG", "status": "paid"}]
    out = suggest_agreement_draft(case, orders)
    assert out is not None
    assert out["package_code"] == "ACCOMP"


def test_no_accomp_without_agreement() -> None:
    case = {"b2c_status": "intake", "clients": {"full_name": "Сергей"}}
    orders = [{"package_code": "DIAG", "status": "paid"}]
    assert suggest_agreement_draft(case, orders) is None


def test_no_draft_for_test_case() -> None:
    case = {"b2c_status": "contract_accepted", "clients": {"full_name": "Тест Клиент AMO"}}
    assert suggest_agreement_draft(case, []) is None


def test_no_second_diag_if_pending() -> None:
    case = {"b2c_status": "contract_accepted", "clients": {"full_name": "Сергей"}}
    orders = [{"package_code": "DIAG", "status": "pending"}]
    assert suggest_agreement_draft(case, orders) is None


def test_ensure_creates_draft() -> None:
    repo = FakeRepo({"b2c_status": "contract_accepted", "clients": {"full_name": "Сергей"}})
    created = ensure_agreement_draft_invoice(repo, "c1", "u1")
    assert created is not None
    assert created["package_code"] == "DIAG"
    assert repo.next_action == "Выставить счёт"


def test_paid_diag_moves_intake_and_sets_action() -> None:
    repo = FakeRepo(
        {
            "b2c_status": "diagnostic_paid",
            "pipeline_status": "intake",
            "clients": {"full_name": "Сергей"},
        },
        orders=[{"package_code": "DIAG", "status": "paid"}],
    )
    on_order_fully_paid(repo, "c1", "DIAG")
    assert repo.next_action == "Провести диагностику"
    assert repo.pipeline == "documents_received"
    assert any(o.get("package_code") == "ACCOMP" for o in repo.orders)


def test_paid_accomp_does_not_jump_pipeline() -> None:
    repo = FakeRepo(
        {
            "b2c_status": "service_paid",
            "pipeline_status": "documents_received",
            "clients": {"full_name": "Сергей"},
        },
        orders=[{"package_code": "ACCOMP", "status": "paid"}],
    )
    on_order_fully_paid(repo, "c1", "ACCOMP")
    assert repo.next_action == "Готовить документы и проект обращения"
    assert repo.pipeline is None


def test_due_tick_creates_task_within_24h() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    due = now + timedelta(hours=10)
    repo = FakeRepo(
        {"b2c_status": "contract_accepted", "clients": {"full_name": "Сергей"}},
        orders=[
            {
                "id": "o1",
                "case_id": "c1",
                "status": "pending",
                "package_code": "DIAG",
                "amount_rub": 3000,
                "due_at": due.isoformat(),
            }
        ],
    )
    stats = run_due_tick(repo, now=now)
    assert stats["due_soon"] == 1
    assert CHECK_PAYMENT_TITLE in repo.tasks


def test_due_tick_overdue_draft_not_sent() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    due = now - timedelta(days=2)
    repo = FakeRepo(
        {"b2c_status": "contract_accepted", "clients": {"full_name": "Сергей"}},
        orders=[
            {
                "id": "o2",
                "case_id": "c1",
                "status": "pending",
                "package_code": "DIAG",
                "amount_rub": 3000,
                "due_at": due.isoformat(),
            }
        ],
    )
    stats = run_due_tick(repo, now=now)
    assert stats["overdue_drafts"] == 1
    fields = repo.updated_fields["o2"]
    draft = fields.get("reminder_draft") or ""
    assert fields["next_action"] == "Напомнить клиенту"
    assert "ЕДВ" not in draft
    assert "увеличим" not in draft.lower()
    assert "результат не гарантирован" in draft.lower()


def test_due_tick_skips_test_and_paid() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    repo = FakeRepo(
        {"clients": {"full_name": "Тест Клиент AMO"}},
        orders=[
            {
                "id": "o3",
                "case_id": "c1",
                "status": "pending",
                "package_code": "DIAG",
                "amount_rub": 3000,
                "due_at": (now + timedelta(hours=2)).isoformat(),
            }
        ],
    )
    stats = run_due_tick(repo, now=now)
    assert stats["due_soon"] == 0
    assert CHECK_PAYMENT_TITLE not in repo.tasks


def test_due_tick_idempotent() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    repo = FakeRepo(
        {"clients": {"full_name": "Сергей"}},
        orders=[
            {
                "id": "o4",
                "case_id": "c1",
                "status": "pending",
                "package_code": "DIAG",
                "amount_rub": 3000,
                "due_at": (now + timedelta(hours=5)).isoformat(),
            }
        ],
    )
    first = run_due_tick(repo, now=now)
    second = run_due_tick(repo, now=now)
    assert first["due_soon"] == 1
    assert second["due_soon"] == 0
    assert repo.tasks.count(CHECK_PAYMENT_TITLE) == 1
