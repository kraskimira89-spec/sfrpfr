"""Агент: юридическое обоснование findings (после детерминированной сверки)."""

from __future__ import annotations

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.ai.prompts import REASON_SYSTEM
from sfrfr.ai.schemas.agents import Finding


def reason_findings(
    findings: list[Finding],
    *,
    client_name: str | None = None,
    llm: LLMClient | None = None,
) -> str:
    """
    DeepSeek-анализ уже найденных расхождений (код audit_ils).

    Не заменяет сверку ИЛС↔трудовая и не принимает сырые сканы.
    """
    if not findings:
        return ""

    findings_text = "\n".join(
        f"- [{f.type}|{f.severity}] {f.detail}" for f in findings
    )
    safe = redact_for_llm(findings_text, client_name=client_name)
    llm = llm or LLMClient.for_analyze()
    if not llm.available:
        return ""

    user = (
        "Ниже — результат детерминированной сверки (findings). "
        "Дай краткое юридическое обоснование и что проверить эксперту.\n\n"
        f"{safe}"
    )
    return llm.chat(system=REASON_SYSTEM, user=user, temperature=0.1)
