"""Формат идентификации клиента в ops-уведомлениях MAX."""

from __future__ import annotations

from sfrfr.integrations.max.ops_client_label import (
    format_ops_client_block,
    is_placeholder_client_name,
    lookup_ops_client_full_name,
    normalize_ops_full_name,
    should_store_max_display_name,
)


def test_format_ops_client_block_with_fio() -> None:
    text = format_ops_client_block(
        max_user_id="12495389",
        full_name="Иванов Иван Иванович",
    )
    assert text == (
        "Клиент: Иванов Иван Иванович\n"
        "MAX user_id: 12495389"
    )


def test_format_ops_client_block_without_fio() -> None:
    text = format_ops_client_block(max_user_id=42, full_name=None)
    assert "ФИО: не указано" in text
    assert "MAX user_id: 42" in text


def test_format_ops_client_block_without_max() -> None:
    text = format_ops_client_block(
        max_user_id=None,
        full_name="Петрова Анна",
    )
    assert text.startswith("Клиент: Петрова Анна")
    assert "MAX user_id: не привязан" in text


def test_should_store_max_display_name_only_over_placeholder() -> None:
    assert should_store_max_display_name("MAX 177840706", "Владимир") is True
    assert should_store_max_display_name("", "Оксана") is True
    assert should_store_max_display_name("Иванов Иван", "Владимир") is False
    assert should_store_max_display_name("MAX 1", "MAX 2") is False


def test_placeholder_names_rejected() -> None:
    assert is_placeholder_client_name("MAX user 123")
    assert is_placeholder_client_name("MAX 999")
    assert is_placeholder_client_name("")
    assert normalize_ops_full_name("MAX user 1") is None
    assert normalize_ops_full_name("Сидоров Пётр") == "Сидоров Пётр"


def test_lookup_prefers_client_row(monkeypatch) -> None:
    name = lookup_ops_client_full_name(
        max_user_id="1",
        case_id="c1",
        client_row={"full_name": "Козлова Мария"},
    )
    assert name == "Козлова Мария"


def test_lookup_skips_placeholder_row() -> None:
    name = lookup_ops_client_full_name(
        client_row={"full_name": "MAX user 55"},
    )
    assert name is None
