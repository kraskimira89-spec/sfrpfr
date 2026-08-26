# -*- coding: utf-8 -*-
"""Force website-only cabinet + reject MAX chat uploads (prod)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------- intake.py ----------
intake_path = ROOT / "src/sfrfr/integrations/max/intake.py"
it = intake_path.read_text(encoding="utf-8")

# Replace welcome docs sentences
it = it.replace(
    "Документы предпочтительно загружайте в личный кабинет на сайте — так защищённее. "
    "Если пришлёте файл сюда в чат — примем, специалист увидит.\n\n",
    "В этом чате MAX — подсказки и связь. "
    "Документы загружайте только в личный кабинет на сайте.\n\n",
)
it = it.replace(
    "Документы предпочтительно — в личный кабинет на сайте; "
    "если пришлёте файл сюда — примем, специалист увидит.",
    "В этом чате MAX — подсказки и связь. "
    "Сканы и трудовую книжку загружайте только в личный кабинет на сайте.",
)
it = re.sub(
    r'SUMMARY_TEXT = \(\n.*?^\)\n',
    '''SUMMARY_TEXT = (
    "Поняли. Для начала нужно загрузить доступные документы и сверить их с данными ИЛС. "
    "Документы загружайте в личный кабинет на сайте — там они передаются защищённо. "
    "Это займёт 2–3 минуты. Перед загрузкой потребуется согласие на обработку данных. "
    f"В этом чате MAX — подсказки и связь; кабинет — только на сайте. {POSITION_SHORT}"
)

''',
    it,
    count=1,
    flags=re.M | re.S,
)
it = it.replace(
    "Предпочтительно загружайте файлы в личный кабинет на сайте — так защищённее. "
    "Если пришлёте сюда в чат — примем, специалист увидит.\n\n",
    "Файлы загружайте только в личный кабинет на сайте, не в этот чат.\n\n",
)
it = it.replace(
    "Готовые файлы предпочтительно — в личный кабинет на сайте; "
    "если пришлёте сюда — примем.",
    "Готовые файлы — в личный кабинет на сайте, не в этот чат.",
)
it = it.replace(
    "Файл предпочтительно загрузите в личный кабинет на сайте; "
    "если пришлёте сюда — примем.\n\n",
    "Файл загрузите в личный кабинет на сайте — не присылайте в этот чат.\n\n",
)
it = it.replace(
    "Файл предпочтительно — в личный кабинет на сайте; если пришлёте сюда — примем.",
    "Файл загрузите только в личный кабинет на сайте.",
)
it = re.sub(
    r"# Канон: предпочтительно кабинет на сайте; вложение в чате — принимаем\.\n"
    r"UPLOAD_ACCEPTED_TEXT = \(\n.*?\)\n"
    r"# Устар\. имя:.*\n"
    r"UPLOAD_BLOCKED_TEXT = UPLOAD_ACCEPTED_TEXT\n",
    '''UPLOAD_BLOCKED_TEXT = (
    "Документы через сообщения MAX не принимаются. "
    "Загрузите их в личный кабинет на сайте — после согласия на обработку данных. "
    f"В этом чате — подсказки и связь. {POSITION_SHORT}"
)

''',
    it,
    count=1,
    flags=re.M | re.S,
)
intake_path.write_text(it, encoding="utf-8")
assert "UPLOAD_ACCEPTED_TEXT" not in it
assert "примем" not in it
print("intake ok")

# ---------- handler.py ----------
hp = ROOT / "src/sfrfr/integrations/max/handler.py"
ht = hp.read_text(encoding="utf-8")
ht = ht.replace("UPLOAD_ACCEPTED_TEXT,", "UPLOAD_BLOCKED_TEXT,")
ht = ht.replace(
    "вложения — принимаем + CTA кабинета на сайте (предпочтительно)",
    "вложения в production — отказ + CTA кабинета на сайте",
)
# Remove notify helper if present
ht = re.sub(
    r"\ndef _notify_staff_chat_docs\(.*?\n\ndef _handle_operator\(",
    "\n\ndef _handle_operator(",
    ht,
    count=1,
    flags=re.S,
)
old_upload = '''    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = (
                "Сначала загрузите документ в кабинет на сайте "
                "или пришлите файл сюда в чат."
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=False,
                action="run_blocked",
                case_id=record.case_id,
                reply=reply,
            )
        updated = store.run_until(record.case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        draft_note = " Откройте /draft." if updated.ctx.draft else ""
        reply = f"Готово: {status_label_ru(updated.ctx.status)}.{draft_note}"
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="run", case_id=record.case_id, reply=reply)

    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    downloads = extract_downloadable_files(update)
    max_files = _collect_max_files(update)
    receipt_handled = _try_max_payment_receipt(
        bot, user_id=user_id, chat_id=chat_id, files=max_files
    )
    if receipt_handled is not None:
        return receipt_handled
    # Канон: предпочтительно кабинет на сайте; вложение в чате — принимаем.
    if max_files or isinstance(file_bytes, (bytes, bytearray)) or bool(downloads):
        fresh = record
        names: list[str] = []
        if max_files:
            for name, data in max_files:
                fresh = _ingest_bytes(store, fresh, name, data)
                names.append(name)
        elif isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
            fresh = _ingest_bytes(store, record, file_name, bytes(file_bytes))
            names.append(file_name)
        else:
            for name, url in downloads:
                try:
                    data = download_file(url)
                    fresh = _ingest_bytes(store, fresh, name, data)
                    names.append(name)
                except Exception:
                    continue
        if names:
            case_id = fresh.case_id
            _notify_staff_chat_docs(user_id=user_id, case_id=case_id, filenames=names)
            cabinet_url = cabinet_url_for_case(case_id)
            reply = (
                f"{UPLOAD_ACCEPTED_TEXT}\\n"
                f"В деле файлов: {len(fresh.ctx.document_paths)}."
            )
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=reply,
                attachments=upload_blocked_keyboard(cabinet_url=cabinet_url),
                case_id=case_id,
            )
            return MaxHandleResult(
                ok=True,
                action="upload",
                case_id=case_id,
                reply=reply,
            )

    # Свободный текст: DeepSeek (Yandex AI Studio) + кнопки шага / fallback nudge (ТЗ-26).
'''
new_upload = '''    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = "Сначала загрузите документ в личный кабинет на сайте."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=False,
                action="run_blocked",
                case_id=record.case_id,
                reply=reply,
            )
        updated = store.run_until(record.case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        draft_note = " Откройте /draft." if updated.ctx.draft else ""
        reply = f"Готово: {status_label_ru(updated.ctx.status)}.{draft_note}"
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="run", case_id=record.case_id, reply=reply)

    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    downloads = extract_downloadable_files(update)
    is_production = get_settings().app_env.strip().lower() == "production"
    max_files = _collect_max_files(update)
    receipt_handled = _try_max_payment_receipt(
        bot, user_id=user_id, chat_id=chat_id, files=max_files
    )
    if receipt_handled is not None:
        return receipt_handled
    if is_production and (
        max_files
        or isinstance(file_bytes, (bytes, bytearray))
        or bool(downloads)
    ):
        case_id = record.case_id
        attempt_names: list[str] = []
        if isinstance(file_name, str):
            attempt_names.append(file_name)
        attempt_names.extend(name for name, _data in max_files)
        attempt_names.extend(name for name, _url in downloads)
        label = attempt_names[0] if attempt_names else "файл"
        _append_client_case_message(
            case_id=case_id or _case_id_for_max_user(user_id),
            max_user_id=user_id,
            text=f"[Документ] попытка отправить в чат: {label}",
        )
        cabinet_url = cabinet_url_for_case(case_id)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=UPLOAD_BLOCKED_TEXT,
            attachments=upload_blocked_keyboard(cabinet_url=cabinet_url),
            case_id=case_id,
        )
        return MaxHandleResult(
            ok=False,
            action="upload_blocked",
            case_id=case_id,
            reply=UPLOAD_BLOCKED_TEXT,
        )
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        fresh = _ingest_bytes(store, record, file_name, bytes(file_bytes))
        reply = f"Файл принят ({len(fresh.ctx.document_paths)}). Пришлите ещё или /run."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="upload", case_id=record.case_id, reply=reply)

    if downloads:
        names: list[str] = []
        fresh = record
        for name, url in downloads:
            try:
                data = download_file(url)
                fresh = _ingest_bytes(store, fresh, name, data)
                names.append(name)
            except Exception:
                continue
        if names:
            reply = f"Файлы приняты ({len(fresh.ctx.document_paths)}). Пришлите ещё или /run."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=True, action="upload_url", case_id=record.case_id, reply=reply
            )

    # Свободный текст: DeepSeek (Yandex AI Studio) + кнопки шага / fallback nudge (ТЗ-26).
'''
if old_upload not in ht:
    raise SystemExit("handler upload block not found")
ht = ht.replace(old_upload, new_upload)
assert "_notify_staff_chat_docs" not in ht
assert "UPLOAD_ACCEPTED_TEXT" not in ht
hp.write_text(ht, encoding="utf-8")
print("handler ok")

# ---------- llm_chat.py (run previous rewriter) ----------
print("run llm rewriter separately if needed")
print("ALL_DONE")
