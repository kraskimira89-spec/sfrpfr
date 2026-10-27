"""Черновик подробного разбора (этап 5) — готовит ИИ, проверяет специалист.

Без обещаний перерасчёта / суммы. Подача через СФР/Госуслуги — клиент сам.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from sfrfr.ai.guardrails import redact_for_llm

logger = logging.getLogger(__name__)

_POSITION = (
    "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
    "Решение принимает СФР."
)
_DISCLAIMER = (
    "Это информационно-аналитический разбор по загруженным документам, "
    "а не юридическое заключение и не решение СФР. Специалист проверяет текст "
    "перед выдачей клиенту."
)
_PROMISE_RE = re.compile(
    r"гарантир|добь[её]мся|верн[её]м\s+недоплат|пересчитаем|перерассчитаем"
    r"|повысим|прибавк|оплата\s+за\s+результат|\d[\d\s]{2,}\s*₽\s*в\s*месяц",
    re.I,
)
_BOT_RE = re.compile(r"/help|кнопк", re.I)

SYSTEM = """Ты помощник сотрудника сервиса проверки стажа (СФР / ИЛС / трудовая).
Пишешь ПОДРОБНЫЙ письменный разбор для клиента на русском.

Правила:
- опирайся только на факты из входных данных (документы, пункты сверки);
- не выдумывай периоды, работодателей, суммы и гарантии выплат;
- не пиши, что сервис подаёт заявление или действует от имени СФР;
- не используй /help и «ответьте кнопкой»;
- структура Markdown:
  1) Заголовок и дата
  2) Какие документы изучены
  3) Краткий итог
  4) Список расхождений: период → источник А → источник Б → что сделать
  5) Чего не хватает
  6) План обращений (таблица): № · адресат · тема · включённые проблемы ·
     что просим · приложения · порядок подачи. Правило сервиса: одно обращение —
     один конкретный адресат и одна группа однородных вопросов; разнородные
     проблемы не сваливать в одно; одного совпадения ведомства мало. Кратко
     «почему объединено / почему разделено». Проблемы без адресата —
     «Нужно уточнить», без выдуманного получателя.
  7) Рекомендуемые шаги клиента
  8) Короткая оговорка: информационно-аналитический характер; решение принимает СФР
- в конце: «Мы готовим документы и план — подаёте через СФР или Госуслуги
  вы сами. Решение принимает СФР.»
