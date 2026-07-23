"""Тест импорта DeepSeek conversations.json (мини-фикстура)."""

from __future__ import annotations

import json
from pathlib import Path

from sfrfr.ai.knowledge.deepseek_export import (
    extract_conversation_markdown,
    import_deepseek_conversations,
)
from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry
from sfrfr.ai.schemas.knowledge_case import KnowledgeQuality


def _sample_conv() -> dict:
    return {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "title": "КЛИ СФР ПФР проверка стажа",
        "updated_at": "2026-05-28T18:00:00Z",
        "mapping": {
            "1": {
                "id": "1",
                "message": {
                    "inserted_at": "2026-05-28T18:00:01Z",
                    "fragments": [
                        {
                            "type": "REQUEST",
                            "content": "Проверь ИЛС и трудовую. СНИЛС 123-456-789 01.",
                        }
                    ],
                },
            },
            "2": {
                "id": "2",
                "message": {
                    "inserted_at": "2026-05-28T18:00:02Z",
                    "fragments": [
                        {
                            "type": "RESPONSE",
                            "content": "Вижу расхождение стажа. Нужен перерасчёт.",
                        }
                    ],
                },
            },
        },
    }


def test_extract_markdown_roles() -> None:
    md = extract_conversation_markdown(_sample_conv())
    assert "## USER" in md
    assert "## ASSISTANT" in md
    assert "ИЛС" in md


def test_import_deepseek_fixture(tmp_path: Path) -> None:
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps([_sample_conv()], ensure_ascii=False), encoding="utf-8")
    registry = KnowledgeCaseRegistry(tmp_path / "cases")
    cleaned = tmp_path / "cleaned"
    cases = import_deepseek_conversations(
        path, registry=registry, cleaned_dir=cleaned, limit=5
    )
    assert len(cases) == 1
    assert cases[0].quality == KnowledgeQuality.DRAFT
    assert "123-456-789 01" not in cases[0].summary
    assert (cleaned / "deepseek-aaaaaaaa.md").exists()
