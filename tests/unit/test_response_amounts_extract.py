"""Извлечение сумм пенсии из текста ответа СФР (ступень 11)."""

from __future__ import annotations

from sfrfr.services.response_amounts_extract import (
    parse_amounts_payload,
    extract_amounts_from_texts,
)


def test_parse_amounts_json_block() -> None:
    raw = """
Вот результат:
```json
{
  "monthly_before_rub": 18500.50,
  "monthly_after_rub": 21200,
  "lump_sum_rub": 45000,
  "chronology": [
    {"date": "2026-09-01", "filename": "otvet.pdf", "note": "как было 18500,50"}
  ],
  "source_quote": "размер пенсии установлен в сумме 21200 руб."
}
```
"""
    out = parse_amounts_payload(raw)
    assert out["monthly_before_rub"] == 18500.5
    assert out["monthly_after_rub"] == 21200.0
    assert out["lump_sum_rub"] == 45000.0
    assert len(out["chronology"]) == 1
    assert out["chronology"][0]["filename"] == "otvet.pdf"
    assert "21200" in (out.get("source_quote") or "")


def test_parse_missing_amounts_null() -> None:
    out = parse_amounts_payload(
        '{"monthly_before_rub": null, "monthly_after_rub": null, '
        '"lump_sum_rub": null, "chronology": [], "source_quote": null}'
    )
    assert out["monthly_before_rub"] is None
    assert out["monthly_after_rub"] is None
    assert out["lump_sum_rub"] is None
    assert out["chronology"] == []


def test_incomplete_text_no_hallucination() -> None:
    out = extract_amounts_from_texts(
        case_ref="CASE",
        snippets=[],
        llm=None,
    )
    assert out["source"] == "template"
    assert out["monthly_before_rub"] is None
    assert out["chronology"] == []


def test_llm_json_returned() -> None:
    class Fake:
        available = True
        provider = "fake"

        def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            return (
                '{"monthly_before_rub": 10000, "monthly_after_rub": 12000, '
                '"lump_sum_rub": 0, "chronology": [{"date": "2026-01-15", '
                '"filename": "a.pdf", "note": "увеличение"}], '
                '"source_quote": "стр. 2"}'
            )

    out = extract_amounts_from_texts(
        case_ref="CASE",
        snippets=[{"filename": "a.pdf", "text": "пенсия 12000 руб"}],
        llm=Fake(),
    )
    assert out["source"] == "ai"
    assert out["monthly_before_rub"] == 10000.0
    assert out["monthly_after_rub"] == 12000.0
    assert out["chronology"][0]["filename"] == "a.pdf"