- тон спокойный, без канцелярита и без давления оплатить ещё раз.
"""


class _LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _doc_lines(documents: list[dict[str, Any]] | None) -> list[str]:
    lines: list[str] = []
    for d in documents or []:
        if not isinstance(d, dict):
            continue
        name = _clean(d.get("filename") or d.get("storage_path") or "файл")
        if "/" in name:
            name = name.rsplit("/", 1)[-1]
        dtype = _clean(d.get("doc_type") or "документ")
        lines.append(f"- {dtype}: {name}")
    return lines[:20]


def _brief_items(brief: dict[str, Any] | None) -> list[dict[str, str]]:
    items = (brief or {}).get("items") if isinstance(brief, dict) else None
    out: list[dict[str, str]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        text = _clean(it.get("text"))
        if not text:
            continue
        out.append(
            {
                "text": text,
                "evidence": _clean(it.get("evidence") or it.get("evidence_label")),
                "basis": _clean(it.get("basis")),
            }
        )
    return out[:12]


def build_template_draft(
    *,
    case_ref: str,
    documents: list[dict[str, Any]] | None,
    brief: dict[str, Any] | None,
    compare: dict[str, Any] | None = None,
) -> str:
    """Детерминированный черновик без LLM — запасной вариант."""
    today = datetime.now(UTC).strftime("%d.%m.%Y")
    docs = _doc_lines(documents)
    items = _brief_items(brief)
    lines = [
        f"# Подробный разбор по делу {case_ref or '—'}",
        f"Дата подготовки: {today}",
        "",
        "## Какие документы изучены",
    ]
    lines.extend(docs or ["- Список документов пока пуст — уточните комплект."])
    lines.extend(["", "## Краткий итог"])
    if items:
        disc = [i for i in items if (i.get("evidence") or "").lower() in {"docs", "документы"}]
        if disc:
            lines.append(
                f"По сверке отмечено направлений, требующих внимания: {len(disc)}. "
                "Ниже — по пунктам, без гарантий выплат."
            )
        else:
            lines.append(
                "Автоматическая сверка не выделила жёстких расхождений по документам; "
                "ниже — темы для ручной проверки специалистом."
            )
    else:
        lines.append("Пунктов сверки пока нет — нужен повторный запуск проверки документов.")

    if isinstance(compare, dict) and compare.get("ran"):
        n = compare.get("discrepancies")
        summary = _clean(compare.get("summary"))
        lines.extend(["", "## Автосверка трудовой и ИЛС"])
        if summary:
            lines.append(summary)
        elif n is not None:
            lines.append(f"Найдено расхождений автосверки: {n}.")

    lines.extend(["", "## Расхождения и основания"])
    if items:
        for idx, it in enumerate(items, start=1):
            lines.append(f"{idx}. {it['text']}")
            if it.get("basis"):
                lines.append(f"   Основание: {it['basis']}")
            if it.get("evidence"):
                lines.append(f"   Источник сигнала: {it['evidence']}")
            lines.append("")
    else:
        lines.append("1. (нет пунктов — повторите проверку документов)")

    lines.extend(
        [
            "## Чего может не хватать",
            "- Страницы трудовой / вкладыши, если периоды оборваны;",
            "- Архивные справки по спорным годам;",
            "- Актуальная выписка ИЛС (PDF с Госуслуг).",
            "",
            "## Рекомендуемые шаги",
            "1. Сверить пункты выше с оригиналами документов.",
            "2. При необходимости запросить недостающие справки у работодателя или в архиве.",
            "3. При согласии на подготовку обращений — перейти к следующему этапу услуги.",
            "",
            "## Оговорка",
            _DISCLAIMER,
            "",
            _POSITION,
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _validate(text: str) -> str | None:
    body = (text or "").strip()
    if _PROMISE_RE.search(body):
        return "promise"
    if _BOT_RE.search(body):
        return "bot_ui"
    if len(body) < 120:
        return "too_short"
    return None


def generate_full_analysis_draft(
    *,
    case_ref: str,
    documents: list[dict[str, Any]] | None,
    brief: dict[str, Any] | None,
    compare: dict[str, Any] | None = None,
    ocr_snippets: list[str] | None = None,
    llm: _LLM | None | Literal["auto"] = "auto",
) -> dict[str, Any]:
    """Вернуть {text, source: ai|template, reason?}."""
    template = build_template_draft(
        case_ref=case_ref,
        documents=documents,
        brief=brief,
        compare=compare,
    )

    client: _LLM | None
    if llm == "auto":
        from sfrfr.ai.llm import LLMClient

        client = LLMClient.for_analyze(allow_fallback=True, foreign_ok=True)
    else:
        client = llm

    if client is None or not client.available:
        return {
            "text": template,
            "source": "template",
            "reason": "llm_unavailable",
            "llm_provider": None,
            "llm_fallback": False,
        }

    items = _brief_items(brief)
    docs = _doc_lines(documents)
    compare_line = ""
    if isinstance(compare, dict) and compare.get("ran"):
        compare_line = (
            _clean(compare.get("summary"))
            or f"discrepancies={compare.get('discrepancies')}"
        )
    snippets = [
        redact_for_llm(_clean(s)[:500]) for s in (ocr_snippets or []) if _clean(s)
    ][:6]

    user = (
        f"Номер/код дела (без ПДн): {redact_for_llm(case_ref)}\n\n"
        f"Документы:\n" + ("\n".join(docs) or "—") + "\n\n"
        "Пункты краткой сверки:\n"
        + (
            "\n".join(
                f"- {it['text']}"
                + (f" | {it['basis']}" if it.get("basis") else "")
                + (f" | evidence={it['evidence']}" if it.get("evidence") else "")
                for it in items
            )
            or "—"
        )
        + "\n\n"
        f"Автосверка: {compare_line or 'нет'}\n\n"
        f"Фрагменты текста документов (уже обезличены):\n"
        + ("\n---\n".join(snippets) if snippets else "—")
        + "\n\n"
        "Напиши подробный разбор по правилам system."
    )
    try:
        raw = client.chat(system=SYSTEM, user=user, temperature=0.3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("full_analysis_draft llm_error %s", type(exc).__name__)
        return {
            "text": template,
            "source": "template",
            "reason": "llm_error",
            "llm_provider": None,
            "llm_fallback": False,
        }

    provider_used = getattr(client, "last_provider_used", None)
    used_fallback = bool(getattr(client, "last_used_fallback", False))
    text = re.sub(r"\n{3,}", "\n\n", str(raw or "").strip())
    problem = _validate(text)
    if problem:
        return {
            "text": template,
            "source": "template",
            "reason": problem,
            "llm_provider": provider_used,
            "llm_fallback": used_fallback,
        }
    lower = text.lower()
    has_position = "решение принимает сфр" in lower or "подаёте через сфр" in lower
    if not has_position:
        text = f"{text.rstrip()}\n\n{_POSITION}"
    return {
        "text": text,
        "source": "ai",
        "llm_provider": provider_used or getattr(client, "provider", None),
        "llm_fallback": used_fallback,
    }
