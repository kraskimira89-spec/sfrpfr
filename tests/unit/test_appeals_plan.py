"""План обращений: группировка и шапка."""

from __future__ import annotations

import pytest

from sfrfr.services.appeals_plan import (
    AppealsPlanError,
    can_merge_problems,
    header_gate,
    plan_table_markdown,
    validate_appeals_plan,
)


def test_cannot_merge_on_agency_alone() -> None:
    assert (
        can_merge_problems(
            same_addressee=True,
            same_question_kind=False,
            compatible_requests=True,
        )
        is False
    )
    assert (
        can_merge_problems(
            same_addressee=True,
            same_question_kind=True,
            compatible_requests=True,
        )
        is True
    )


def test_homogeneous_periods_one_appeal() -> None:
    plan = validate_appeals_plan(
        {
            "version": 1,
            "problems": [
                {
                    "id": "p1",
                    "fact": "период 1995–1998 не учтён",
                    "period": "1995-1998",
                    "status": "in_appeal",
                },
                {
                    "id": "p2",
                    "fact": "период 1999–2001 не учтён",
                    "period": "1999-2001",
                    "status": "in_appeal",
                },
            ],
            "appeals": [
                {
                    "id": "a1",
                    "addressee": "СФР, территориальный орган",
                    "topic": "Учёт стажа по периодам",
                    "doc_type": "application",
                    "problem_ids": ["p1", "p2"],
                    "requests": ["внести периоды в ИЛС"],
                    "merge_reason": "один адресат, однотипные расхождения по стажу",
                    "submit_order": 1,
                }
            ],
        }
    )
    assert len(plan["appeals"]) == 1
    assert plan["appeals"][0]["problem_ids"] == ["p1", "p2"]
    md = plan_table_markdown(plan)
    assert "План обращений" in md
    assert "СФР" in md


def test_heterogeneous_must_split() -> None:
    plan = validate_appeals_plan(
        {
            "problems": [
                {"id": "p1", "fact": "уточнить сведения ИЛС", "status": "in_appeal"},
                {
                    "id": "p2",
                    "fact": "обжаловать отказ от 01.09.2026",
                    "status": "in_appeal",
                },
            ],
            "appeals": [
                {
                    "addressee": "СФР",
                    "topic": "Уточнение сведений",
                    "problem_ids": ["p1"],
                    "split_reason": "другой предмет и процедура",
                    "submit_order": 1,
                },
                {
                    "addressee": "СФР",
                    "topic": "Обжалование отказа",
                    "doc_type": "complaint",
                    "problem_ids": ["p2"],
                    "split_reason": "обжалование решения ≠ уточнение сведений",
                    "submit_order": 2,
                },
            ],
        }
    )
    assert len(plan["appeals"]) == 2


def test_clarify_without_fake_addressee() -> None:
    plan = validate_appeals_plan(
        {
            "problems": [
                {
                    "id": "p1",
                    "fact": "нужна архивная справка, адресат неясен",
                    "status": "need_clarify",
                }
            ],
            "appeals": [],
        }
    )
    assert plan["problems"][0]["status"] == "need_clarify"
    assert "Нужно уточнить" in plan_table_markdown(plan)


def test_header_gate_blocks_ready() -> None:
    g = header_gate(
        organ_name=None,
        organ_address="г. N",
        applicant_fio="Иванов",
        representative="Петров",
        representation_confirmed=False,
    )
    assert g["ready_to_file"] is False
    assert "organ_name" in g["missing_header_fields"]
    assert "representation_basis" in g["missing_header_fields"]


def test_missing_problem_id_fails() -> None:
    with pytest.raises(AppealsPlanError, match="unknown problem_id"):
        validate_appeals_plan(
            {
                "problems": [{"id": "p1", "fact": "x", "status": "in_appeal"}],
                "appeals": [
                    {
                        "addressee": "СФР",
                        "topic": "t",
                        "problem_ids": ["p9"],
                    }
                ],
            }
        )
