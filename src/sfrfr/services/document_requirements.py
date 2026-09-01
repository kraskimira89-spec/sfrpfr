"""Динамические требования к документам по сценарию дела."""

from __future__ import annotations

from typing import Any

# Коды сценариев (case_scenarios.scenario_code)
SCENARIO_NAME_CHANGE = "name_change"
SCENARIO_CHILDREN_CARE = "children_care"
SCENARIO_ADOPTION_GUARDIANSHIP = "adoption_or_guardianship"
SCENARIO_MILITARY = "military_service"
SCENARIO_DISABILITY_CARE = "disability_or_80plus_care"
SCENARIO_NORTHERN = "northern_or_preferential_service"
SCENARIO_LIQUIDATED = "liquidated_employer_or_archive"
SCENARIO_SFR_RESPONSE = "sfr_response_or_refusal"
SCENARIO_REPRESENTATIVE = "representative"
SCENARIO_PENSION_ASSIGNED = "pension_assigned"
SCENARIO_BANK_LIMITED = "bank_statement_limited"
SCENARIO_PAYOUT_RECONCILIATION = "payout_reconciliation"

ALL_SCENARIO_CODES: frozenset[str] = frozenset(
    {
        SCENARIO_NAME_CHANGE,
        SCENARIO_CHILDREN_CARE,
        SCENARIO_ADOPTION_GUARDIANSHIP,
        SCENARIO_MILITARY,
        SCENARIO_DISABILITY_CARE,
        SCENARIO_NORTHERN,
        SCENARIO_LIQUIDATED,
        SCENARIO_SFR_RESPONSE,
        SCENARIO_REPRESENTATIVE,
        SCENARIO_PENSION_ASSIGNED,
        SCENARIO_BANK_LIMITED,
        SCENARIO_PAYOUT_RECONCILIATION,
    }
)

# Слот work map → сценарии, при которых слот виден клиенту
_SLOT_SCENARIO_MAP: dict[str, frozenset[str]] = {
    "passport": frozenset({SCENARIO_REPRESENTATIVE}),
    "sfr_size": frozenset({SCENARIO_PENSION_ASSIGNED}),
    "sfr_pay": frozenset({SCENARIO_PENSION_ASSIGNED}),
    "bank": frozenset({SCENARIO_BANK_LIMITED}),
    "children": frozenset({SCENARIO_CHILDREN_CARE}),
    "marriage": frozenset({SCENARIO_NAME_CHANGE}),
    "military": frozenset({SCENARIO_MILITARY}),
    "north": frozenset({SCENARIO_NORTHERN}),
    "archive": frozenset({SCENARIO_LIQUIDATED}),
    "sfr": frozenset({SCENARIO_SFR_RESPONSE}),
}

# Дополнительный слот опеки (ключ в work map)
GUARDIANSHIP_SLOT_KEY = "guardianship"

GUARDIANSHIP_SLOT: dict[str, Any] = {
    "key": GUARDIANSHIP_SLOT_KEY,
    "title": "Документы об опеке / попечительстве",
    "need": "conditional",
    "need_label": "По ситуации",
    "doc_type": "guardianship",
}

BANK_REQUIREMENT_CODE = "bank_statement_limited"
LABOR_TRANSCRIPTION_CODE = "employment_record_transcription"

BANK_STAFF_TITLE = "Дополнительный финансовый документ — только по запросу специалиста"


def active_scenario_codes(rows: list[Any] | None) -> set[str]:
    out: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if not row.get("active", True):
            continue
        code = str(row.get("scenario_code") or "").strip()
        if code in ALL_SCENARIO_CODES:
            out.add(code)
    return out


def staff_requested_codes(checklist_items: list[Any] | None) -> set[str]:
    out: set[str] = set()
    for item in checklist_items or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("category") or "") != "staff_requested":
            continue
        if item.get("status") in ("done", "cancelled"):
            continue
        code = str(item.get("requirement_code") or "").strip()
        if code:
            out.add(code)
    return out


