"""§70–71: уточнение переходов и доказательств (без второго реестра / миграций)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final


class EvidenceLifecycleStatus(StrEnum):
    RECEIVED = "received"
    READABLE = "readable"
    CHECKED_IN_SCOPE = "checked_in_stated_scope"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded_by_new_version"
    UNAVAILABLE = "unavailable_or_corrupt"


class ClosureContour(StrEnum):
    TECH_DEFECT = "tech_defect"
    CASE_RESULTS = "case_results"
    CLIENT_DEMAND = "client_demand"
    COMMUNICATION = "communication"
    PENSION_QUESTION = "pension_question"


EVIDENCE_LINK_CHAIN: Final[tuple[str, ...]] = (
    "disputed_point",
    "source_messages_docs",
    "conclusion_version",
    "check_event",
    "assignee_decision",
    "corrected_version",
    "execution_proof",
    "client_notification",
)

EVIDENCE_ROLE_FIELDS: Final[tuple[str, ...]] = (
    "reported_by",
    "material_origin",
    "uploaded_by",
    "verified_by",
    "verifier_authority",
)

CHRONOLOGY_FIELDS: Final[tuple[str, ...]] = (
    "event_at",
    "received_at",
    "registered_at",
    "time_source",
    "operation_author",
    "prior_event_or_version_ref",
    "late_entry_flag",
)

AUDIT_SENSITIVE_OPS: Final[tuple[str, ...]] = (
    "view_sensitive",
    "export",
    "relink_case",
    "create_version",
    "change_currency_flag",
    "decision_taken",
    "change_access",
    "delete_or_retention_limit",
)


def claim_intake_order() -> tuple[str, ...]:
    """§70.1 — регистрация до полной проверки доказательств."""
    return (
        "message_received",
        "saved_in_allowed_store",
        "demands_extracted",
        "registered_by_process",
        "evidence_collect_and_check",
    )


def may_require_full_proof_before_claim_registration() -> bool:
    return False


def may_drop_claim_due_to_access_check() -> bool:
    """Доступ ограничивает раскрытие, не стирает обращение."""
    return False


def provisional_restriction_order() -> tuple[str, ...]:
    """§70.2 — временное ограничение до окончательного вывода."""
    return (
        "material_error_signal",
        "mark_needs_recheck",
        "limit_dependent_action_per_policy",
        "full_check",
        "confirm_error_or_restore_currency",
    )


def provisional_mark_is_not_error_admission() -> bool:
    return True


def dual_fix_planes() -> dict[str, str]:
    """§70.3 — причина и последствия независимы."""
    return {
        "cause_fixed": "template_data_calc_transition_or_component",
        "consequences_fixed": "affected_materials_and_actions_checked",
        "template_fix_updates_old_reports": "false",
        "one_report_fix_proves_system_cause": "false",
    }


def notification_transition_order() -> tuple[str, ...]:
    """§70.4 — уведомление отдельный переход."""
    return (
        "fix_prepared",
        "fix_verified",
        "fix_saved",
        "available_to_authorized_client",
        "notification_sent",
        "delivery_status_known_scope",
    )


def may_treat_sent_as_read() -> bool:
    return False


def may_treat_read_as_acceptance() -> bool:
    return False


def closure_contour_criteria() -> dict[str, str]:
    return {
        ClosureContour.TECH_DEFECT.value: "cause_fixed_and_verified",
        ClosureContour.CASE_RESULTS.value: (
            "dependents_checked_current_versions_available"
        ),
        ClosureContour.CLIENT_DEMAND.value: "decision_executed_on_own_process",
        ClosureContour.COMMUNICATION.value: (
            "correct_outcome_delivered_or_undeliverable_logged"
        ),
        ClosureContour.PENSION_QUESTION.value: (
            "factual_result_or_kept_open_separately"
        ),
    }


def may_close_all_contours_in_one_action() -> bool:
    return False


def refined_error_pipeline() -> tuple[str, ...]:
    """Итоговая схема §70."""
    return (
        "possible_error_message",
        "preserve_message_and_demands",
        "register_needed_claims",
        "assess_misuse_risk",
        "optional_targeted_restriction",
        "collect_and_check_evidence",
        "finding_per_point",
        "authorized_decision",
        "fix_cause",
        "check_and_fix_consequences",
        "provide_current_result",
        "notify_client",
        "separate_closure_checks",
    )


def insufficient_data_goes_to() -> str:
    return "needs_clarification_not_no_error"


def evidence_status_may_call_trustworthy_from_file_ok_only() -> bool:
    return False


def may_promote_received_to_checked_without_record() -> bool:
    return False


def may_put_secrets_in_audit_payload() -> bool:
    return False


def may_client_or_ai_silently_edit_history() -> bool:
    return False


def may_create_duplicate_claim_on_retry() -> bool:
    return False


def may_announce_fixed_on_partial_persist_failure() -> bool:
    return False


def may_invent_evidence_ref_when_store_failed() -> bool:
    return False


def late_event_must_flag_late_entry() -> bool:
    return True


def may_use_registered_at_as_unknown_event_at() -> bool:
    return False


def dual_presentation_kinds() -> tuple[str, ...]:
    return ("client_summary", "authorized_audit_pack")


def export_must_exclude() -> tuple[str, ...]:
    return (
        "other_clients_data",
        "secrets",
        "internal_not_for_recipient",
        "signed_temp_urls_in_public_systems",
    )


def operation_idempotency_requires_op_id() -> bool:
    return True


def mark_evidence_status(
    *,
    current: EvidenceLifecycleStatus,
    promote_to: EvidenceLifecycleStatus,
    check_record_exists: bool,
) -> dict[str, Any]:
    if (
        promote_to == EvidenceLifecycleStatus.CHECKED_IN_SCOPE
        and not check_record_exists
    ):
        return {
            "ok": False,
            "status": current.value,
            "reason": "no_check_record",
        }
    return {"ok": True, "status": promote_to.value, "reason": "ok"}


def announce_fix_allowed(
    *,
    persist_ok: bool,
    cause_fixed: bool,
    consequences_checked: bool,
) -> dict[str, Any]:
    if not persist_ok:
        return {
            "may_say_fixed": False,
            "reason": "persist_failed",
        }
    return {
        "may_say_fixed": cause_fixed and consequences_checked,
        "cause_only": cause_fixed and not consequences_checked,
        "reason": "ok" if cause_fixed and consequences_checked else "partial",
    }
