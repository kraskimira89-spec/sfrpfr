"""Импорт официального экспорта DeepSeek (conversations.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from sfrfr.ai.knowledge.importer import import_dialog_to_case
from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry
from sfrfr.ai.pii.depersonalize import depersonalize_text
from sfrfr.ai.schemas.knowledge_case import KnowledgeCase

# Заголовки/тексты про СФР, пенсию, стаж (не продукт Zerocoder).
_DEFAULT_TITLE_RE = re.compile(
    r"СФР|ПФР|пенси|стаж|ИЛС|перерасч|ЕДВ",
    re.IGNORECASE,
)
_SKIP_TITLE_RE = re.compile(r"Zerocoder|ZeroCoder|автоматизация пенсионных дел", re.I)


def extract_conversation_markdown(conv: dict) -> str:
    """Собирает диалог из mapping[].message.fragments в Markdown."""
    title = (conv.get("title") or "без названия").strip()
    lines = [f"# {title}", ""]
    nodes = list((conv.get("mapping") or {}).values())
    # сортировка по inserted_at, если есть
    def _ts(node: dict) -> str:
        msg = node.get("message") or {}
        return str(msg.get("inserted_at") or "")

    nodes.sort(key=_ts)
    for node in nodes:
        msg = node.get("message") or {}
        frags = msg.get("fragments") or []
        if not frags:
            continue
        for frag in frags:
            if not isinstance(frag, dict):
                continue
            content = frag.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            typ = (frag.get("type") or "MESSAGE").upper()
            role = "USER" if typ == "REQUEST" else ("ASSISTANT" if typ == "RESPONSE" else typ)
            lines.append(f"## {role}")
            lines.append(content.strip())
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def load_conversations(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("conversations.json: ожидается JSON-массив")
    return data


def select_pension_conversations(
    conversations: list[dict],
    *,
    title_re: re.Pattern[str] | None = None,
    limit: int | None = 5,
) -> list[dict]:
    """Пилотные пенсионные диалоги по заголовку (без продуктовых чатов)."""
    pat = title_re or _DEFAULT_TITLE_RE
    hits: list[dict] = []
    for conv in conversations:
        title = conv.get("title") or ""
        if _SKIP_TITLE_RE.search(title):
            continue
        if not pat.search(title):
            continue
        hits.append(conv)
    hits.sort(key=lambda c: c.get("updated_at") or c.get("inserted_at") or "", reverse=True)
    if limit is not None:
        return hits[:limit]
    return hits


def conversation_to_cleaned_markdown(conv: dict, *, client_name: str | None = None) -> str:
    raw = extract_conversation_markdown(conv)
    return depersonalize_text(raw, client_name=client_name)


def import_deepseek_conversations(
    conversations_path: Path,
    *,
    registry: KnowledgeCaseRegistry | None = None,
    cleaned_dir: Path | None = None,
    limit: int | None = 5,
    title_re: re.Pattern[str] | None = None,
    client_name: str | None = None,
) -> list[KnowledgeCase]:
    """
    Выбирает пенсионные диалоги, пишет обезличенный MD (опционально)
    и создаёт draft-кейсы в реестре.
    """
    registry = registry or KnowledgeCaseRegistry()
    conversations = load_conversations(conversations_path)
    selected = select_pension_conversations(
        conversations, title_re=title_re, limit=limit
    )
    if cleaned_dir is not None:
        cleaned_dir.mkdir(parents=True, exist_ok=True)

    imported: list[KnowledgeCase] = []
    for conv in selected:
        cid = str(conv.get("id") or "unknown")[:8]
        safe_md = conversation_to_cleaned_markdown(conv, client_name=client_name)
        # не сохраняем исходный title с возможными фамилиями в имени файла
        tmp_name = f"deepseek-{cid}.md"
        if cleaned_dir is not None:
            out_path = cleaned_dir / tmp_name
            out_path.write_text(safe_md, encoding="utf-8")
            case = import_dialog_to_case(out_path, registry=registry)
        else:
            # временный файл рядом с реестром
            tmp = registry.cases_dir / f"_tmp_{tmp_name}"
            tmp.write_text(safe_md, encoding="utf-8")
            try:
                case = import_dialog_to_case(tmp, registry=registry)
            finally:
                tmp.unlink(missing_ok=True)
        case.source_file = f"deepseek:{cid}"
        case.notes = (
            (case.notes or "")
            + f" Импорт из DeepSeek conversations.json, id={conv.get('id')}."
        ).strip()
        registry.save(case)
        imported.append(case)
    return imported
