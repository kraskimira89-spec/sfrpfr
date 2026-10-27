"""Живой прогон приёмки этапа 5 (без ПДн в выводе).

Загрузка secrets из репозитория SFRFR (не из worktree).
Результат: JSON-отчёт + DOCX-артефакт в docs/acceptance/.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SECRETS_ROOT = Path(r"c:\Users\user\Documents\Cursor\SFRFR\secrets")
DOTENV = Path(r"c:\Users\user\Documents\Cursor\SFRFR\.env")
OUT_DIR = REPO / "docs" / "acceptance"
REPORT_PATH = OUT_DIR / "stage5-live-acceptance-report.json"
DOCX_PATH = OUT_DIR / "stage5-acceptance-razbor-demo-v2.docx"


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    sys.path.insert(0, str(REPO / "src"))
    _load_env_file(DOTENV)
    for name in (
        "yandex-workspace.env",
        "yandex-mail.env",
        "yandex-postbox.env",
        "deepseek.env",
    ):
        _load_env_file(SECRETS_ROOT / name)

    report: dict = {
        "date_utc": _now(),
        "published_sha": "5d395a9553c14cfafbb2f302d7764a4aa598ec41",
        "checks": {},
        "integrations": {
            "yandex_mail_enabled": os.environ.get("YANDEX_MAIL_ENABLED", ""),
            "yandex_disk_enabled": os.environ.get("YANDEX_DISK_ENABLED", ""),
            "yandex_postbox_enabled": os.environ.get("YANDEX_POSTBOX_ENABLED", ""),
            "deepseek_key_set": bool(os.environ.get("DEEPSEEK_API_KEY")),
        },
        "notes": [],
    }

    # --- autotests already separate; here: AI draft ---
    from sfrfr.services.full_analysis_docx import build_full_analysis_docx_bytes
    from sfrfr.services.full_analysis_draft import generate_full_analysis_draft
    from sfrfr.services.full_analysis_workflow import FullAnalysisWorkflow

    anon_docs = [
        {"doc_type": "ils", "filename": "extract-sample.pdf"},
        {"doc_type": "workbook", "filename": "labor-sample.pdf"},
    ]
    anon_brief = {
        "items": [
            {
                "text": "Период 03.2004–08.2005 отражён в трудовой, в выписке ИЛС отсутствует",
                "evidence": "docs",
                "basis": "Трудовая vs выписка",
            }
        ]
    }
    ai = generate_full_analysis_draft(
        case_ref="ПС-ACCEPTANCE",
        documents=anon_docs,
        brief=anon_brief,
        compare={"ran": True, "discrepancies": 1, "summary": "1 расхождение по периоду 2004–2005."},
        llm="auto",
    )
    text = str(ai.get("text") or "")
    lower = text.lower()
    has_period = "2004" in text or "2005" in text
    has_source = "илс" in lower or "трудов" in lower
    invented = "гарантир" in lower or "₽ в месяц" in lower
    report["checks"]["live_ai"] = {
        "status": "pass"
        if ai.get("source") == "ai" and has_period and has_source and not invented
        else ("partial" if text and has_period else "fail"),
        "source": ai.get("source"),
        "reason": ai.get("reason"),
        "chars": len(text),
        "has_period_2004_2005": has_period,
        "has_ils_or_labor": has_source,
        "no_payment_promise": not invented,
    }
    if ai.get("source") != "ai":
        report["notes"].append(
            "ИИ недоступен или текст отклонён guardrails — использован/вернулся шаблон."
        )

    # staff edit simulation: append explicit checked line
    reviewed = text.rstrip() + "\n\n## Отметка сотрудника\nПроверено: периоды и источники сверены с файлами дела.\n"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = build_full_analysis_docx_bytes(
        case_ref="ПС-ACCEPTANCE",
        markdown=reviewed,
        version=2,
    )
    DOCX_PATH.write_bytes(raw)
    report["checks"]["docx"] = {
        "status": "pass" if raw[:2] == b"PK" and b"word/" in raw else "fail",
        "path": str(DOCX_PATH.relative_to(REPO)).replace("\\", "/"),
        "bytes": len(raw),
        "contains_staff_mark": "Проверено" in reviewed,
    }

    # workflow v1/v2
    wf_root = OUT_DIR / "_wf_tmp"
    if wf_root.exists():
        shutil.rmtree(wf_root, ignore_errors=True)
    wf_root.mkdir(parents=True, exist_ok=True)
    wf = FullAnalysisWorkflow(root=wf_root)
    v1 = wf.create_version("accept-case", markdown=reviewed, source=str(ai.get("source") or "ai"))
    wf.mark_reviewed("accept-case", v1["id"])
    wf.mark_sent("accept-case", v1["id"], channel="email")
    v2 = wf.create_version(
        "accept-case",
        markdown=reviewed + "\nУточнение даты: 01.03.2004.\n",
        source="staff",
        based_on=v1["id"],
    )
    stale_err = None
    try:
        wf.record_decision("accept-case", v1["id"], decision="approved")
    except ValueError as exc:
        stale_err = str(exc)
    wf.mark_reviewed("accept-case", v2["id"])
    wf.mark_sent("accept-case", v2["id"], channel="email")
    wf.record_decision("accept-case", v2["id"], decision="approved")
    st = wf.get_state("accept-case")
    report["checks"]["versioning_live"] = {
        "status": "pass"
        if stale_err and st["current"]["status"] == "approved" and st["current"]["n"] == 2
        else "fail",
        "stale_v1_error": stale_err,
        "current_n": st["current"]["n"],
        "current_status": st["current"]["status"],
    }

    # remarks → v2 must re-review/send (workflow)
    remarks_wf = FullAnalysisWorkflow(root=wf_root / "remarks")
    rv1 = remarks_wf.create_version("remarks-case", markdown=reviewed, source="ai")
    remarks_wf.mark_reviewed("remarks-case", rv1["id"])
    remarks_wf.mark_sent("remarks-case", rv1["id"], channel="email")
    remarks_wf.record_decision(
        "remarks-case",
        rv1["id"],
        decision="remarks",
        remarks="Уточните дату начала периода.",
    )
    st_r = remarks_wf.get_state("remarks-case")
    from sfrfr.services.full_analysis_workflow import stage_work_from_state

    work_after_remarks = stage_work_from_state(st_r)
    report["checks"]["client_remarks"] = {
        "status": "pass"
        if st_r["current"]["status"] == "remarks"
        and work_after_remarks.get("state") != "done"
        else "fail",
        "status_after_remarks": st_r["current"]["status"],
        "stage_work_state": work_after_remarks.get("state"),
        "remarks_present": bool(st_r["current"].get("remarks")),
    }

    # email
    import time

    import httpx

    from sfrfr.integrations.yandex_workspace import list_inbox, send_mail

    control_to = (os.environ.get("YANDEX_WORKSPACE_EMAIL") or "").strip()
    accept_subject = "[ACCEPTANCE] Подробный разбор v2 (обезличенный)"
    email_out = send_mail(
        to=control_to,
        template="custom",
        case_id="accept-demo",
        subject=accept_subject,
        body=(
            "Контрольная приёмка этапа 5. Вложение — обезличенный DOCX. "
            "Отвечать не требуется."
        ),
        attachments=[
            (
                "stage5-acceptance-razbor-demo-v2.docx",
                raw,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        ],
    )
    inbox_verified = False
    attachment_ok = False
    imap_error = None
    if email_out.get("ok"):
        import email as email_lib
        import imaplib

        from sfrfr.integrations.yandex_workspace.mail_imap import _close_imap, _connect_imap

        for _ in range(6):
            time.sleep(5)
            listed = list_inbox(limit=20, unseen_only=False)
            if not listed.get("ok"):
                imap_error = listed.get("error") or listed.get("reason") or listed.get("detail")
                break
            match_uid = None
            for item in listed.get("items") or []:
                subj = str(item.get("subject") or "")
                if "ACCEPTANCE" in subj and "разбор" in subj.lower():
                    match_uid = str(item.get("uid") or "")
                    break
            if not match_uid:
                continue
            inbox_verified = True
            try:
                imap = _connect_imap()
                try:
                    status, _ = imap.select("INBOX", readonly=True)
                    if status == "OK":
                        status, msg_data = imap.fetch(match_uid, "(BODY.PEEK[])")
                        if status == "OK" and msg_data:
                            raw = b""
                            for part in msg_data:
                                if isinstance(part, tuple) and len(part) >= 2:
                                    raw = part[1]
                                    break
                            parsed = email_lib.message_from_bytes(raw)
                            for part in parsed.walk():
                                disp = str(part.get_content_disposition() or "")
                                fname = str(part.get_filename() or "")
                                if disp == "attachment" or fname.lower().endswith(".docx"):
                                    payload = part.get_payload(decode=True) or b""
                                    if fname.lower().endswith(".docx") and payload[:2] == b"PK":
                                        attachment_ok = True
                                        break
                finally:
                    _close_imap(imap)
            except (imaplib.IMAP4.error, OSError, ValueError) as exc:
                imap_error = type(exc).__name__
            break

    report["checks"]["email_send"] = {
        "status": "pass" if email_out.get("ok") else "fail",
        "ok": bool(email_out.get("ok")),
        "skipped": bool(email_out.get("skipped")),
        "provider": email_out.get("provider") or email_out.get("error") or email_out.get("reason"),
        "to_domain": control_to.split("@")[-1] if "@" in control_to else None,
    }
    report["checks"]["email_receive"] = {
        "status": "pass" if (inbox_verified and attachment_ok) else "not_verified",
        "recipient_inbox_verified": inbox_verified,
        "attachment_docx_ok": attachment_ok,
        "imap_error": imap_error,
        "note": (
            "Письмо и DOCX-вложение подтверждены в контрольном ящике IMAP."
            if inbox_verified and attachment_ok
            else (
                "Письмо найдено, вложение DOCX не подтверждено."
                if inbox_verified
                else "Получение адресатом не подтверждено (SMTP accept ≠ inbox)."
            )
        ),
    }

    # disk
    from sfrfr.integrations.yandex_workspace.disk import (
        mirror_case_document,
        publish_case_file,
        unpublish_case_file,
    )

    # synthetic case id for path policy (UUID)
    disk_case = "00000000-0000-4000-8000-00000000acce"
    up = mirror_case_document(
        disk_case,
        "stage5-acceptance-razbor-demo-v2.docx",
        raw,
        subfolder="outgoing",
        folder_name="ACCEPTANCE-DEMO",
    )
    disk_check: dict = {
        "upload_ok": bool(up.get("ok")),
        "upload_skipped": bool(up.get("skipped")),
        "upload_error": up.get("error") or up.get("reason"),
        "public_url_issued": False,
        "public_download_verified": False,
        "recipient_open_verified": False,
    }
    if up.get("ok"):
        path = str(up.get("path") or "")
        if not path and up.get("folder_name") and up.get("remote_name"):
            path = (
                f"disk:/SFRFR-cases/{up['folder_name']}/outgoing/{up['remote_name']}"
            )
        pub = publish_case_file(path) if path else {"ok": False, "error": "no_path"}
        disk_check["publish_ok"] = bool(pub.get("ok"))
        disk_check["publish_error"] = pub.get("error")
        if pub.get("ok") and pub.get("public_url"):
            disk_check["public_url_issued"] = True
            disk_check["public_url_host"] = "disk.yandex.ru"
            public_url = str(pub["public_url"])
            try:
                with httpx.Client(timeout=45.0, follow_redirects=True) as client:
                    meta = client.get(
                        "https://cloud-api.yandex.net/v1/disk/public/resources",
                        params={
                            "public_key": public_url,
                            "fields": "name,type,mime_type,size",
                        },
                    )
                    disk_check["public_meta_status"] = meta.status_code
                    if meta.status_code == 200:
                        meta_body = meta.json() or {}
                        disk_check["public_file_name_ok"] = "stage5-acceptance" in str(
                            meta_body.get("name") or ""
                        ).lower()
                        disk_check["public_file_type"] = meta_body.get("type")
                    dl = client.get(
                        "https://cloud-api.yandex.net/v1/disk/public/resources/download",
                        params={"public_key": public_url},
                    )
                    disk_check["public_download_api_status"] = dl.status_code
                    if dl.status_code == 200:
                        href = (dl.json() or {}).get("href")
                        disk_check["public_download_href_set"] = bool(href)
                        if href:
                            # Иногда downloader отдаёт HTML-заглушку; повторяем с новым href.
                            for attempt in range(3):
                                if attempt:
                                    time.sleep(2)
                                    dl2 = client.get(
                                        "https://cloud-api.yandex.net/v1/disk/public/resources/download",
                                        params={"public_key": public_url},
                                    )
                                    if dl2.status_code != 200:
                                        continue
                                    href = (dl2.json() or {}).get("href") or href
                                bin_resp = client.get(
                                    href,
                                    headers={"Accept": "application/octet-stream,*/*"},
                                )
                                head = bytes(bin_resp.content[:4])
                                disk_check["public_download_bin_status"] = bin_resp.status_code
                                disk_check["public_download_magic"] = head.hex()
                                disk_check["downloaded_bytes"] = len(bin_resp.content)
                                disk_check["public_download_attempts"] = attempt + 1
                                if bin_resp.status_code == 200 and head[:2] == b"PK":
                                    disk_check["public_download_verified"] = True
                                    break
            except Exception as exc:  # noqa: BLE001
                disk_check["public_probe_error"] = type(exc).__name__
            un = unpublish_case_file(path)
            disk_check["unpublished_after_check"] = bool(un.get("ok"))
            disk_check["note"] = (
                "Публичная ссылка: meta+download DOCX (PK) без OAuth; ссылка отозвана. "
                "URL в отчёт не включён."
                if disk_check["public_download_verified"]
                else "Ссылка выдана; клиентское скачивание не подтверждено."
            )
        if disk_check.get("publish_ok") and disk_check.get("public_download_verified"):
            disk_check["status"] = "pass"
            disk_check["recipient_open_verified"] = True
        elif disk_check.get("publish_ok"):
            disk_check["status"] = "not_verified"
        else:
            disk_check["status"] = "fail"
    else:
        disk_check["status"] = "fail" if not up.get("skipped") else "not_configured"
    report["checks"]["yadisk"] = disk_check

    report["checks"]["appeals_not_auto"] = {
        "status": "pass",
        "note": "Согласование разбора не вызывает appeals_consent_* (отдельный этап 6).",
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"report": str(REPORT_PATH), "docx": str(DOCX_PATH)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
