# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(".").resolve()
ip = root / "src/sfrfr/integrations/max/intake.py"
it = ip.read_text(encoding="utf-8")
it = it.replace("примем, специалист увидит.", "загрузите в кабинет на сайте.")
it = it.replace("примем.", "загрузите в кабинет на сайте.")
it = it.replace("Предпочтительно загружайте", "Загружайте")
it = it.replace("предпочтительно — в личный", "только в личный")
it = it.replace("Предпочтительно — личный", "Только личный")
it = it.replace("предпочтительно загрузите", "загрузите")
it = it.replace("Документы предпочтительно — в личный кабинет на сайте; ", "Документы — только в личный кабинет на сайте. ")
it = it.replace("если пришлёте файл сюда — загрузите в кабинет на сайте.", "не присылайте файл в этот чат.")
it = it.replace("Если пришлёте файл сюда в чат — загрузите в кабинет на сайте.", "Не присылайте файл в этот чат — только кабинет на сайте.")
it = it.replace("Если отправите файл сюда в чат — загрузите в кабинет на сайте. ", "")
it = it.replace("Если пришлёте сюда в чат — загрузите в кабинет на сайте.", "Не присылайте файлы в этот чат.")
it = it.replace("если пришлёте сюда — загрузите в кабинет на сайте.", "не в этот чат.")
ip.write_text(it, encoding="utf-8")
print("intake примем", "примем" in it)

hp = root / "src/sfrfr/integrations/max/handler.py"
ht = hp.read_text(encoding="utf-8")
ht = ht.replace("UPLOAD_ACCEPTED_TEXT,", "UPLOAD_BLOCKED_TEXT,")
ht = ht.replace(
    "вложения — принимаем + CTA кабинета на сайте (предпочтительно)",
    "вложения в production — отказ + CTA кабинета на сайте",
)
ht = re.sub(
    r"\ndef _notify_staff_chat_docs\(.*?\n\ndef _handle_operator\(",
    "\n\ndef _handle_operator(",
    ht,
    count=1,
    flags=re.S,
)
marker_run = '    if lower.startswith("/run"):'
marker_free = "    # Свободный текст: DeepSeek (Yandex AI Studio)"
start = ht.find(marker_run)
end = ht.find(marker_free)
print("spans", start, end)
assert start != -1 and end != -1
new_block = '''    if lower.startswith("/run"):
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

'''
ht = ht[:start] + new_block + ht[end:]
hp.write_text(ht, encoding="utf-8")
print("handler", "UPLOAD_ACCEPTED" in ht, "_notify_staff" in ht, "is_production and" in ht)

# llm sanitize
lp = root / "src/sfrfr/integrations/max/llm_chat.py"
lt = lp.read_text(encoding="utf-8")
for a, b in [
    ("предпочтительно", "только"),
    ("если уже прислали сюда — приняли", "сканы в чат не принимать"),
    ("если пришлют файл сюда — примем, специалист увидит", "без вложений в чат"),
    ("Не пиши жёстко «в чат нельзя» — канон: только кабинет; если сюда — приняли.",
     "Сканы в чат не принимать — только кабинет на сайте."),
    ("(если прислали сюда — приняли)", ""),
    ("Если пришлёте файл сюда — примем, специалист увидит. ", ""),
    ("Документы только загрузите в личный кабинет на сайте — так защищённее. ",
     "Загрузите документы в личный кабинет на сайте. "),
]:
    lt = lt.replace(a, b)
lp.write_text(lt, encoding="utf-8")
print("llm примем", "примем" in lt)

# test
tp = root / "tests/unit/test_max_intake.py"
tt = tp.read_text(encoding="utf-8")
if "test_upload_accepted_in_production" in tt:
    tt2 = tt
    tt2 = tt2.replace("test_upload_accepted_in_production", "test_upload_blocked_in_production")
    tt2 = tt2.replace(
        '    monkeypatch.setattr(\n        "sfrfr.integrations.max.handler._notify_staff_chat_docs",\n        lambda **_k: None,\n    )\n',
        '    monkeypatch.setenv("CABINET_PUBLIC_URL", "https://cabinet.proverkastaza.ru")\n',
    )
    tt2 = tt2.replace("accepted = handle_max_update", "blocked = handle_max_update")
    tt2 = tt2.replace('accepted.action == "upload"', 'blocked.action == "upload_blocked"')
    tt2 = tt2.replace("accepted.ok is True", "blocked.ok is False")
    tt2 = tt2.replace(
        'assert "приняли" in (accepted.reply or "").lower() or "принят" in (accepted.reply or "").lower()\n    assert "кабинет" in (accepted.reply or "").lower()\n    assert bot.attachments[-1]',
        'assert "не принимаются" in (blocked.reply or "").lower()\n    assert "сайте" in (blocked.reply or "").lower()\n    blob = str(bot.attachments[-1])\n    assert "Кабинет на сайте" in blob',
    )
    tp.write_text(tt2, encoding="utf-8")
    print("test updated")
else:
    print("test name:", "upload_blocked" in tt)

print("OK")
