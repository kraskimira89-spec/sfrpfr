"""SFRFR-110 §63–68: интеграция, доказательства, реакция на ошибку ИИ."""

from __future__ import annotations

import json
from pathlib import Path

from sfrfr.services.deception_accusation_policy import (
    DeceptionVariant,
    claim_registration_must_not_auto,
    classify_deception_signal,
    integration_transition_order,
    may_keep_spreading_false_claims_while_investigating,
    split_deception_compound,
)
from sfrfr.services.deception_evidence_contract import (
    ARCHITECTURE_MAP,
    EVIDENCE_CARD_FIELDS,
    ErrorConsequenceClass,
    EvidenceType,
    VerificationState,
    ai_output_reproducibility_fields,
    architecture_gap_allows_new_table,
    client_confirmed_error_reply_parts,
    closure_planes_are_separate,
    confirmed_error_record,
    consequence_reaction,
    evidence_card_skeleton,
    first_actions_on_confirmed_error,
    link_correction_to_original,
    mark_stale_after_error,
    may_auto_refund_or_change_prod_as_error_fix,
    may_invent_missing_history,
    may_leave_wrong_result_as_current_after_apology,
    may_overwrite_original_to_hide_error,
    may_put_client_pii_in_git_or_public_report,
    may_tech_fix_close_finance_claim,
    may_treat_regen_as_proof,
    payment_impact_ai_duties,
    scale_check_steps,
    statuses_must_not_collapse,
    verification_pipeline,
)
from sfrfr.services.multi_intent_policy import parse_multi_intent

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


def test_no_competing_branch_and_architecture() -> None:
    assert architecture_gap_allows_new_table() is False
    assert ARCHITECTURE_MAP["result_evidence_table"].startswith("pension")
    assert "id" in EVIDENCE_CARD_FIELDS
    assert "original_ref" in EVIDENCE_CARD_FIELDS


def test_split_compound_four_elements() -> None:
    text = (
        "Вы обманули меня с прибавкой. Больше платить не буду, "
        "верните деньги и исправьте расчёт."
    )
    got = split_deception_compound(text)
    kinds = {e["kind"] for e in got["elements"]}
    assert kinds == {
        "deception_accusation",
        "refuse_new_purchase",
        "refund",
        "fix_calc",
    }
    assert got["competing_claim_branch"] is False
    assert got["single_handoff_reply_forbidden"] is True
    assert classify_deception_signal(text) == DeceptionVariant.PROMISED_RECALC


def test_multi_intent_wires_deception_subtype() -> None:
    parsed = parse_multi_intent(
        "Вы обманули меня с прибавкой. Верните деньги."
    )
    claim = parsed["claim"]
    assert isinstance(claim, dict)
    assert claim["kind"] == "deception_subtype_20_26"
    assert claim["parent_process"] == "20.21"


def test_integration_order_and_side_effects() -> None:
    steps = integration_transition_order()
    assert steps[0] == "possible_error_message"
    assert steps[-1] == "separate_closure_checks"
    assert "register_needed_claims" in steps
    assert "preserve_message_and_demands" in steps
    assert may_keep_spreading_false_claims_while_investigating() is False
    banned = set(claim_registration_must_not_auto())
    assert "cancel_payment" in banned
    assert "admit_calc_wrong" in banned


def test_evidence_card_and_guards() -> None:
    card = evidence_card_skeleton(
        evidence_id="ev_demo_1",
        evidence_type=EvidenceType.MESSAGE,
        links={"case": "case_redacted", "point": "promise"},
        original_ref="protected://msg/redacted",
        fragment="…добьётесь перерасчёта…",
        event_at="2026-01-01T10:00:00Z",
        ingested_at="2026-01-01T10:00:01Z",
        limitations=["context_truncated"],
    )
    assert card["event_at"] != card["ingested_at"]
    assert may_overwrite_original_to_hide_error() is False
    assert may_invent_missing_history() is False
    assert may_treat_regen_as_proof() is False
    assert may_put_client_pii_in_git_or_public_report() is False
    link = link_correction_to_original(
        original_evidence_id="ev_demo_1", correction_id="ev_fix_1"
    )
    assert link["overwrite_original"] == "forbidden"
    assert "model_or_policy_version" in ai_output_reproducibility_fields()


def test_confirmed_error_reaction() -> None:
    rec = confirmed_error_record(
        wrong_assertion="дата начала 1987",
        confirmed_by=["source_image_redacted"],
        correct_fact="1985",
        still_unknown=["итоговая длительность"],
        affected=["duration", "amount_stale"],
    )
    assert rec["label_whole_case_wrong"] is False
    assert "limit_repeat_of_wrong_claim" in first_actions_on_confirmed_error()
    assert may_leave_wrong_result_as_current_after_apology() is False
    assert (
        consequence_reaction(ErrorConsequenceClass.UNSUPPORTED_AMOUNT)
        == "clear_confirmed_amount_recheck_calc"
    )
    assert may_auto_refund_or_change_prod_as_error_fix() is False
    assert "our_error_apology" in client_confirmed_error_reply_parts()
    assert "register_client_demand" in payment_impact_ai_duties()
    assert may_tech_fix_close_finance_claim() is False
    assert "no_blast_notify_all_clients" in scale_check_steps()
    stale = mark_stale_after_error(["amount", "draft"])
    assert stale["amount"] == "needs_recheck"


def test_closure_planes_and_states() -> None:
    planes = closure_planes_are_separate()
    assert "tech_defect_done" in planes
    assert "claim_done" in planes
    assert "thanks_is_not_execution_proof" in planes["client_thanks_not_enough"]
    pipe = verification_pipeline()
    assert VerificationState.MESSAGE_RECEIVED.value in pipe
    assert VerificationState.OUTCOME.value in pipe
    collapsed = set(statuses_must_not_collapse())
    assert collapsed == {
        "error_fixed",
        "client_notified",
        "refund_done",
        "claim_closed",
    }


def test_json_s2026_jk() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows if str(r["id"]).startswith("S20.26")}
    assert "S20.26J" in by_id and "S20.26K" in by_id
    compound = by_id["S20.26J"]
    client = next(t for t in compound["turns"] if t["role"] == "client")
    split = split_deception_compound(client["text"])
    assert {e["kind"] for e in split["elements"]} == set(
        compound["compound_elements"]
    )
    for sid in ("S20.26J", "S20.26K"):
        for turn in by_id[sid]["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            for m in turn.get("must", []):
                assert m.casefold() in turn["text"].casefold()
            for ban in turn.get("must_not", []):
                assert ban.casefold() not in turn["text"].casefold()
