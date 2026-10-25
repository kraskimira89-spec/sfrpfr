"""Резюме проверки → ответ клиенту: DeepSeek дорабатывает черновик под переписку.

ИИ только переформулирует: отвечает на вопрос клиента, убирает повторы.
Новые факты, суммы, годы, обещания и текст бота (/help, «кнопкой») не пропускаем —
тогда возвращаем очищенный шаблон.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from sfrfr.services.case_chat_context import format_thread_for_llm
from sfrfr.services.staff_reply_suggest import client_salutation


class _LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


_POSITION_RE = re.compile(
    r"решение\s+(?:об?\s+[^.]*?)?принимает\s+сфр|пода[её]те\s+[^.]*?\s+сами", re.I
)
_BOT_RE = re.compile(r"/help|кнопк", re.I)
_PROMISE_RE = re.compile(
    r"гарантир|добь[её]мся|верн[её]м\s+недоплат|пересчитаем|перерассчитаем"
    r"|повысим|прибавк|оплата\s+за\s+результат",
    re.I,
)
_MONEY_RE = re.compile(r"(\d[\d \u00a0]*)\s*(?:₽|руб)", re.I)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_STAFF_KINDS = {"staff", "system", "bot"}

SYSTEM = """Ты редактор ответов сотрудника сервиса «Проверка стажа» клиенту в чате MAX.
Тебе дают ЧЕРНОВИК (факты проверки документов) и последние сообщения переписки.
Перепиши черновик в живой ответ этому клиенту:
- если клиент задал вопрос — сначала коротко ответь на него, опираясь только на факты черновика;
- обратись по имени и отчеству из поля «Обращение», только если сотрудник сегодня ещё
  не писал; иначе без повторного «Здравствуйте»;
- убери повторы слов и мыслей, канцелярит и служебные слова («анкета»,
  «формулировка клиента»);
- сохрани смысл: что уже известно, чего не хватает, что нужно от клиента;
- 3–6 предложений, без списков, заголовков и эмодзи.
Запрещено:
- добавлять факты, периоды, годы, суммы и цены, которых нет в черновике;
- обещать перерасчёт, повышение пенсии, результат или сроки;
- писать про кнопки, команды (/help) и личный кабинет на сайте;
- утверждать, что сервис подаёт обращение вместо клиента;
- добавлять фразу о том, кто подаёт обращение и кто принимает решение, если её нет
  в черновике.
Верни только текст сообщения."""


def _norm(sentence: str) -> str:
    s = sentence.lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def dedupe_sentences(text: str) -> str:
    """Убрать повторённые предложения и сдвоенные метки («Следующий шаг: Следующий шаг:»)."""
    t = re.sub(r"(следующий шаг:\s*){2,}", "Следующий шаг: ", text or "", flags=re.I)
    seen: list[str] = []
    paragraphs: list[str] = []
    for para in re.split(r"\n\s*\n", t):
        kept: list[str] = []
        for sentence in _SENT_SPLIT.split(para.strip()):
            s = sentence.strip()
            key = _norm(s)
            if not key:
                continue
            if key in seen or (len(key) >= 10 and any(key in prev for prev in seen)):
                continue
            seen.append(key)
            kept.append(s)
        if kept:
            paragraphs.append(" ".join(kept))
    return "\n\n".join(paragraphs).strip()


def strip_position(text: str) -> str:
    """Убрать предложения «кто подаёт / кто решает» — если это уже говорили."""
    paragraphs: list[str] = []
    for para in re.split(r"\n\s*\n", text or ""):
        kept = [
            s.strip()
            for s in _SENT_SPLIT.split(para.strip())
            if s.strip() and not _POSITION_RE.search(s)
        ]
        if kept:
            paragraphs.append(" ".join(kept))
    return "\n\n".join(paragraphs).strip()


def position_said_recently(messages: list[dict[str, Any]], *, window: int = 10) -> bool:
    """Позицию про подачу и решение СФР уже писали в последних сообщениях сервиса."""
    ours = [m for m in messages if str(m.get("author_kind") or "") in _STAFF_KINDS]
    return any(_POSITION_RE.search(str(m.get("body") or "")) for m in ours[-window:])


def _amounts(text: str) -> set[str]:
    return {re.sub(r"\D", "", m.group(1)) for m in _MONEY_RE.finditer(text or "")}


def _validate(text: str, *, draft: str, messages: list[dict[str, Any]]) -> str | None:
    if len(text) < 40:
        return "too_short"
    if len(text) > 1500:
        return "too_long"
    if "[" in text:
        return "placeholder"
    if _BOT_RE.search(text):
        return "bot_text"
    if _PROMISE_RE.search(text):
        return "promise"
    if not _amounts(text) <= _amounts(draft):
        return "new_amount"
    client_text = " ".join(
        str(m.get("body") or "") for m in messages if m.get("author_kind") == "client"
    )
    allowed_years = set(_YEAR_RE.findall(draft)) | set(_YEAR_RE.findall(client_text))
    if not set(_YEAR_RE.findall(text)) <= allowed_years:
        return "new_year"
    return None


def _clean_llm_text(raw: str) -> str:
    t = (raw or "").strip().strip("`").strip()
    t = re.sub(r"^(ответ|сообщение)\s*:\s*", "", t, flags=re.I)
    return t.strip().strip("«»\"").strip()


def _user_prompt(*, draft: str, messages: list[dict[str, Any]], client_name: str | None) -> str:
    recent = messages[-12:]
    client_lines = [
        str(m.get("body") or "").strip()
        for m in recent
        if m.get("author_kind") == "client" and str(m.get("body") or "").strip()
    ][-3:]
    staff_wrote = any(str(m.get("author_kind") or "") == "staff" for m in recent[-6:])
    asked = "\n".join(f"- {line[:400]}" for line in client_lines) or "- (вопросов нет)"
    return (
        f"Обращение: {client_salutation(client_name)}\n"
        f"Сотрудник уже писал в последних сообщениях: {'да' if staff_wrote else 'нет'}\n\n"
        f"Последние сообщения клиента:\n{asked}\n\n"
        f"История переписки:\n{format_thread_for_llm(recent, max_body_chars=400)}\n\n"
        f"ЧЕРНОВИК:\n{draft}"
    )


def polish_brief_reply(
    *,
    draft: str,
    messages: list[dict[str, Any]],
    client_name: str | None,
    llm: _LLM | None | Literal["auto"] = "auto",
) -> dict[str, Any]:
    """Черновик резюме → ответ клиенту. source=ai | template (+ reason при откате)."""
    said = position_said_recently(messages)
    base = dedupe_sentences(draft)
    if said:
        base = strip_position(base)

    def template(reason: str) -> dict[str, Any]:
        return {"text": base, "source": "template", "reason": reason}

    client: _LLM | None
    if llm == "auto":
        from sfrfr.ai.llm import LLMClient

        client = LLMClient.for_analyze(allow_fallback=False)
    else:
        client = llm
    if client is None or not client.available:
        return template("llm_unavailable")
    try:
        raw = client.chat(
            system=SYSTEM,
            user=_user_prompt(draft=base, messages=messages, client_name=client_name),
            temperature=0.3,
        )
    except Exception:  # noqa: BLE001
        return template("llm_error")
    text = dedupe_sentences(_clean_llm_text(raw))
    if said:
        text = strip_position(text)
    problem = _validate(text, draft=base, messages=messages)
    if problem:
        return template(problem)
    return {"text": text, "source": "ai"}
