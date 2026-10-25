from sfrfr.services.stazh_compare_case import merge_compare_into_brief, run_case_stazh_compare

_DISC = {
    "kind": "north_partial",
    "title": "Северный стаж учтён не за весь период работы 01.02.1989–04.10.1999",
    "detail": "В выписке ИЛС северная отметка есть только за 01.01.1998–04.10.1999.",
}


def test_merge_puts_document_discrepancies_first() -> None:
    brief = {
        "has_justified_discrepancy": True,
        "offer_diag_allowed": False,
        "items": [{"text": "по северному стажу", "evidence": "needs_check", "basis": "анкета"}],
    }
    compare = {"ran": True, "discrepancies": [_DISC], "summary": "найдено расхождений: 1."}
    out = merge_compare_into_brief(brief, compare)
    assert out is not None
    assert out["items"][0]["evidence"] == "docs"
    assert out["items"][0]["text"] == _DISC["title"]
    assert out["items"][0]["basis"] == _DISC["detail"]
    assert out["items"][1]["evidence"] == "needs_check"
    assert out["offer_diag_allowed"] is True
    assert out["compare"] == {"ran": True, "discrepancies": 1, "summary": "найдено расхождений: 1."}


def test_merge_clean_compare_keeps_items_and_marks_result() -> None:
    brief = {"items": [{"text": "по северному стажу", "evidence": "needs_check"}]}
    compare = {"ran": True, "discrepancies": [], "summary": "расхождений не найдено."}
    out = merge_compare_into_brief(brief, compare)
    assert out is not None
    assert [i["evidence"] for i in out["items"]] == ["needs_check"]
    assert out["compare"]["discrepancies"] == 0
    assert out["headline"] == "расхождений не найдено."


def test_merge_ignores_not_ran() -> None:
    brief = {"items": []}
    assert merge_compare_into_brief(brief, {"ran": False, "reason": "нет строк"}) is brief
    assert merge_compare_into_brief(brief, None) is brief


def test_run_picks_ils_and_paper_workbook_by_type() -> None:
    analyzed = [
        {"id": "a", "guessed_type": "ils", "checksum_sha256": "1"},
        {"id": "a2", "guessed_type": "ils", "checksum_sha256": "1"},
        {"id": "b", "guessed_type": "workbook", "checksum_sha256": "2"},
        {"id": "c", "guessed_type": "other", "checksum_sha256": "3"},
    ]
    docs = [{"id": x["id"]} for x in analyzed]
    loaded: list[str] = []
    texts = {
        "a": "01.02.1989 - 04.10.1999 10 лет 8 мес. 4 дн. ШКОЛА",
        "b": "1 01.02.1989 Школа Принята учителем 2 04.10.1999 Школа Уволена",
    }

    def load(doc: dict) -> str:
        loaded.append(doc["id"])
        return texts.get(doc["id"], "")

    out = run_case_stazh_compare(docs, analyzed, load_text=load)
    assert out is not None and out["ran"] is True
    assert out["discrepancies"] == []
    assert sorted(loaded) == ["a", "b"]


def test_run_returns_none_without_core_documents() -> None:
    analyzed = [{"id": "c", "guessed_type": "other"}]
    assert run_case_stazh_compare([{"id": "c"}], analyzed, load_text=lambda _d: "") is None
