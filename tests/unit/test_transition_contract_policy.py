"""SFRFR-110 §49–59: переходы сказано → выполнено → подтверждено."""

from __future__ import annotations

from sfrfr.services.transition_contract_policy import (
    CheckFork,
    ClosureKind,
    OfficialOutcome,
    ResultDomain,
    after_check_fork,
    after_official_reply,
    check_status_client_label,
    closure_label,
    compound_refuse_calc_claim_outcomes,
    domains_are_independent,
    may_announce_check_from_llm_phrase_alone,
    may_announce_running_when_queued,
    may_auto_route_refuse_to_court,
    may_auto_supplement_external_after_local_update,
    may_blind_retry_unknown_external_outcome,
    may_close_domain_via_another,
    may_offer_on_stale_conclusion,
    may_recommend_old_draft_while_stale,
    may_say_case_fully_checked_while_stale,
    may_show_stale_amount_as_current,
    may_treat_file_created_as_delivered,
    may_treat_partial_reply_as_all_periods_done,
    may_treat_pause_as_success,
    may_treat_project_as_submitted,
    may_treat_upload_as_check_started,
    may_use_single_success_flag,
    on_new_fact_invalidate,
    parallel_event_effects,
    pause_snapshot_fields,
    reply_has_banned_transition_announce,
    return_from_pause_steps,
    transition_gate,
)


def test_three_domains_independent() -> None:
    assert domains_are_independent() is True
    assert (
        may_close_domain_via_another(
            ResultDomain.SERVICE_ORDER, ResultDomain.PENSION_CASE
        )
        is False
    )


def test_queued_is_not_running() -> None:
    assert check_status_client_label("queued") == "queued_waiting"
    assert may_announce_running_when_queued("queued") is False
    assert may_announce_running_when_queued("running") is True


def test_upload_and_llm_not_enough() -> None:
    assert may_treat_upload_as_check_started() is False
    assert may_announce_check_from_llm_phrase_alone() is False
    assert may_treat_project_as_submitted() is False
    assert may_treat_file_created_as_delivered() is False


def test_check_forks() -> None:
    d = after_check_fork(CheckFork.DISCREPANCY)
    assert "promise_raise" in d["forbid"]
    n = after_check_fork(CheckFork.NOT_CONFIRMED)
    assert "new_paid_stage_for_funnel" in n["forbid"]
    c = after_check_fork(CheckFork.CONTRADICTION)
    assert "put_as_undisputed_in_appeal" in c["forbid"]


def test_official_outcomes() -> None:
    assert after_official_reply(OfficialOutcome.REFUSED)["next"].startswith(
        "parse_grounds"
    )
    assert may_auto_route_refuse_to_court() is False
    assert may_treat_partial_reply_as_all_periods_done() is False


def test_parallel_refuse_keeps_order() -> None:
    eff = parallel_event_effects("refuse_next_pay")
    assert "offer" in eff["changes"]
    assert "current_order" in eff["keeps"]


def test_transition_gate_unknown_and_fail() -> None:
    unk = transition_gate(
        client_want="refund",
        case_or_order_ref="o1",
        has_access=True,
        entry_conditions_met=True,
        needs_consent=False,
        consent_given=False,
        already_done=False,
        action_succeeded=None,
    )
    assert unk["blind_retry"] is False
    assert may_blind_retry_unknown_external_outcome() is False
    fail = transition_gate(
        client_want="register",
        case_or_order_ref="o1",
        has_access=True,
        entry_conditions_met=True,
        needs_consent=False,
        consent_given=False,
        already_done=False,
        action_succeeded=False,
    )
    assert fail["say_ready"] is False
    ok = transition_gate(
        client_want="deliver",
        case_or_order_ref="o1",
        has_access=True,
        entry_conditions_met=True,
        needs_consent=False,
        consent_given=False,
        already_done=False,
        action_succeeded=True,
    )
    assert ok["allow_action"] is True
    assert ok["announce"] == "confirmed_result_only"


def test_stale_fact_rules() -> None:
    assert on_new_fact_invalidate(["calc", "draft"]) == {
        "calc": "needs_recheck",
        "draft": "needs_recheck",
    }
    assert may_show_stale_amount_as_current() is False
    assert may_recommend_old_draft_while_stale() is False
    assert may_offer_on_stale_conclusion() is False
    assert may_say_case_fully_checked_while_stale() is False
    assert may_auto_supplement_external_after_local_update() is False


def test_pause_and_return() -> None:
    assert "confirmed_deadlines" in pause_snapshot_fields()
    assert may_treat_pause_as_success() is False
    assert return_from_pause_steps()[0] == "check_access"


def test_compound_and_closures() -> None:
    out = compound_refuse_calc_claim_outcomes()
    assert "reoffer_tariff" in out["forbid"]
    assert may_use_single_success_flag() is False
    assert "открыт" in closure_label(ClosureKind.SERVICE_DONE_CASE_OPEN).casefold()


def test_banned_announce() -> None:
    assert reply_has_banned_transition_announce("Заявление подано без подтверждения")
    assert not reply_has_banned_transition_announce(
        "Статус проверки: в очереди. Запуск ещё не подтверждён."
    )
