"""SFRFR-110 §20.21 / §31–34: агрессия и жалобы — содержание важнее тона."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfrfr.services.complaint_aggression_policy import (
    ComplaintVariant,
    classify_complaint_signal,
    complaint_case_record,
    extract_message_layers,
    harm_threat_response,
    is_complaint_threat_not_harm,
    may_accuse_client_of_lying,
    may_apply_harm_route_to_review_threat,
    may_claim_registration_without_success,
    may_close_claim_for_tone,
    may_discourage_complaint,
    may_invent_sla_deadline,
    may_offer_upsell_instead_of_claim,
    may_promise_refund_without_authority,
    may_say_resolved_when_only_task_created,
    may_trade_help_for_no_complaint,
    registration_reply,
    reply_has_banned_complaint_rhetoric,
    reply_has_forbidden_complaint_label,
    send_vs_delivery_status,
)

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "client_ai_complex_dialogues.json"


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        (
            "Сколько можно ждать? Вы только деньги брать умеете!",
            ComplaintVariant.DELAY_ANGER,
        ),
        (
            "Напишу на вас жалобу. И отзыв везде оставлю!",
            ComplaintVariant.THREATEN_REVIEW,
        ),
        (
            "Мне не нужен разговор с ботом. Зарегистрируйте претензию.",
            ComplaintVariant.FORMAL_CLAIM,
        ),
        (
            "Верните деньги прямо сейчас. Больше с вами работать не хочу.",
            ComplaintVariant.IMMEDIATE_REFUND,
        ),
        (
            "Вы мошенники! Ничего не проверяли!",
            ComplaintVariant.FRAUD_ACCUSATION,
        ),
        (
            "У вас все безграмотные. Делайте, что я сказал!",
            ComplaintVariant.INSULT,
        ),
        (
            "Я приеду и причиню вашему сотруднику вред.",
            ComplaintVariant.HARM_THREAT,
        ),
        (
            "Я уже писал в кабинете и в MAX. Никто не отвечает!",
            ComplaintVariant.MULTI_CHANNEL,
        ),
        (
            "Ваш бот сказал, что мне положена прибавка. "
            "Я оплатил, а теперь вы отказываетесь от слов!",
            ComplaintVariant.AI_ERROR_CLAIM,
        ),
        (
            "Вы вообще ничего мне не отправляли!",
            ComplaintVariant.WRONG_CLIENT_ASSERTION,
        ),
    ],
)
def test_classify_complaint_variants(
    text: str, variant: ComplaintVariant
) -> None:
    assert classify_complaint_signal(text) == variant


def test_layers_keep_content_and_tone() -> None:
    layers = extract_message_layers(
        "Вы вообще ничего не делаете! Деньги взяли, где мой отчёт? Верните оплату!"
    )
    assert "status" in layers["requirements"]
    assert "refund" in layers["requirements"]
    assert layers["reduce_to_insult_only"] is False
    assert layers["content_still_processed"] is True
    assert layers["tone"] in {"sharp", "insulting", "complaint_threat"}


def test_review_threat_is_not_harm_route() -> None:
    assert is_complaint_threat_not_harm("Подам в суд и оставлю отзыв")
    assert may_apply_harm_route_to_review_threat() is False
    assert classify_complaint_signal("Подам в суд!") == ComplaintVariant.THREATEN_REVIEW


def test_policy_guards() -> None:
    assert may_discourage_complaint() is False
    assert may_trade_help_for_no_complaint() is False
    assert may_promise_refund_without_authority() is False
    assert may_say_resolved_when_only_task_created() is False
    assert may_invent_sla_deadline() is False
    assert may_offer_upsell_instead_of_claim() is False
    assert may_close_claim_for_tone() is False
    assert may_accuse_client_of_lying() is False
    assert may_claim_registration_without_success() is False


def test_registration_and_case_record() -> None:
    ok = registration_reply(succeeded=True, ticket_id="CLM-1")
    assert ok["announce_accepted"] is True
    bad = registration_reply(succeeded=False)
    assert bad["announce_accepted"] is False
    assert bad["must_say_failed"] is True
    rec = complaint_case_record(
        channel="max",
        subject="refund",
        requirements=["refund"],
        client_position="хочу возврат",
        registered=False,
    )
    assert rec["ticket_id"] is None
    assert rec["task_created_is_not_resolution"] is True
    assert rec["client_label"] is None


def test_send_vs_delivery() -> None:
    st = send_vs_delivery_status(
        prepared=True, sent=True, delivered=False, opened=False
    )
    assert st["may_blame_client"] is False
    assert st["prove_received"] is False


def test_harm_threat_stub() -> None:
    resp = harm_threat_response()
    assert resp["claim_emergency_dispatched"] is False
    assert resp["keep_service_request"] is True
    assert "безопасности" in resp["template_core"]


def test_banned_rhetoric() -> None:
    assert reply_has_banned_complaint_rhetoric("Вопрос решён, задача создана")
    assert reply_has_forbidden_complaint_label("Вы неадекватный")
    assert not reply_has_banned_complaint_rhetoric(
        "Проверю статус заказа. Возврат пока не выполнен."
    )


def test_json_s2021_scenarios() -> None:
    rows = json.loads(_ASSETS.read_text(encoding="utf-8"))
    calc = [r for r in rows if str(r["id"]).startswith("S20.21")]
    assert {f"S20.21{x}" for x in "ABCDEFGHI"} | {"S20.21K"} <= {
        r["id"] for r in calc
    }
    for scenario in calc:
        client = next(t for t in scenario["turns"] if t["role"] == "client")
        got = classify_complaint_signal(client["text"])
        assert got is not None
        assert got.value == scenario["complaint"]
        for turn in scenario["turns"]:
            if turn["role"] != "assistant_ok":
                continue
            assert not reply_has_banned_complaint_rhetoric(turn["text"])
            assert not reply_has_forbidden_complaint_label(turn["text"])
