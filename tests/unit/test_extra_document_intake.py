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


def test_review_statuses_received_checked_needs_clarification(tmp_path: Path) -> None:
    from sfrfr.services.extra_document_intake import (
        REVIEW_STATUSES,
        ExtraDocumentReviewStore,
    )

    assert set(REVIEW_STATUSES) == {"received", "checked", "needs_clarification"}
    store = ExtraDocumentReviewStore(root=tmp_path)
    row = store.mark_received("doc-1", case_id="case-a", source="cabinet")
    assert row["status"] == "received"
    assert store.get("doc-1")["status"] == "received"

    checked = store.set_status(
        "doc-1",
        status="checked",
        actor_id="staff-1",
        analysis_update_needed=False,
    )
    assert checked["status"] == "checked"
    assert checked.get("analysis_update_needed") is False

    clarify = store.set_status(
        "doc-1",
        status="needs_clarification",
        actor_id="staff-1",
        analysis_update_needed=True,
        note="Нужна дата на справке",
    )
    assert clarify["status"] == "needs_clarification"
    assert clarify["analysis_update_needed"] is True
    assert "дата" in str(clarify.get("note") or "").lower()


def test_set_status_rejects_unknown(tmp_path: Path) -> None:
    from sfrfr.services.extra_document_intake import ExtraDocumentReviewStore

    store = ExtraDocumentReviewStore(root=tmp_path)
    store.mark_received("doc-2", case_id="c", source="email")
    try:
        store.set_status("doc-2", status="accepted", actor_id="s")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "invalid_status" in str(exc)


def test_unbound_mark_bound_to_case(tmp_path: Path) -> None:
    q = UnboundMailQueue(root=tmp_path)
    row = q.enqueue(
        message_id="<x@y>",
        subject="без токена",
        sender="a@b.ru",
        attachment_names=["a.pdf"],
    )
    bound = q.mark_bound(
        row["id"],
        case_id="11111111-1111-1111-1111-111111111111",
        actor_id="staff-1",
    )
    assert bound["status"] == "bound"
    assert bound["case_id"].startswith("11111111")
    assert q.list_pending() == []


def test_request_analysis_update_preserves_funnel(tmp_path: Path, monkeypatch) -> None:
    from sfrfr.services import extra_document_intake as mod
    from sfrfr.services.extra_document_intake import (
        ExtraDocumentReviewStore,
        request_analysis_update_review,
    )

    monkeypatch.setattr(
        mod,
        "ExtraDocumentReviewStore",
        lambda: ExtraDocumentReviewStore(root=tmp_path),
    )
    store = ExtraDocumentReviewStore(root=tmp_path)
    store.mark_received("doc-x", case_id="case-1", source="email")

    calls: list[dict] = []

    class Repo:
        def upsert_checklist_item(self, case_id, **kwargs):
            calls.append({"case_id": case_id, **kwargs})

        def audit(self, case_id, actor_id, action):
            calls.append({"audit": action, "case_id": case_id})

    out = request_analysis_update_review(
        repo=Repo(),
        case_id="case-1",
        document_id="doc-x",
        actor_id="staff-1",
        note="справка новая",
    )
    assert out["preserves_funnel"] is True
    assert out["review"]["status"] == "needs_clarification"
    assert out["review"]["analysis_update_needed"] is True
    assert any("обновить разбор" in str(c.get("title") or "") for c in calls)
