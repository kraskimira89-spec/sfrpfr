"""Переходы дела: сказано клиенту ≠ выполнено ≠ подтверждено (§49–59).

Сопоставление с client_case_status / check_status; без новой схемы БД.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final


class ResultDomain(StrEnum):
    PENSION_CASE = "pension_case"
    SERVICE_ORDER = "service_order"
    CONVERSATION = "conversation"


class CheckFork(StrEnum):
    DISCREPANCY = "discrepancy"  # А
    NEED_EVIDENCE = "need_evidence"  # Б
    CONTRADICTION = "contradiction"  # В
    NOT_CONFIRMED = "not_confirmed"  # Г


class OfficialOutcome(StrEnum):
    GRANTED = "granted"
    PARTIAL = "partial"
    REFUSED = "refused"
    NEED_MORE = "need_more"
    UNCLEAR = "unclear"
    NO_REPLY_YET = "no_reply_yet"


class ClosureKind(StrEnum):
    SERVICE_DONE_CASE_OPEN = "service_done_case_open"
    NO_FURTHER_BASIS = "no_further_basis"
    CLIENT_STOPPED = "client_stopped"
    CLAIM_OPEN = "claim_open"
    PERIOD_OFFICIALLY_COUNTED = "period_officially_counted"
    RECALC_CONFIRMED = "recalc_confirmed"
    NO_CLIENT_REPLY = "no_client_reply"


# Логический этап → что может считаться доказательством в текущем коде
STAGE_EVIDENCE: Final[dict[str, tuple[str, ...]]] = {
    "docs_collected": ("ingest_readable", "bucket_present"),
    "check_planned": ("check_status=queued",),
    "check_running": ("check_status=running",),
    "prelim_result": ("result_artifact_saved", "result_ready"),
    "staff_review": ("staff_job_created", "staff_active"),
    "submitted": ("submission_receipt",),
    "official_reply": ("reply_document_in_case",),
}

BANNED_ANNOUNCE_WITHOUT_PROOF: Final[tuple[str, ...]] = (
    "проверка запущена",  # при отсутствии queued/running
    "уже выполняется",  # при queued
    "передано специалисту",  # без задачи
    "заявление подано",  # без receipt
    "перерасчёт подтверждён",  # без official proof
    "дело успешно завершено",  # при открытом пенсионном вопросе
    "вы приняли работу",  # по молчанию
)


def domains_are_independent() -> bool:
    """Закрытие одной области не закрывает остальные."""
    return True


def may_close_domain_via_another(
    closing: ResultDomain, other: ResultDomain
) -> bool:
    return False if closing != other else True


def check_status_client_label(check_status: str | None) -> str:
    """SFRFR-83: queued ≠ running."""
    s = (check_status or "").strip().lower()
    if s == "queued":
        return "queued_waiting"
    if s == "running":
        return "running"
    if s == "failed":
        return "failed"
    return "unknown"


def may_announce_running_when_queued(check_status: str | None) -> bool:
    return check_status_client_label(check_status) == "running"


def may_announce_check_from_llm_phrase_alone() -> bool:
    return False


def may_treat_upload_as_check_started() -> bool:
    return False


def may_treat_file_created_as_delivered() -> bool:
    return False


def may_treat_project_as_submitted() -> bool:
    return False


def may_treat_partial_reply_as_all_periods_done() -> bool:
    return False


def may_blind_retry_unknown_external_outcome() -> bool:
    return False


def may_auto_route_refuse_to_court() -> bool:
    return False


def may_use_single_success_flag() -> bool:
    return False


def after_check_fork(fork: CheckFork) -> dict[str, Any]:
    routes = {
        CheckFork.DISCREPANCY: {
            "next": ["assess_impact", "plan", "agreed_action"],
            "forbid": ["promise_raise"],
        },
        CheckFork.NEED_EVIDENCE: {
            "next": ["specific_request", "new_doc", "recheck_dependents"],
            "forbid": ["full_restart_if_parts_ok"],
        },
        CheckFork.CONTRADICTION: {
            "next": ["keep_both_sources", "limit_dependents", "clarify_or_specialist"],
            "forbid": ["put_as_undisputed_in_appeal"],
        },
        CheckFork.NOT_CONFIRMED: {
            "next": ["explain_scope", "deliver_result", "end_or_justified_clarify"],
            "forbid": ["new_paid_stage_for_funnel"],
        },
    }
    return routes[fork]


def after_official_reply(outcome: OfficialOutcome) -> dict[str, str]:
    mapping = {
        OfficialOutcome.GRANTED: "verify_what_changed_and_proof",
        OfficialOutcome.PARTIAL: "split_resolved_vs_open",
        OfficialOutcome.REFUSED: "parse_grounds_then_expert_choice",
        OfficialOutcome.NEED_MORE: "list_docs_and_deadlines",
        OfficialOutcome.UNCLEAR: "hand_to_review_no_success_no_refuse",
        OfficialOutcome.NO_REPLY_YET: "check_status_and_rules_no_invented_decision",
    }
    return {"outcome": outcome.value, "next": mapping[outcome]}


def parallel_event_effects(event: str) -> dict[str, Any]:
    """Что меняется / что не меняется молча (§53)."""
    table = {
        "anxiety": {"changes": ["form", "pace"], "keeps": ["evidence", "conclusions"]},
        "aggression": {"changes": ["tone", "routing"], "keeps": ["access", "obligations"]},
        "claim": {"changes": ["claim_process"], "keeps": ["truth_of_dispute"]},
        "refuse_next_pay": {
            "changes": ["offer"],
            "keeps": ["current_order", "pension_result"],
        },
        "pause": {"changes": ["actions", "notices"], "keeps": ["external_deadlines"]},
        "refund_request": {
            "changes": ["finance_process"],
            "keeps": ["refund_executed_flag"],
        },
        "delete_request": {
            "changes": ["data_process"],
            "keeps": ["immediate_wipe_all"],
        },
        "want_specialist": {
            "changes": ["handoff_request"],
            "keeps": ["assigned_answered"],
        },
        "new_document": {
            "changes": ["dependents_freshness"],
            "keeps": ["all_conclusions_unreviewed"],
        },
        "stop_ads": {
            "changes": ["commercial_messages"],
            "keeps": ["all_service_comms_unchecked"],
        },
    }
    return table.get(
        event,
        {"changes": [], "keeps": ["evidence", "conclusions"]},
    )


def transition_gate(
    *,
    client_want: str,
    case_or_order_ref: str,
    has_access: bool,
    entry_conditions_met: bool,
    needs_consent: bool,
    consent_given: bool,
    already_done: bool,
    action_succeeded: bool | None,
) -> dict[str, Any]:
    """Контракт §54 перед действием и сообщением клиенту."""
    if not has_access:
        return {
            "allow_action": False,
            "announce": "access_denied_or_check",
            "reason": "no_access",
        }
    if needs_consent and not consent_given:
        return {
            "allow_action": False,
            "announce": "need_consent",
            "reason": "consent",
        }
    if not entry_conditions_met:
        return {
            "allow_action": False,
            "announce": "entry_not_met",
            "reason": "preconditions",
        }
    if already_done:
        return {
            "allow_action": False,
            "announce": "already_done_idempotent",
            "reason": "duplicate",
        }
    if action_succeeded is None:
        return {
            "allow_action": False,
            "announce": "reconcile_unknown_outcome",
            "reason": "unknown_outcome",
            "blind_retry": False,
        }
    if action_succeeded is False:
        return {
            "allow_action": False,
            "announce": "failed_keep_prior_state",
            "reason": "action_failed",
            "say_ready": False,
        }
    return {
        "allow_action": True,
        "announce": "confirmed_result_only",
        "reason": "ok",
        "client_want": client_want,
        "ref": case_or_order_ref,
    }


def on_new_fact_invalidate(
    dependents: list[str],
) -> dict[str, str]:
    return {d: "needs_recheck" for d in dependents}


def may_recommend_old_draft_while_stale() -> bool:
    return False


def may_show_stale_amount_as_current() -> bool:
    return False


def may_offer_on_stale_conclusion() -> bool:
    return False


def may_say_case_fully_checked_while_stale() -> bool:
    return False


def may_auto_supplement_external_after_local_update() -> bool:
    """Локальное обновление ≠ отправка дополнения во внешнюю систему."""
    return False


def pause_snapshot_fields() -> tuple[str, ...]:
    return (
        "stage",
        "done_obligations",
        "open_questions",
        "confirmed_deadlines",
        "message_settings",
        "next_available_step",
    )


def may_treat_pause_as_success() -> bool:
    return False


def return_from_pause_steps() -> tuple[str, ...]:
    return (
        "check_access",
        "restore_context",
        "new_events",
        "freshness_docs_deadlines",
        "continue_from_fit_stage",
    )


def compound_refuse_calc_claim_outcomes() -> dict[str, Any]:
    """§57: три независимых результата."""
    return {
        "refuse_next_saved": True,
        "calc_marked_for_review": True,
        "claim_registered_or_honest_fail": True,
        "forbid": [
            "close_whole_case",
            "cancel_order_by_guess",
            "reoffer_tariff",
            "only_emotional_support",
        ],
    }


def closure_label(kind: ClosureKind) -> str:
    labels = {
        ClosureKind.SERVICE_DONE_CASE_OPEN: (
            "Текущий заказ завершён; пенсионный вопрос открыт"
        ),
        ClosureKind.NO_FURTHER_BASIS: "Проверка завершена в указанном объёме",
        ClosureKind.CLIENT_STOPPED: "Сопровождение остановлено по выбору клиента",
        ClosureKind.CLAIM_OPEN: "Заказ и претензия имеют отдельные статусы",
        ClosureKind.PERIOD_OFFICIALLY_COUNTED: "Подтверждён конкретный результат учёта",
        ClosureKind.RECALC_CONFIRMED: "Есть основание зафиксировать финансовый результат",
        ClosureKind.NO_CLIENT_REPLY: "Нет ответа; не приёмка и не удовлетворённость",
    }
    return labels[kind]


def reply_has_banned_transition_announce(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_ANNOUNCE_WITHOUT_PROOF)
