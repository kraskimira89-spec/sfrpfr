"""SFRFR-110 §70–72: переходы, статусы доказательств, частичные сбои."""

from __future__ import annotations

from sfrfr.services.deception_accusation_policy import integration_transition_order
from sfrfr.services.deception_transition_refine import (
    AUDIT_SENSITIVE_OPS,
    CHRONOLOGY_FIELDS,
    EVIDENCE_LINK_CHAIN,
    EVIDENCE_ROLE_FIELDS,
    EvidenceLifecycleStatus,
    announce_fix_allowed,
    claim_intake_order,
    closure_contour_criteria,
    dual_fix_planes,
    dual_presentation_kinds,
    export_must_exclude,
    insufficient_data_goes_to,
    late_event_must_flag_late_entry,
    mark_evidence_status,
    may_announce_fixed_on_partial_persist_failure,
    may_client_or_ai_silently_edit_history,
    may_close_all_contours_in_one_action,
    may_create_duplicate_claim_on_retry,
    may_drop_claim_due_to_access_check,
    may_invent_evidence_ref_when_store_failed,
    may_promote_received_to_checked_without_record,
    may_put_secrets_in_audit_payload,
    may_require_full_proof_before_claim_registration,
    may_treat_read_as_acceptance,
    may_treat_sent_as_read,
    may_use_registered_at_as_unknown_event_at,
    notification_transition_order,
    operation_idempotency_requires_op_id,
    provisional_mark_is_not_error_admission,
    provisional_restriction_order,
    refined_error_pipeline,
)


def test_claim_before_full_evidence() -> None:
    order = claim_intake_order()
    assert order.index("registered_by_process") < order.index(
        "evidence_collect_and_check"
    )
    assert may_require_full_proof_before_claim_registration() is False
    assert may_drop_claim_due_to_access_check() is False


def test_provisional_and_dual_fix() -> None:
    assert provisional_restriction_order()[1] == "mark_needs_recheck"
    assert provisional_mark_is_not_error_admission() is True
    planes = dual_fix_planes()
    assert planes["template_fix_updates_old_reports"] == "false"
    assert planes["one_report_fix_proves_system_cause"] == "false"


def test_notification_and_closure() -> None:
    n = notification_transition_order()
    assert n.index("notification_sent") > n.index("fix_saved")
    assert may_treat_sent_as_read() is False
    assert may_treat_read_as_acceptance() is False
    assert len(closure_contour_criteria()) == 5
    assert may_close_all_contours_in_one_action() is False


def test_refined_pipeline_wired() -> None:
    pipe = refined_error_pipeline()
    assert pipe[0] == "possible_error_message"
    assert "register_needed_claims" in pipe
    assert pipe[-1] == "separate_closure_checks"
    assert integration_transition_order() == pipe
    assert insufficient_data_goes_to() == "needs_clarification_not_no_error"


def test_evidence_roles_chrono_status() -> None:
    assert "disputed_point" in EVIDENCE_LINK_CHAIN
    assert "verified_by" in EVIDENCE_ROLE_FIELDS
    assert "late_entry_flag" in CHRONOLOGY_FIELDS
    assert late_event_must_flag_late_entry() is True
    assert may_use_registered_at_as_unknown_event_at() is False
    blocked = mark_evidence_status(
        current=EvidenceLifecycleStatus.RECEIVED,
        promote_to=EvidenceLifecycleStatus.CHECKED_IN_SCOPE,
        check_record_exists=False,
    )
    assert blocked["ok"] is False
    ok = mark_evidence_status(
        current=EvidenceLifecycleStatus.RECEIVED,
        promote_to=EvidenceLifecycleStatus.CHECKED_IN_SCOPE,
        check_record_exists=True,
    )
    assert ok["status"] == EvidenceLifecycleStatus.CHECKED_IN_SCOPE.value
    assert may_promote_received_to_checked_without_record() is False


def test_audit_idempotency_partial_fail() -> None:
    assert "view_sensitive" in AUDIT_SENSITIVE_OPS
    assert may_put_secrets_in_audit_payload() is False
    assert may_client_or_ai_silently_edit_history() is False
    assert operation_idempotency_requires_op_id() is True
    assert may_create_duplicate_claim_on_retry() is False
    assert may_announce_fixed_on_partial_persist_failure() is False
    assert may_invent_evidence_ref_when_store_failed() is False
    fail = announce_fix_allowed(
        persist_ok=False, cause_fixed=True, consequences_checked=True
    )
    assert fail["may_say_fixed"] is False
    partial = announce_fix_allowed(
        persist_ok=True, cause_fixed=True, consequences_checked=False
    )
    assert partial["cause_only"] is True
    assert partial["may_say_fixed"] is False


def test_dual_presentation_export() -> None:
    assert set(dual_presentation_kinds()) == {
        "client_summary",
        "authorized_audit_pack",
    }
    assert "other_clients_data" in export_must_exclude()
    assert "secrets" in export_must_exclude()
