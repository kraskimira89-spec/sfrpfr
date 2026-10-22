"""Извлечение ФИО из текста документа / реплики (синтетические имена)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.client_fio_from_text import (
    extract_fio_from_text,
    maybe_apply_client_fio_from_text,
    should_replace_client_fio,
)
from sfrfr.utils.person_name import parse_person_name


def test_extract_labeled_fio_from_ils_like_text() -> None:
    text = (
        "Сведения о состоянии индивидуального лицевого счёта\n"
        "ФИО: Сидоров Пётр Николаевич\n"
        "СНИЛС: ***-***-*** **\n"
    )
    parsed = extract_fio_from_text(text, source="document")
    assert parsed is not None
    assert parsed.display == "Сидоров Пётр Николаевич"
    assert parsed.salutation == "Пётр Николаевич"
    assert parsed.confidence == "high"


def test_extract_line_fio_with_patronymic() -> None:
    text = "Страница 1\nКозлова Анна Сергеевна\nГод рождения …\n"
    parsed = extract_fio_from_text(text, source="document")
    assert parsed is not None
    assert parsed.given == "Анна"
    assert parsed.patronymic == "Сергеевна"


def test_ambiguous_two_strong_fio_returns_none() -> None:
    text = (
        "ФИО: Сидоров Пётр Николаевич\n"
        "ФИО: Иванов Иван Иванович\n"
    )
    assert extract_fio_from_text(text, source="document") is None


def test_client_intro_name_otchestvo() -> None:
    parsed = extract_fio_from_text(
        "Здравствуйте, меня зовут Пётр Николаевич",
        source="client_text",
    )
    assert parsed is not None
    assert parsed.salutation == "Пётр Николаевич"


def test_should_replace_placeholder_and_upgrade_max_name() -> None:
    incoming = parse_person_name("Сидоров Пётр Николаевич")
    assert should_replace_client_fio("MAX 12345", incoming) is True
    assert should_replace_client_fio("Пётр", incoming) is True
    assert should_replace_client_fio("Сидоров Пётр Николаевич", incoming) is False


def test_maybe_apply_writes_full_name() -> None:
    client = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_case_row.return_value = {
        "id": "case-1",
        "client_id": "client-1",
        "clients": {"id": "client-1", "full_name": "MAX 9"},
    }
    with (
        patch(
            "sfrfr.db.case_repository.CaseRepository",
            return_value=mock_repo,
        ),
        patch(
            "sfrfr.db.session.get_supabase_client",
            return_value=client,
        ),
        patch(
            "sfrfr.integrations.yandex_workspace.sync_case_disk_folder_name_safe",
            MagicMock(),
        ),
    ):
        out = maybe_apply_client_fio_from_text(
            case_id="case-1",
            text="ФИО: Сидоров Пётр Николаевич\n",
            source="document",
        )
    assert out is not None
    assert out["reason"] == "applied"
    client.table.assert_called()
