"""Разбор ФИО: обращение и шапка без мусора."""

from __future__ import annotations

from sfrfr.utils.person_name import (
    client_salutation,
    display_person_name,
    parse_person_name,
    should_accept_incoming_display_name,
    welcome_first_name,
)


def test_full_fio_russian() -> None:
    p = parse_person_name("иванов иван иванович")
    assert p.salutation == "Иван Иванович"
    assert p.display == "Иванов Иван Иванович"
    assert p.confidence == "high"
    assert p.needs_confirm is False


def test_surname_name_russian() -> None:
    assert client_salutation("Петров Пётр") == "Пётр"
    assert display_person_name("Петров Пётр") == "Петров Пётр"


def test_latin_given_surname() -> None:
    p = parse_person_name("Ivan Petrov")
    assert p.salutation == "Ivan"
    assert p.display == "Ivan Petrov"


def test_single_name_from_max() -> None:
    assert welcome_first_name("Владимир") == "Владимир"
    assert client_salutation("Мария") == "Мария"


def test_garbage_rejected() -> None:
    assert display_person_name("xkcdqplmz") is None
    assert client_salutation("!!!@@@") == "Клиент"
    assert display_person_name("a1b2c3") is None
    assert display_person_name("MAX 12345") is None
    assert welcome_first_name("user_99") is None


def test_mixed_script_token_rejected() -> None:
    assert display_person_name("Ивan") is None


def test_should_not_store_garbage_over_placeholder() -> None:
    assert should_accept_incoming_display_name("MAX 1", "Владимир") is True
    assert should_accept_incoming_display_name("MAX 1", "asdfghjkl") is False
    assert should_accept_incoming_display_name("Иванов Иван", "Владимир") is False


def test_name_otchestvo_without_surname() -> None:
    p = parse_person_name("Анна Сергеевна")
    assert p.salutation == "Анна Сергеевна"
    assert p.confidence == "high"
