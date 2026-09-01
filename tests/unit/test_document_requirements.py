"""Тесты динамических требований к документам."""

from __future__ import annotations

from sfrfr.services.client_work_map import document_slots
from sfrfr.services.document_requirements import (
    BANK_REQUIREMENT_CODE,
    SCENARIO_CHILDREN_CARE,
    SCENARIO_PENSION_ASSIGNED,
    scenarios_from_questionnaire,
    slot_visible,
)


def test_only_ils_and_labor_without_scenarios() -> None:
    slots, uploaded, total = document_slots([], [])
    keys = {s["key"] for s in slots}
    assert "ils" in keys
    assert "labor" in keys
    assert "bank" not in keys
    assert "sfr_size" not in keys
    assert uploaded == 0
    assert total == 2


def test_pension_scenario_shows_sfr_slots() -> None:
    scenarios = [{"scenario_code": SCENARIO_PENSION_ASSIGNED, "active": True}]
    slots, _u, _t = document_slots([], [], scenario_rows=scenarios)
    keys = {s["key"] for s in slots}
    assert "sfr_size" in keys
    assert "sfr_pay" in keys
    assert "bank" not in keys


def test_bank_only_with_staff_request() -> None:
    checklist = [
        {
            "requirement_code": BANK_REQUIREMENT_CODE,
            "category": "staff_requested",
            "status": "open",
        }
    ]
    slots, _u, _t = document_slots([], checklist)
    keys = {s["key"] for s in slots}
    assert "bank" in keys


def test_children_scenario_from_questionnaire() -> None:
    codes = scenarios_from_questionnaire({"children_care": True})
    assert SCENARIO_CHILDREN_CARE in codes


def test_slot_visible_requires_scenario() -> None:
    assert slot_visible("children", active_scenarios=set(), staff_codes=set(), has_uploaded=False) is False
    assert (
        slot_visible(
            "children",
            active_scenarios={SCENARIO_CHILDREN_CARE},
            staff_codes=set(),
            has_uploaded=False,
        )
        is True
    )
