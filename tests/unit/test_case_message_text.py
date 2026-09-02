"""Префикс [[internal]] в текстах case_messages."""

from sfrfr.services.case_message_text import (
    mark_internal_staff_body,
    strip_internal_staff_prefix,
)


def test_strip_internal_prefix() -> None:
    assert strip_internal_staff_prefix("[[internal]] заметка") == "заметка"
    assert strip_internal_staff_prefix("[[internal]]Здравствуйте") == "Здравствуйте"
    assert strip_internal_staff_prefix("обычный текст") == "обычный текст"


def test_mark_internal_prefix() -> None:
    assert mark_internal_staff_body("заметка") == "[[internal]] заметка"
    assert mark_internal_staff_body("[[internal]] уже") == "[[internal]] уже"
