"""Тесты базы знаний, обезличивания и RAG-фильтра."""

from __future__ import annotations

from pathlib import Path

import pytest

from sfrfr.ai.knowledge import KnowledgeCaseRegistry, import_dialog_to_case
from sfrfr.ai.pii.depersonalize import depersonalize_text
from sfrfr.ai.rag.retriever import KnowledgeRetriever
from sfrfr.ai.schemas.knowledge_case import KnowledgeQuality


def test_depersonalize_masks_pii() -> None:
    text = (
        "Иванов Иван Иванович, СНИЛС 123-456-789 01, паспорт 4510 123456, "
        "тел +7 (900) 111-22-33, email a@b.ru, дата 01.02.1960, "
        "https://lk.example.ru/file/1"
    )
    out = depersonalize_text(text)
    assert "123-456-789 01" not in out
    assert "***-***-789 01" in out
    assert "[ПАСПОРТ]" in out
    assert "[ТЕЛЕФОН]" in out
    assert "[EMAIL]" in out
    assert "[ДАТА]" in out
    assert "[ССЫЛКА]" in out
    assert "Иванов Иван Иванович" not in out
    assert "[ФАМИЛИЯ]" in depersonalize_text("Документы Лопаковой Н.Ф. и ЛОПАКОВА")


def test_import_creates_draft(tmp_path: Path) -> None:
    dialog = tmp_path / "pilot.md"
    dialog.write_text(
        "Клиент: расхождение стажа в ИЛС и трудовой книжке.\n"
        "Подготовлено заявление. Результат СФР: удовлетворено.\n"
        "СНИЛС 111-222-333 44 не сохранять.\n",
        encoding="utf-8",
    )
    registry = KnowledgeCaseRegistry(tmp_path / "cases")
    case = import_dialog_to_case(dialog, registry=registry)
    assert case.quality == KnowledgeQuality.DRAFT
    assert case.case_id.startswith("CASE-")
    assert "111-222-333 44" not in case.summary
    assert "ИЛС" in case.documents or "трудовая книжка" in case.documents


