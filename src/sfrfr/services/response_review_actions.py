"""Word / почта / Я.Диск для разбора входящего ответа (full_analysis_docx + mail)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sfrfr.db.case_repository import CaseRepository
from sfrfr.services.full_analysis_docx import build_full_analysis_docx_bytes
from sfrfr.services.response_review import (
    RESPONDENT_LABELS,
    ResponseReviewError,
    serialize_review,
)


def build_response_review_docx(
    *,
    case_ref: str,
    review: dict[str, Any],
) -> bytes:
    md = str(review.get("staff_draft_md") or review.get("ai_draft_md") or "")
    organ = RESPONDENT_LABELS.get(
        str(review.get("respondent") or "sfr"), "орган"
    )
    return build_full_analysis_docx_bytes(
        case_ref=case_ref,
        markdown=md,
        version=1,
        title=f"Разбор входящего ответа ({organ})",
        note=(
            f"Проект разбора ответа ({organ}). Не является решением фонда "
            "и не обещает выплату. Положительный ответ органа ≠ фактическая выплата."
        ),
    )


def send_response_review_email(
    repo: CaseRepository,
    *,
    case_id: str,
    case_ref: str,
    review: dict[str, Any],
    actor_id: str | None,
    to: str,
    subject: str | None = None,
    body: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    if str(review.get("status")) != "reviewed":
        raise ResponseReviewError("сначала отметьте разбор как проверенный сотрудником")
    organ = RESPONDENT_LABELS.get(
        str(review.get("respondent") or "sfr"), "органа"
    )
    filename = f"otvet-{case_ref[:24]}.docx".replace(" ", "_")
    docx = build_response_review_docx(case_ref=case_ref, review=review)
    subj = (subject or "").strip() or f"Разбор входящего ответа ({organ}) · дело {case_ref}"
    text = (body or "").strip() or (
        f"Здравствуйте!\n\n"
        f"Направляем разбор входящего ответа ({organ}) по делу {case_ref} "
        f"во вложении Word.\n\n"
        f"Положительный ответ органа не означает фактическую выплату — решение "
        f"и суммы фиксирует только СФР.\n\n"
        f"Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
        f"Решение принимает СФР."
    )
    preview = {
        "ok": False,
        "preview": True,
        "to": (to or "").strip(),
        "subject": subj,
        "body": text,
        "attachment": filename,
        "attachment_bytes": len(docx),
        "review_id": review.get("id"),
    }
    if not confirm:
        return preview
    if "@" not in (to or ""):
        return {**preview, "error": "invalid_to", "preview": False}

    from sfrfr.integrations.yandex_workspace import send_mail

    result = send_mail(
        to=to,
        template="custom",
        case_id=case_id,
        subject=subj,
        body=text,
        attachments=[
            (
                filename,
                docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        ],
    )
    if result.get("ok"):
        updated = _mark_sent(repo, review, channel="email", actor_id=actor_id, case_id=case_id)
        return {
            "ok": True,
            "channel": "email",
            "to": to,
            "subject": subj,
            "attachment": filename,
            "provider": result.get("provider"),
            "review": serialize_review(updated or review),
        }
    err = str(result.get("error") or result.get("reason") or "email_failed")
    if result.get("skipped"):
        err = str(result.get("reason") or "email_disabled")
    return {"ok": False, "error": err, "preview": False, "review_id": review.get("id")}


def send_response_review_yadisk(
    repo: CaseRepository,
    *,
    case_id: str,
    case_ref: str,
    review: dict[str, Any],
    actor_id: str | None,
    confirm: bool = False,
) -> dict[str, Any]:
    if str(review.get("status")) != "reviewed":
        raise ResponseReviewError("сначала отметьте разбор как проверенный сотрудником")
    filename = f"otvet-sfr-{case_ref[:24]}.docx".replace(" ", "_")
    docx = build_response_review_docx(case_ref=case_ref, review=review)
    preview = {
        "ok": False,
        "preview": True,
        "channel": "yadisk",
        "attachment": filename,
        "attachment_bytes": len(docx),
        "review_id": review.get("id"),
    }
    if not confirm:
        return preview

    from sfrfr.integrations.yandex_workspace.disk import (
        mirror_case_document,
        publish_case_file,
    )

    up = mirror_case_document(
        case_id,
        filename,
        docx,
        subfolder="outgoing",
    )
    if up.get("skipped"):
        return {
            "ok": False,
            "error": str(up.get("reason") or "yandex_disk_disabled"),
            "preview": False,
        }
    if not up.get("ok"):
        return {
            "ok": False,
            "error": str(up.get("error") or "yadisk_upload_failed"),
            "preview": False,
        }
    path = str(up.get("path") or "")
    if not path:
        folder = up.get("folder_name") or ""
        remote = up.get("remote_name") or filename
        if folder:
            path = f"disk:/SFRFR-cases/{folder}/outgoing/{remote}"
    pub = publish_case_file(path) if path else {"ok": False, "error": "no_disk_path"}
    if not pub.get("ok"):
        return {
            "ok": False,
            "error": str(pub.get("error") or "yadisk_publish_failed"),
            "preview": False,
            "hint": "Файл на Диске есть, но публичная ссылка не выдана — не пишем «отправлено».",
        }
    updated = _mark_sent(repo, review, channel="yadisk", actor_id=actor_id, case_id=case_id)
    public_url = str(pub.get("public_url") or "")
    return {
        "ok": True,
        "channel": "yadisk",
        "public_url": public_url,
        "path": path,
        "attachment": filename,
        "chat_hint": (
            f"Здравствуйте! Разбор ответа СФР по делу {case_ref}: {public_url}\n\n"
            f"Положительный ответ фонда не означает фактическую выплату."
        ),
        "review": serialize_review(updated or review),
    }


def _mark_sent(
    repo: CaseRepository,
    review: dict[str, Any],
    *,
    channel: str,
    actor_id: str | None,
    case_id: str,
) -> dict[str, Any] | None:
    now = datetime.now(UTC).isoformat()
    updated = repo.update_response_review(
        str(review["id"]),
        {"sent_at": now, "sent_channel": channel, "updated_at": now},
    )
    repo.audit(case_id, actor_id, f"response_review_sent:{channel}")
    return updated
