"""Агент: черновик заявления в СФР."""

from __future__ import annotations

from sfrfr.ai.guardrails import ensure_needs_human_review, redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.ai.prompts import ASSISTANT_SYSTEM, DRAFT_SYSTEM
from sfrfr.ai.rag.retriever import KnowledgeRetriever
from sfrfr.ai.schemas.agents import DraftResult, Finding


def draft_application(
    findings: list[Finding],
    *,
    client_name: str | None = None,
    llm: LLMClient | None = None,
    retriever: KnowledgeRetriever | None = None,
    use_assistant_prompt: bool = False,
) -> DraftResult:
    """Черновик по findings + RAG (только verified/template). Всегда needs_human_review=True."""
    findings_text = "\n".join(f"- [{f.type}] {f.detail}" for f in findings) or "- (нет findings)"
    safe_findings = redact_for_llm(findings_text, client_name=client_name)

    retriever = retriever or KnowledgeRetriever()
    hits = retriever.search(safe_findings or "заявление перерасчёт стаж ИЛС")
    knowledge_block = "\n".join(f"[{h.source}] {h.snippet}" for h in hits)

    system = ASSISTANT_SYSTEM if use_assistant_prompt else DRAFT_SYSTEM
    llm = llm or LLMClient()
    if llm.available:
        user = (
            f"Findings:\n{safe_findings}\n\n"
            f"Проверенная база знаний (RAG):\n{knowledge_block or '(пусто)'}"
        )
        body = llm.chat(system=system, user=user, temperature=0.2)
        if body:
            return ensure_needs_human_review(
                DraftResult(
                    title="Черновик заявления в СФР",
                    body=body,
                    findings_used=[f.type for f in findings],
                    needs_human_review=True,
                )
            )

    body_lines = [
        "Черновик заявления (заглушка без LLM).",
        "",
        "Прошу учесть следующие расхождения:",
        safe_findings,
        "",
        "Требуется проверка юристом перед отправкой.",
        "Клиент подаёт документы в СФР самостоятельно.",
    ]
    if knowledge_block:
        body_lines.extend(["", "Справка из базы знаний:", knowledge_block])

    return ensure_needs_human_review(
        DraftResult(
            title="Черновик заявления в СФР",
            body="\n".join(body_lines),
            findings_used=[f.type for f in findings],
            needs_human_review=True,
        )
    )
