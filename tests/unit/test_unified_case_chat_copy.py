"""Канон единого чата: одна MAX CTA, без «кабинет основной / MAX — уведомления»."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

BANNED = (
    "ответ появится в кабинете, а в max придёт уведомление",
    "max — только уведомления",
    "кабинет — основной чат",
    "ответ появится здесь и придёт в max",
    "ответ придёт в max",
    "вопросы по делу — в чате max",
)

CABINET_FILES = (
    REPO / "apps/cabinet/src/components/case-work-map.tsx",
    REPO / "apps/cabinet/src/components/client-case-chat-panel.tsx",
    REPO / "apps/cabinet/src/components/client-cabinet.tsx",
    REPO / "shared/case-chat-copy.ts",
)


def test_unified_chat_copy_not_notification_channel() -> None:
    for path in CABINET_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in BANNED:
            assert phrase not in text, f"{path.name}: запрещено «{phrase}»"


def test_quick_question_chips_insert_into_draft_not_send() -> None:
  panel = (REPO / "apps/cabinet/src/components/client-case-chat-panel.tsx").read_text(
      encoding="utf-8"
  )
  cabinet = (REPO / "apps/cabinet/src/components/client-cabinet.tsx").read_text(
      encoding="utf-8"
  )
  assert "insertDraft(question)" in panel
  assert "inputRef.current?.value ?? body" in panel
  assert "onSendQuick" not in panel
  assert "onSendQuick" not in cabinet
  assert "client_message_id" in cabinet


def test_single_max_cta_button_in_chat_header() -> None:
    panel = (REPO / "apps/cabinet/src/components/client-case-chat-panel.tsx").read_text(
        encoding="utf-8"
    )
    left = (REPO / "apps/cabinet/src/components/case-work-map.tsx").read_text(encoding="utf-8")
    assert "CASE_CHAT_MAX_BUTTON" in panel
    assert "CASE_CHAT_MAX_BUTTON" not in left
    assert left.count("Открыть этот чат в MAX") == 0
    assert panel.count("{CASE_CHAT_MAX_BUTTON}") == 1
    assert "#case-chat-input" in left
