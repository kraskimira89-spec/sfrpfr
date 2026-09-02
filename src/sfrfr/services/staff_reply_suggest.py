"""Подсказки ответов сотруднику: DeepSeek в Yandex AI Studio."""

from __future__ import annotations

import re
from typing import Any

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.core.copy import POSITION_SHORT

# Канон вложений для подсказок сотруднику (чат MAX / кабинет на сайте).
DOCS_CHANNEL_CANON = (
    "Документы клиент может прислать прямо в этот чат MAX "
    "(переписка с ботом / чат с сотрудником) — примем, специалист увидит. "
    "Также можно воспользоваться личным кабинетом на сайте "
    "cabinet.proverkastaza.ru (загрузка документов, статус, оплата, согласие). "
    "Не пиши «загружайте только в личный кабинет» / «не присылайте в чат» "
    "и не предлагай mini-app как единственный способ. "
    "Если уместно просить файлы — сначала чат MAX, кабинет на сайте — как удобная альтернатива."
)

SYSTEM = f"""Ты помощник сотрудника сервиса «Проверка стажа».

{POSITION_SHORT}

Сгенерируй 3 коротких варианта ответа клиенту в MAX.
Формат строго:
1) ...
2) ...
3) ...
Каждый вариант — 1–2 предложения на русском.

Документы и кабинет (канон):
{DOCS_CHANNEL_CANON}
Если в ответе уместно просить или напоминать про файлы — явно скажи,
что их можно прислать в этот чат MAX; при желании упомяни и кабинет на сайте.

Обязательно:
- в КАЖДОМ варианте обратись к человеку по имени/отчеству из поля «Обращение»
  (например: «Здравствуйте, Иван Иванович!» или «Иван Иванович, …»);
- если обращение «Клиент» — начни с «Здравствуйте,» без выдуманного имени;
- без телефона, e-mail, СНИЛС, номера дела, без обещаний перерасчёта и сумм;
- не обещай, что сервис подаёт в СФР / Госуслуги вместо клиента.
"""


def client_salutation(full_name: str | None) -> str:
    """Имя + отчество для обращения; без фамилии, если есть полное ФИО."""
    parts = [p for p in re.split(r"\s+", (full_name or "").strip()) if p]
    if len(parts) >= 3:
        return f"{parts[1]} {parts[2]}"
    if len(parts) == 2:
        # Фамилия Имя → обращение по имени
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    return "Клиент"


def _ensure_salutation(text: str, salutation: str) -> str:
    """Если модель забыла имя — аккуратно добавить обращение в начало."""
    body = (text or "").strip()
    if not body:
        return body
    if salutation == "Клиент":
        if re.match(r"(?i)^здравствуйте\b", body):
            return body
        return f"Здравствуйте! {body}"
    # Уже есть имя или имя+отчество в тексте
    tokens = [t for t in re.split(r"\s+", salutation) if t]
    if tokens and all(re.search(rf"(?i)\b{re.escape(t)}\b", body) for t in tokens):
        return body
    if re.match(r"(?i)^здравствуйте\b", body):
        # «Здравствуйте! …» → «Здравствуйте, Иван Иванович! …»
        rest = re.sub(r"(?i)^здравствуйте\s*[,!]?\s*", "", body).strip()
        if rest:
            return f"Здравствуйте, {salutation}! {rest}"
        return f"Здравствуйте, {salutation}!"
    return f"{salutation}, {body[0].lower() + body[1:] if body else body}"


def _fallback_replies(salutation: str, *, pipeline_status: str | None) -> list[str]:
    """Шаблоны, если DeepSeek недоступен — лучше, чем пустой экран."""
    hello = f"Здравствуйте, {salutation}!" if salutation != "Клиент" else "Здравствуйте!"
    stage = pipeline_status or "intake"
    if stage in {"intake", "consent_pending", "docs_pending"}:
        action = "Пришлите, пожалуйста, выписку ИЛС (PDF) и сканы трудовой"
    else:
        action = "Напишите, если по делу остались вопросы — ответим в этом чате"
    return [
        (
            f"{hello} {action} — можно прямо в этот чат MAX или в личный кабинет на сайте. "
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами."
        )[:400],
        (
            f"{hello} Напоминаем: {action.lower()}. "
            "Файлы можно прислать сюда в MAX или загрузить в кабинет на сайте."
        )[:400],
        (
            f"{hello} Если удобнее через сайт: cabinet.proverkastaza.ru → раздел документов. "
            "Или пришлите файлы PDF/JPG сюда в чат."
        )[:400],
    ]


def suggest_staff_replies(
    *,
    messages: list[dict[str, Any]],
    pipeline_status: str | None = None,
    b2c_status: str | None = None,
    client_name: str | None = None,
) -> list[str]:
    salutation = client_salutation(client_name)
    llm = LLMClient.for_analyze(allow_fallback=False)
    if not llm.available:
        return _fallback_replies(salutation, pipeline_status=pipeline_status)

    lines: list[str] = []
    for row in messages[-12:]:
        kind = str(row.get("author_kind") or "unknown")
        body = redact_for_llm(str(row.get("body") or ""))[:400]
        if not body:
            continue
        lines.append(f"{kind}: {body}")
    if not lines:
        lines.append("(история пуста — предложи вежливое первое сообщение)")

    user = (
        f"Обращение к клиенту (обязательно в каждом варианте): {salutation}\n"
        f"Этап дела: pipeline={pipeline_status or '—'}, b2c={b2c_status or '—'}\n"
        f"Лента (без ПДн в тексте):\n" + "\n".join(lines)
    )
    try:
        raw = llm.chat(system=SYSTEM, user=user, temperature=0.4)
    except Exception:  # noqa: BLE001
        return _fallback_replies(salutation, pipeline_status=pipeline_status)

    out: list[str] = []
    for m in re.finditer(r"^\s*\d+[).]\s*(.+)$", raw or "", re.M):
        text = _ensure_salutation(m.group(1).strip().strip("«»\"'"), salutation)
        if text:
            out.append(text[:400])
        if len(out) >= 3:
            break
    if not out and (raw or "").strip():
        for line in (raw or "").splitlines():
            t = line.strip().lstrip("1234567890). ").strip()
            if len(t) > 12:
                out.append(_ensure_salutation(t, salutation)[:400])
            if len(out) >= 3:
                break
    return out or _fallback_replies(salutation, pipeline_status=pipeline_status)