def test_rag_skips_draft(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    cases_dir = knowledge / "cases"
    cases_dir.mkdir(parents=True)
    (knowledge / "sfr_norms.md").write_text("перерасчёт стаж ИЛС\n", encoding="utf-8")

    registry = KnowledgeCaseRegistry(cases_dir)
    draft_path = tmp_path / "d.md"
    draft_path.write_text("черновик про стаж и ИЛС\n", encoding="utf-8")
    verified = import_dialog_to_case(draft_path, registry=registry)
    registry.set_quality(verified.case_id, KnowledgeQuality.VERIFIED)

    other = tmp_path / "other.md"
    other.write_text("другой draft про стаж\n", encoding="utf-8")
    draft = import_dialog_to_case(other, registry=registry)
    assert draft.quality == KnowledgeQuality.DRAFT

    retriever = KnowledgeRetriever(knowledge_dir=knowledge, registry=registry)
    hits = retriever.search("стаж ИЛС перерасчёт", limit=10)
    sources = [h.source for h in hits]
    assert any(verified.case_id in s for s in sources)
    assert not any(draft.case_id in s for s in sources)

    rag_cases = registry.list_cases(rag_ready_only=True)
    assert len(rag_cases) == 1
    assert rag_cases[0].case_id == verified.case_id


def test_rag_skips_rejected(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    cases_dir = knowledge / "cases"
    cases_dir.mkdir(parents=True)
    registry = KnowledgeCaseRegistry(cases_dir)
    path = tmp_path / "r.md"
    path.write_text("отклонённый кейс про стаж ИЛС\n", encoding="utf-8")
    case = import_dialog_to_case(path, registry=registry)
    registry.set_quality(case.case_id, KnowledgeQuality.REJECTED)
    template_path = tmp_path / "t.md"
    template_path.write_text("шаблон про стаж ИЛС перерасчёт\n", encoding="utf-8")
    tmpl = import_dialog_to_case(template_path, registry=registry)
    registry.set_quality(tmpl.case_id, KnowledgeQuality.TEMPLATE)

    retriever = KnowledgeRetriever(knowledge_dir=knowledge, registry=registry)
    sources = [h.source for h in retriever.search("стаж ИЛС", limit=10)]
    assert any(tmpl.case_id in s for s in sources)
    assert not any(case.case_id in s for s in sources)


def test_expert_feedback_updates_rag_registry(tmp_path: Path) -> None:
    from sfrfr.ai.knowledge.feedback import apply_expert_feedback

    registry = KnowledgeCaseRegistry(tmp_path / "cases")
    kb = apply_expert_feedback(
        ops_case_id="11111111-2222-3333-4444-555555555555",
        quality="template",
        what_worked="Сверка ИЛС с трудовой; запрос в архив",
        documents_note="ИЛС\nТрудовая книжка",
        sfr_outcome="удовлетворено",
        registry=registry,
    )
    assert kb.case_id.startswith("CASE-")
    assert kb.quality == KnowledgeQuality.TEMPLATE
    assert kb.is_rag_ready()
    assert kb.ops_case_id.startswith("11111111")
    assert (tmp_path / "cases" / f"{kb.case_id}.md").exists()

    again = apply_expert_feedback(
        ops_case_id="11111111-2222-3333-4444-555555555555",
        quality="rejected",
        what_worked="ошибка подхода",
        registry=registry,
    )
    assert again.case_id == kb.case_id
    assert again.quality == KnowledgeQuality.REJECTED
    assert not again.is_rag_ready()
    assert registry.list_cases(rag_ready_only=True) == []


def test_assistant_system_prompt_rules() -> None:
    from sfrfr.ai.prompts import ASSISTANT_SYSTEM

    low = ASSISTANT_SYSTEM.lower()
    assert "не обещай" in low or "не обеща" in low
    assert "сфр" in low
    assert "пдн" in low or "снилс" in low
    assert "самостоятельно" in low


def test_draft_always_needs_human_review() -> None:
    from sfrfr.ai.agents.drafter import draft_application
    from sfrfr.ai.guardrails import ensure_needs_human_review
    from sfrfr.ai.schemas.agents import DraftResult, Finding

    draft = draft_application([Finding(type="stazh", detail="разрыв в ИЛС")])
    assert draft.needs_human_review is True
    forced = ensure_needs_human_review(
        DraftResult(title="t", body="b", needs_human_review=False)
    )
    assert forced.needs_human_review is True


def test_depersonalize_dir(tmp_path: Path) -> None:
    from sfrfr.ai.knowledge import depersonalize_dir

    inbox = tmp_path / "inbox"
    nested = inbox / "sub"
    nested.mkdir(parents=True)
    (inbox / "a.md").write_text(
        "Иванов Иван Иванович СНИЛС 123-456-789 01\n",
        encoding="utf-8",
    )
    (nested / "b.txt").write_text("тел +7 (900) 111-22-33\n", encoding="utf-8")
    (inbox / "scan.pdf").write_bytes(b"%PDF-fake")

    out = tmp_path / "cleaned"
    results = depersonalize_dir(inbox, out)
    by_status = {r.source.name: r for r in results}
    assert by_status["a.md"].status == "ok"
    assert by_status["b.txt"].status == "ok"
    assert by_status["scan.pdf"].status == "skipped"
    cleaned_a = (out / "a.md").read_text(encoding="utf-8")
    assert "123-456-789 01" not in cleaned_a
    assert "***-***-789 01" in cleaned_a
    cleaned_b = (out / "sub" / "b.txt").read_text(encoding="utf-8")
    assert "[ТЕЛЕФОН]" in cleaned_b


def test_set_quality_unknown_raises(tmp_path: Path) -> None:
    registry = KnowledgeCaseRegistry(tmp_path / "cases")
    with pytest.raises(KeyError):
        registry.set_quality("CASE-2099-999", KnowledgeQuality.VERIFIED)