def slot_visible(
    slot_key: str,
    *,
    active_scenarios: set[str],
    staff_codes: set[str],
    has_uploaded: bool,
) -> bool:
    """Показывать ли слот в клиентском чек-листе."""
    if slot_key in {"ils", "labor", "extra"}:
        return True
    if slot_key == "bank":
        return (
            SCENARIO_BANK_LIMITED in active_scenarios
            or SCENARIO_PAYOUT_RECONCILIATION in active_scenarios
            or BANK_REQUIREMENT_CODE in staff_codes
        )
    if slot_key == GUARDIANSHIP_SLOT_KEY:
        return SCENARIO_ADOPTION_GUARDIANSHIP in active_scenarios or has_uploaded
    required_scenarios = _SLOT_SCENARIO_MAP.get(slot_key)
    if required_scenarios is None:
        # optional: archive, education — показываем при наличии файла или всегда как «при наличии»
        if slot_key in {"archive", "education"}:
            return True
        return has_uploaded
    if active_scenarios & required_scenarios:
        return True
    return has_uploaded


def scenarios_from_questionnaire(answers: dict[str, Any]) -> set[str]:
    """Построить набор сценариев из короткой анкеты кабинета."""
    out: set[str] = set()
    if answers.get("name_changed"):
        out.add(SCENARIO_NAME_CHANGE)
    if answers.get("children_care"):
        out.add(SCENARIO_CHILDREN_CARE)
    if answers.get("adoption_or_guardianship"):
        out.add(SCENARIO_ADOPTION_GUARDIANSHIP)
    if answers.get("military_service"):
        out.add(SCENARIO_MILITARY)
    if answers.get("disability_or_80plus_care"):
        out.add(SCENARIO_DISABILITY_CARE)
    if answers.get("northern_or_preferential"):
        out.add(SCENARIO_NORTHERN)
    if answers.get("liquidated_employer"):
        out.add(SCENARIO_LIQUIDATED)
    if answers.get("sfr_response_or_refusal"):
        out.add(SCENARIO_SFR_RESPONSE)
    if answers.get("representative"):
        out.add(SCENARIO_REPRESENTATIVE)
    if answers.get("pension_assigned"):
        out.add(SCENARIO_PENSION_ASSIGNED)
    if answers.get("payout_reconciliation"):
        out.add(SCENARIO_PAYOUT_RECONCILIATION)
    return out & ALL_SCENARIO_CODES


def checklist_rows_for_scenarios(
    scenarios: set[str],
    *,
    staff_bank: bool = False,
) -> list[dict[str, Any]]:
    """Создать условные пункты чек-листа для новых сценариев."""
    rows: list[dict[str, Any]] = []
    mapping: list[tuple[str, str, str]] = [
        (SCENARIO_NAME_CHANGE, "marriage_cert", "Свидетельство о браке / перемене имени"),
        (SCENARIO_CHILDREN_CARE, "children_birth", "Свидетельства о рождении детей"),
        (
            SCENARIO_ADOPTION_GUARDIANSHIP,
            "guardianship_docs",
            "Документы об опеке / попечительстве",
        ),
        (SCENARIO_MILITARY, "military_docs", "Военный билет / справка о службе"),
        (SCENARIO_NORTHERN, "north_docs", "Справки по северному / льготному стажу"),
        (SCENARIO_LIQUIDATED, "archive_docs", "Архивные справки с мест работы"),
        (SCENARIO_SFR_RESPONSE, "sfr_response", "Ответ / отказ СФР и приложения"),
        (SCENARIO_REPRESENTATIVE, "representative_docs", "Доверенность / представительство"),
        (SCENARIO_PENSION_ASSIGNED, "pension_size", "Справка о размере пенсии"),
        (SCENARIO_PENSION_ASSIGNED, "sfr_payments", "Справка о выплатах СФР за период"),
    ]
    order = 10
    for scenario, req_code, title in mapping:
        if scenario not in scenarios:
            continue
        rows.append(
            {
                "title": title,
                "item_type": "document",
                "owner": "client",
                "requirement_code": req_code,
                "scenario_code": scenario,
                "category": "conditional",
                "is_required_now": False,
                "sort_order": order,
            }
        )
        order += 1
    bank_scenario = (
        staff_bank
        or SCENARIO_BANK_LIMITED in scenarios
        or SCENARIO_PAYOUT_RECONCILIATION in scenarios
    )
    if bank_scenario:
        rows.append(
            {
                "title": BANK_STAFF_TITLE,
                "item_type": "document",
                "owner": "client",
                "requirement_code": BANK_REQUIREMENT_CODE,
                "scenario_code": SCENARIO_BANK_LIMITED,
                "category": "staff_requested",
                "is_required_now": True,
                "consent_required": True,
                "sort_order": order,
            }
        )
    return rows
