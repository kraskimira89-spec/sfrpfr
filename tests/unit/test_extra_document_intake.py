"""Доп. документы на любом этапе: категории, почта по токену, без сброса маршрута."""

from __future__ import annotations

from pathlib import Path

from sfrfr.services.extra_document_intake import (
    CATEGORIES,
    RECEIVED_CLIENT_MESSAGE,
    UnboundMailQueue,
    bind_case_from_mail_subject,
    build_mail_compose,
    category_to_doc_type,
    doc_type_is_extra,
    extra_upload_preserves_funnel,
    make_case_mail_token,
    should_reset_funnel_on_extra_upload,
    staff_review_task_title,
)


def test_categories_cover_tz() -> None:
    codes = {c["code"] for c in CATEGORIES}
    assert codes == {
        "children",
        "stazh",
        "guardianship",
        "contract",
        "other",
        "unknown",
    }


def test_doc_type_mapping_and_extra_flag() -> None:
    assert category_to_doc_type("children") == "extra_children"
    assert category_to_doc_type(None) == "extra_unknown"
    assert category_to_doc_type("weird") == "extra_unknown"
    assert doc_type_is_extra("extra_stazh")
    assert not doc_type_is_extra("ils")


def test_mail_token_binds_only_with_secret(tmp_path: Path) -> None:
    token = make_case_mail_token("11111111-1111-1111-1111-111111111111", secret="s3cret")
    assert len(token) >= 8
    hit = bind_case_from_mail_subject(
        f"Re: документы [SFRFR-DOC {token}]",
        secret="s3cret",
        known_case_ids=["11111111-1111-1111-1111-111111111111"],
    )
    assert hit == "11111111-1111-1111-1111-111111111111"
    # чужой секрет / угадывание по ФИО — не привязываем
    assert (
        bind_case_from_mail_subject(
            "Иванов Иван документы",
            secret="s3cret",
            known_case_ids=["11111111-1111-1111-1111-111111111111"],
            sender="ivanov@example.com",
        )
        is None
    )
    assert (
        bind_case_from_mail_subject(
            f"[SFRFR-DOC {token}]",
            secret="other",
            known_case_ids=["11111111-1111-1111-1111-111111111111"],
        )
        is None
    )


def test_ambiguous_without_token_goes_unbound(tmp_path: Path) -> None:
    q = UnboundMailQueue(root=tmp_path)
    row = q.enqueue(
        message_id="<abc@mail>",
        subject="справка о стаже",
        sender="a@b.ru",
        attachment_names=["scan.pdf"],
    )
    assert row["status"] == "needs_binding"
    assert q.get_by_message_id("<abc@mail>") is not None
    # повтор — без дубля
    again = q.enqueue(
        message_id="<abc@mail>",
        subject="справка о стаже",
        sender="a@b.ru",
        attachment_names=["scan.pdf"],
    )
    assert again["id"] == row["id"]
    assert again.get("deduped") is True


def test_extra_upload_does_not_reset_funnel() -> None:
    assert extra_upload_preserves_funnel("extra_children") is True
    assert should_reset_funnel_on_extra_upload("extra_children") is False
    assert extra_upload_preserves_funnel("ils") is False


def test_client_message_and_task_title() -> None:
    assert "получен и добавлен" in RECEIVED_CLIENT_MESSAGE.lower()
    assert "не нужно" in RECEIVED_CLIENT_MESSAGE.lower()
    assert "принят" not in RECEIVED_CLIENT_MESSAGE.lower()  # не до проверки сотрудником
    title = staff_review_task_title(category="stazh", may_affect_analysis=True)
    assert "Проверить новый документ" in title
    assert "разбор" in title.lower()


def test_mail_compose_shows_opaque_subject() -> None:
    out = build_mail_compose(
        case_id="11111111-1111-1111-1111-111111111111",
        inbox="proverkastaza@yandex.ru",
        secret="s3cret",
    )
    assert out["to"] == "proverkastaza@yandex.ru"
    assert "SFRFR-DOC" in out["subject"]
    assert "11111111" not in out["subject"]  # не светим UUID целиком в теме без токена
    assert out["mailto"].startswith("mailto:proverkastaza@yandex.ru")
