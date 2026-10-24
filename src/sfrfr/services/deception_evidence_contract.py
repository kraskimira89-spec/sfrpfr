"""§64–68: доказательства и реакция на подтверждённую ошибку ИИ.

Логическая карточка без новой БД-таблицы. `result_evidence` — суммы пенсии,
не журнал диалоговых доказательств. Оригиналы — только защищённый контур.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final


class EvidenceMaterialKind(StrEnum):
    SOURCE = "source_material"  # сообщение, документ, версия условий
    SYSTEM_EVENT = "system_event"  # создание/запуск/отправка
    ANALYTIC = "analytic_conclusion"  # интерпретация (не самоподтверждение)
    DECISION = "authorized_decision"


class EvidenceType(StrEnum):
    MESSAGE = "message"
    DOCUMENT = "document"
    EVENT = "event"
    TERMS = "terms"
    CALC = "calc"
    DECISION = "decision"


class ErrorConsequenceClass(StrEnum):
    WORDING = "wording_only"
    FALSE_STATUS = "false_work_status"
    WRONG_DATE = "wrong_date_or_period"
    UNSUPPORTED_AMOUNT = "unsupported_amount"
    FALSE_PRE_PAY_PROMISE = "false_pre_pay_promise"
    BAD_APPEAL_DRAFT = "bad_appeal_draft"
    ALREADY_SUBMITTED = "material_already_filed"
    ACCESS_BREACH = "access_or_disclosure"
    UNLAWFUL_EXTERNAL = "unlawful_external_action"


class VerificationState(StrEnum):
    MESSAGE_RECEIVED = "possible_error_message_received"
    EVIDENCE_COLLECTED = "evidence_collected"
    CHECKING = "checking"
    CONFIRMED = "confirmed"
    PARTIAL = "partially_confirmed"
    NOT_IN_SCOPE = "not_confirmed_in_checked_scope"
    INSUFFICIENT = "insufficient_data"
    DECISION = "decision"
    FIXING = "fixing"
    CONSEQUENCES_CHECK = "consequences_check"
    OUTCOME = "outcome"


# Поля §64.2 — логическая схема; persist только после аудита хранилища.
EVIDENCE_CARD_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "links",  # case / order / claim / disputed_point
    "type",
    "source",
    "event_at",
    "ingested_at",
    "version",
    "original_ref",
    "fragment",
    "verified",
    "limitations",
    "dependents",
    "access_roles",
    "retention_policy",
)

ARCHITECTURE_MAP: Final[dict[str, str]] = {
    "evidence_card": "logical_only_no_new_table",
    "result_evidence_table": "pension_amounts_only_do_not_overload",
    "chat_originals": "protected_channel_store_not_git",
    "job_timeline": "existing_check_status_events",
    "staff_decisions": "tracker_and_staff_cabinet",
    "pii_in_tests": "redacted_only",
}

MINIMUM_EVIDENCE_BY_DISPUTE: Final[dict[str, tuple[str, ...]]] = {
    "promised_raise": ("message_with_context", "date", "terms_at_purchase"),
    "check_not_started": ("status_history", "start_events_not_current_only"),
    "wrong_calc": ("inputs", "method", "version", "assumptions", "result"),
    "report_not_delivered": ("file_version", "delivery_events", "availability"),
    "hidden_extra_pay": ("offer_at_order", "price_at_order", "pre_order_messages"),
    "wrong_period_ocr": ("source_image", "ocr_version", "corrected_value"),
    "action_without_consent": ("consent", "authority", "params", "result"),
}


def architecture_gap_allows_new_table() -> bool:
    """Новая сущность — только после доказанного пробела; сейчас пробела нет."""
    return False


def evidence_card_skeleton(
    *,
    evidence_id: str,
    evidence_type: EvidenceType,
    links: dict[str, str],
    original_ref: str,
    fragment: str,
    event_at: str | None = None,
    ingested_at: str | None = None,
    version: str | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "links": dict(links),
        "type": evidence_type.value,
        "source": "system_or_channel",
        "event_at": event_at,
        "ingested_at": ingested_at,
        "version": version,
        "original_ref": original_ref,
        "fragment": fragment,
        "verified": None,
        "limitations": list(limitations or []),
        "dependents": [],
        "access_roles": ["assignee", "owner"],
        "retention_policy": "approved_policy_only",
        "kind_layer": EvidenceMaterialKind.SOURCE.value,
    }


def may_overwrite_original_to_hide_error() -> bool:
    return False


def may_invent_missing_history() -> bool:
    return False


def may_backdate_missing_events() -> bool:
    return False


def may_treat_regen_as_proof() -> bool:
    """Повторная генерация ≠ доказательство правильности."""
    return False


def may_store_hidden_model_reasoning() -> bool:
    return False


def may_put_client_pii_in_git_or_public_report() -> bool:
    return False


def may_copy_full_document_into_journal() -> bool:
    return False


def ai_output_reproducibility_fields() -> tuple[str, ...]:
    return (
        "model_or_policy_version",
        "template_version",
        "material_refs",
        "tools_and_results",
        "final_reply",
        "calc_engine_version_if_any",
    )


def confirmed_error_record(
    *,
    wrong_assertion: str,
    confirmed_by: list[str],
    correct_fact: str | None,
    still_unknown: list[str],
    affected: list[str],
) -> dict[str, Any]:
    return {
        "wrong_assertion": wrong_assertion,
        "confirmed_by": list(confirmed_by),
        "correct_fact": correct_fact,
        "still_unknown": list(still_unknown),
        "affected": list(affected),
        "label_whole_case_wrong": False,
    }


def first_actions_on_confirmed_error() -> tuple[str, ...]:
    return (
        "limit_repeat_of_wrong_claim",
        "preserve_evidence",
        "map_dependents",
        "mark_affected_needs_recheck",
        "create_assignee_work",
        "tell_client_fact_and_next_step",
    )


def may_leave_wrong_result_as_current_after_apology() -> bool:
    return False


def consequence_reaction(cls: ErrorConsequenceClass) -> str:
    return {
        ErrorConsequenceClass.WORDING: "fix_text_check_context",
        ErrorConsequenceClass.FALSE_STATUS: "fix_display_restore_timeline",
        ErrorConsequenceClass.WRONG_DATE: "fix_fact_recheck_dependents",
        ErrorConsequenceClass.UNSUPPORTED_AMOUNT: (
            "clear_confirmed_amount_recheck_calc"
        ),
        ErrorConsequenceClass.FALSE_PRE_PAY_PROMISE: (
            "assess_order_impact_and_claim"
        ),
        ErrorConsequenceClass.BAD_APPEAL_DRAFT: (
            "restrict_version_hand_to_review"
        ),
        ErrorConsequenceClass.ALREADY_SUBMITTED: (
            "establish_filing_fact_specialist_decides"
        ),
        ErrorConsequenceClass.ACCESS_BREACH: "security_incident_process",
        ErrorConsequenceClass.UNLAWFUL_EXTERNAL: (
            "emergency_procedure_then_authorized"
        ),
    }[cls]


def may_auto_refund_or_change_prod_as_error_fix() -> bool:
    return False


def client_confirmed_error_reply_parts() -> tuple[str, ...]:
    return (
        "date_and_wrong_fact",
        "confirmed_correction",
        "our_error_apology",
        "known_impact",
        "done_and_next_step",
        "remaining_uncertainty_if_any",
    )


def payment_impact_ai_duties() -> tuple[str, ...]:
    return (
        "admit_specific_false_promise_if_confirmed",
        "register_client_demand",
        "hand_execution_refund_to_assignee",
        "no_promise_of_outcome",
        "no_demand_to_drop_complaint_or_review",
        "no_upsell_instead_of_review",
    )


def may_tech_fix_close_finance_claim() -> bool:
    return False


def scale_check_steps() -> tuple[str, ...]:
    return (
        "cause_template_gen_data_ocr_calc_or_transition",
        "repeat_risk",
        "other_results_at_risk",
        "sample_or_full_recheck_need",
        "no_blast_notify_all_clients",
    )


def closure_planes_are_separate() -> dict[str, tuple[str, ...]]:
    """Техдефект ≠ последствия в деле ≠ претензия."""
    return {
        "tech_defect_done": (
            "cause_fixed",
            "repro_test_added",
            "regression_ok",
            "approved_deploy_checked",
        ),
        "case_consequences_done": (
            "dependents_checked",
            "current_versions_available",
            "required_actions_done",
            "client_got_correct_explanation",
        ),
        "claim_done": ("own_claim_process",),
        "client_thanks_not_enough": ("thanks_is_not_execution_proof",),
    }


def verification_pipeline() -> tuple[str, ...]:
    return tuple(s.value for s in VerificationState)


def statuses_must_not_collapse() -> tuple[str, ...]:
    return (
        "error_fixed",
        "client_notified",
        "refund_done",
        "claim_closed",
    )


def link_correction_to_original(
    *,
    original_evidence_id: str,
    correction_id: str,
) -> dict[str, str]:
    return {
        "original_id": original_evidence_id,
        "correction_id": correction_id,
        "overwrite_original": "forbidden",
    }


def mark_stale_after_error(dependents: list[str]) -> dict[str, str]:
    return {d: "needs_recheck" for d in dependents}
