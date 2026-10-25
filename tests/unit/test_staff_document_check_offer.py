from sfrfr.services.staff_document_check_result import attach_honest_brief


def _brief(*evidence: str) -> dict:
    return {
        "offer_diag_allowed": True,
        "offer_amount_rub": 3000,
        "has_justified_discrepancy": True,
        "next_step": "Следующий шаг: ответьте кнопкой ниже (или /help).",
        "items": [{"text": f"пункт {e}", "evidence": e, "basis": ""} for e in evidence],
    }


def test_offer_blocked_when_only_questionnaire_themes() -> None:
    out = attach_honest_brief({}, brief=_brief("needs_check", "client"))
    assert out["diag_offer"]["allowed"] is False
    assert "/help" not in out["diag_offer"]["note"]
    assert "кнопк" not in out["diag_offer"]["note"]


def test_offer_allowed_with_document_evidence() -> None:
    out = attach_honest_brief({}, brief=_brief("docs", "client"))
    assert out["diag_offer"]["allowed"] is True
    assert out["diag_offer"]["amount_rub"] == 3000


def test_offer_blocked_when_brief_disallows() -> None:
    brief = _brief("docs")
    brief["offer_diag_allowed"] = False
    out = attach_honest_brief({}, brief=brief)
    assert out["diag_offer"]["allowed"] is False
