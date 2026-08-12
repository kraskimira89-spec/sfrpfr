"""ТЗ-27: AI-ответы специалистам в ops-боте / канале команды."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.ai.prompts import ASSISTANT_SYSTEM
from sfrfr.ai.rag.retriever import KnowledgeRetriever
from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)

OPS_BOT_DISPLAY_NAME = "Проверка стажа-Ops"

_ROOT = Path(__file__).resolve().parents[4]
_MENTION_RE = re.compile(
    r"@id8905998693_3_bot|проверка\s+стажа-?ops",
    re.IGNORECASE,
)
_ASK_RE = re.compile(r"^/ask(?:@\w+)?\s*", re.IGNORECASE)

_EXTRA_CONTEXT_FILES: tuple[Path, ...] = (
    _ROOT / "scripts" / "assets" / "copy" / "submission-position.md",
    _ROOT / "docs" / "ops" / "max-ops-bot-setup.md",
    _ROOT / "docs" / "specs" / "25-max-ops-bot.md",
)


OPS_SPECIALIST_SYSTEM = f"""{ASSISTANT_SYSTEM}

Дополнительно — ты отвечаешь **специалистам сервиса** в служебном чате MAX
(бот «{OPS_BOT_DISPLAY_NAME}»), не клиенту.

- Отвечай кратко и по делу (обычно 5–12 предложений или короткий список).
- Опирайся на блок «База знаний» в сообщении пользователя; не выдумывай процессы.
- Если вопрос про продукт/процессы команды — используй ops-справку.
- Если вопрос юридический/по стажу без документов — дай общую рамку и что проверить эксперту.
- Не проси выкладывать полные СНИЛС/паспорт в канал.
"""


def ops_llm_enabled() -> bool:
    return bool(get_settings().max_ops_llm_enabled)


def is_specialists_channel(chat_id: int | str | None) -> bool:
    configured = (get_settings().max_specialists_channel_chat_id or "").strip()
    if not configured or chat_id is None:
        return False
    return str(chat_id) == configured


def extract_ops_question(text: str, *, in_channel: bool) -> str | None:
    """Вернуть текст вопроса или None, если отвечать не нужно."""
    raw = (text or "").strip()
    if not raw:
        return None
    if in_channel:
        if _ASK_RE.match(raw):
            q = _ASK_RE.sub("", raw).strip()
            return q or None
        if _MENTION_RE.search(raw):
            q = _MENTION_RE.sub(" ", raw)
            q = re.sub(r"\s+", " ", q).strip(" \t\n\r,.:;")
            return q or None
        return None
    return raw


def _load_extra_context(*, limit_chars: int = 6000) -> str:
    chunks: list[str] = []
    used = 0
    for path in _EXTRA_CONTEXT_FILES:
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not body:
            continue
        piece = f"### {path.name}\n{body}"
        if used + len(piece) > limit_chars:
            remain = limit_chars - used
            if remain < 200:
                break
            piece = piece[:remain] + "…"
        chunks.append(piece)
        used += len(piece)
        if used >= limit_chars:
            break
    return "\n\n".join(chunks)


def _rag_block(question: str, *, limit: int = 5) -> str:
    hits = KnowledgeRetriever().search(question, limit=limit)
    if not hits:
        return (
            "(релевантных фрагментов knowledge/ не найдено — "
            "опирайся на ops-справку и общие правила.)"
        )
    lines = []
    for h in hits:
        lines.append(f"- [{h.source} | score={h.score:.2f}] {h.snippet}")
    return "\n".join(lines)


def answer_specialist_question(
    question: str,
    *,
    llm: LLMClient | None = None,
) -> str:
    """Сгенерировать ответ специалисту. Пустая строка — LLM недоступен."""
    settings = get_settings()
    max_chars = max(500, int(settings.max_ops_llm_max_chars or 3500))
    safe_q = redact_for_llm(question.strip())[:4000]
    if not safe_q:
        return "Уточните вопрос одной фразой (без персональных данных клиента)."

    llm = llm or LLMClient.for_analyze()
    if not llm.available:
        logger.warning("ops_llm: LLM unavailable")
        return (
            "ИИ сейчас недоступен (не настроен провайдер). "
            "Проверьте Yandex/DeepSeek ключи на сервере или спросите коллегу."
        )

    rag = _rag_block(safe_q)
    extra = _load_extra_context()
    user = (
        f"Вопрос специалиста:\n{safe_q}\n\n"
        f"База знаний (фрагменты):\n{rag}\n\n"
        f"Доп. контекст проекта:\n{extra or '(нет файлов)'}\n"
    )
    try:
        reply = llm.chat(system=OPS_SPECIALIST_SYSTEM, user=user, temperature=0.2)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ops_llm chat failed: %s", exc)
        return "Не удалось получить ответ ИИ. Попробуйте позже или спросите коллегу."

    reply = (reply or "").strip()
    if not reply:
        return "Пустой ответ модели. Переформулируйте вопрос или проверьте LLM."
    if len(reply) > max_chars:
        reply = reply[: max_chars - 1].rstrip() + "…"
    return reply
