"""Отправка версии подробного разбора: почта (DOCX) и Яндекс Диск (публичная ссылка на файл)."""

from __future__ import annotations

from typing import Any

from sfrfr.services.full_analysis_docx import build_full_analysis_docx_bytes
from sfrfr.services.full_analysis_workflow import FullAnalysisWorkflow


def build_version_docx(
    *,
    case_ref: str,
    version: dict[str, Any],
) -> bytes:
    return build_full_analysis_docx_bytes(
        case_ref=case_ref,
        markdown=str(version.get("markdown") or ""),
        version=int(version.get("n") or 1),
    )


def send_version_email(
    *,
    case_id: str,
    case_ref: str,
    version: dict[str, Any],
    to: str,
    subject: str | None = None,
    body: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Отправить DOCX на почту. Без confirm — только превью (ok=false, preview=…)."""
    wf = FullAnalysisWorkflow()
    n = int(version.get("n") or 1)
    filename = f"razbor-{case_ref[:24]}-v{n}.docx".replace(" ", "_")
    docx = build_version_docx(case_ref=case_ref, version=version)
    subj = (subject or "").strip() or f"Подробный разбор на согласование (версия {n})"
    text = (body or "").strip() or (
        f"Здравствуйте!\n\n"
        f"Направляем подробный разбор по делу {case_ref} (версия {n}) "
        f"во вложении Word для согласования.\n\n"
        f"Ответьте, пожалуйста: «Согласовать» или опишите замечания "
        f"(даты, ФИО, события). Можно прислать свою правленную версию файла.\n\n"
        f"Согласование разбора не означает согласия на подготовку обращений — "
        f"это следующий этап.\n\n"
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
        "version_id": version.get("id"),
        "version_n": n,
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
        wf.mark_sent(case_id, str(version["id"]), channel="email")
        return {
            "ok": True,
            "channel": "email",
            "to": to,
            "subject": subj,
            "attachment": filename,
            "provider": result.get("provider"),
            "version_id": version.get("id"),
            "version_n": n,
        }
    err = str(result.get("error") or result.get("reason") or "email_failed")
    if result.get("skipped"):
        err = str(result.get("reason") or "email_disabled")
    wf.mark_delivery_error(case_id, str(version["id"]), error=err)
    return {
        "ok": False,
        "error": err,
        "detail": result.get("detail") or result.get("hint"),
        "preview": False,
        "version_id": version.get("id"),
    }


def send_version_yadisk(
    *,
    case_id: str,
    case_ref: str,
    version: dict[str, Any],
    folder_name: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Загрузить DOCX в outgoing дела и опубликовать ссылку на файл (не на папку)."""
    wf = FullAnalysisWorkflow()
    n = int(version.get("n") or 1)
    filename = f"razbor-{case_ref[:24]}-v{n}.docx".replace(" ", "_")
    docx = build_version_docx(case_ref=case_ref, version=version)
    preview = {
        "ok": False,
        "preview": True,
        "channel": "yadisk",
        "filename": filename,
        "attachment_bytes": len(docx),
        "version_id": version.get("id"),
        "version_n": n,
        "note": "Публикуется только этот файл в outgoing/, не вся папка дела.",
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
        folder_name=folder_name,
    )
    if up.get("skipped"):
        err = str(up.get("reason") or "yandex_disk_disabled")
        wf.mark_delivery_error(case_id, str(version["id"]), error=err)
        return {"ok": False, "error": err, "honest": True, "preview": False}
    if not up.get("ok"):
        err = str(up.get("error") or "yadisk_upload_failed")
        wf.mark_delivery_error(case_id, str(version["id"]), error=err)
        return {
            "ok": False,
            "error": err,
            "detail": up.get("detail"),
            "preview": False,
        }

    path = str(up.get("path") or "")
    if not path:
        # mirror может вернуть remote_name без полного path
        folder = up.get("folder_name") or ""
        remote = up.get("remote_name") or filename
        if folder:
            path = f"disk:/SFRFR-cases/{folder}/outgoing/{remote}"

    pub = publish_case_file(path) if path else {"ok": False, "error": "no_disk_path"}
    if not pub.get("ok"):
        err = str(pub.get("error") or "yadisk_publish_failed")
        wf.mark_delivery_error(case_id, str(version["id"]), error=err)
        return {
            "ok": False,
            "error": err,
            "detail": pub.get("detail"),
            "uploaded": True,
            "path": path,
            "honest": True,
            "preview": False,
            "hint": "Файл на Диске есть, но публичная ссылка не выдана — не пишем «отправлено».",
        }

    public_url = str(pub.get("public_url") or "")
    wf.mark_sent(case_id, str(version["id"]), channel="yadisk")
    chat_hint = (
        f"Здравствуйте! Подробный разбор (версия {n}) на согласование: {public_url}\n\n"
        f"Ответьте «Согласовать» или пришлите замечания / свою версию файла. "
        f"Согласование разбора ≠ согласие на подготовку обращений."
    )
    return {
        "ok": True,
        "channel": "yadisk",
        "public_url": public_url,
        "path": path,
        "filename": filename,
        "version_id": version.get("id"),
        "version_n": n,
        "chat_hint": chat_hint,
    }
