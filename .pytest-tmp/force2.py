# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(".").resolve()

# --- intake: strip accept-in-chat phrases ---
ip = root / "src/sfrfr/integrations/max/intake.py"
it = ip.read_text(encoding="utf-8")
subs = [
    (
        "Документы предпочтительно загружайте в личный кабинет на сайте — так защищённее. "
        "Если пришлёте файл сюда в чат — примем, специалист увидит.\n\n",
        "В этом чате MAX — подсказки и связь. "
        "Документы загружайте только в личный кабинет на сайте.\n\n",
    ),
    (
        "Документы предпочтительно — в личный кабинет на сайте; "
        "если пришлёте файл сюда — примем, специалист увидит.",
        "В этом чате MAX — подсказки и связь. "
        "Сканы и трудовую книжку загружайте только в личный кабинет на сайте.",
    ),
    (
        "Если пришлёте файл сюда в чат — примем, специалист увидит.\n\n",
        "Документы загружайте только в личный кабинет на сайте.\n\n",
    ),
    (
        "если пришлёте файл сюда — примем, специалист увидит.",
        "документы — только в личный кабинет на сайте.",
    ),
    (
        "Если пришлёте сюда в чат — примем, специалист увидит.\n\n",
        "Файлы загружайте только в личный кабинет на сайте, не в этот чат.\n\n",
    ),
    (
        "если пришлёте сюда — примем.",
        "не в этот чат.",
    ),
    (
        "если пришлёте сюда — примем.\n\n",
        "не присылайте в этот чат.\n\n",
    ),
]
for a, b in subs:
    it = it.replace(a, b)
# summary cleanup
it = it.replace(
    "Если отправите файл сюда в чат — примем, специалист увидит. ",
    "",
)
it = it.replace("Предпочтительно — личный кабинет на сайте: там файлы передаются защищённо "
                "(после согласия на обработку данных), это займёт 2–3 минуты. ",
                "Документы загружайте в личный кабинет на сайте — там они передаются защищённо. "
                "Это займёт 2–3 минуты. Перед загрузкой потребуется согласие на обработку данных. ")
it = it.replace("Кабинет клиента — только на сайте. ",
                "В этом чате MAX — подсказки и связь; кабинет — только на сайте. ")
assert "примем" not in it, [line for line in it.splitlines() if "примем" in line]
ip.write_text(it, encoding="utf-8")
print("intake fixed")

# --- handler ---
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

start = ht.find('    if lower.startswith("/run"):')
end = ht.find("    # Свободный текст: DeepSeek (Yandex AI Studio)")
assert start != -1 and end != -1 and end > start
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
assert "UPLOAD_ACCEPTED_TEXT" not in ht
assert "_notify_staff_chat_docs" not in ht
assert "is_production and" in ht
hp.write_text(ht, encoding="utf-8")
print("handler fixed")

# --- llm_chat quick sanitize ---
lp = root / "src/sfrfr/integrations/max/llm_chat.py"
lt = lp.read_text(encoding="utf-8")
lt = lt.replace(
    "- Документы предпочтительно — в кабинет на сайте (после согласия): так защищённее.\n"
    "- Если клиент уже прислал файл сюда в чат — не отказывай: «приняли, специалист увидит»;\n"
    "  мягко напомни про кабинет на сайте для следующих файлов.\n"
    "- Оплата и согласие — через кабинет на сайте (кнопка «Кабинет на сайте»).\n",
    "- Документы, оплата, согласие — через кабинет на сайте (кнопка «Кабинет на сайте»).\n"
    "- Сканы и файлы в чат MAX не принимать — только кабинет на сайте.\n",
)
lt = lt.replace(
    "- Файлы: предпочтительно кабинет на сайте; если уже прислали сюда — приняли.\n",
    "- Вне компетенции / разбор дела / ПДн / файлы — мягко к специалисту или в кабинет на сайте;\n"
    "  сканы в чат не принимать.\n",
)
lt = lt.replace(
    "Как передать сервису: предпочтительно личный кабинет сайта после согласия;\n"
    "в MAX можно написать «ИЛС получил(а)» / «файл в кабинете»;\n"
    "если пришлют файл сюда — примем, специалист увидит.\n",
    "Как передать сервису: только личный кабинет сайта после согласия;\n"
    "в MAX писать «ИЛС получил(а)» / «файл в кабинете на сайте» — без вложений.\n",
)
lt = lt.replace(
    "Нельзя: «сделаем Госуслуги за вас», пароль/код СМС.\n"
    "Не пиши жёстко «в чат нельзя» — канон: предпочтительно кабинет; если сюда — приняли.\n",
    "Нельзя: «сделаем Госуслуги за вас», пароль/код СМС, файл «на минутку» в чат.\n",
)
lt = lt.replace(
    "- не проси писать СНИЛС/паспорт цифрами в чат; файлы — предпочтительно кабинет на сайте\n"
    "  (если прислали сюда — приняли);\n",
    "- не проси СНИЛС, паспорт, сканы / ИЛС в чат — только кабинет на сайте;\n",
)
lt = lt.replace(
    '            "Лучше не писать СНИЛС и паспорт цифрами в чат. "\n'
    '            "Документы предпочтительно загрузите в личный кабинет на сайте — так защищённее. "\n'
    '            "Если пришлёте файл сюда — примем, специалист увидит. "\n'
    '            "Или позовите специалиста кнопкой ниже.\\n\\n"\n',
    '            "Пожалуйста, не присылайте СНИЛС, паспорт и сканы в чат. "\n'
    '            "Загрузите документы в личный кабинет на сайте "\n'
    '            "или позовите специалиста кнопкой ниже.\\n\\n"\n',
)
lp.write_text(lt, encoding="utf-8")
print("llm fixed, accept leftover:", "примем" in lt or "принят" in lt.lower() and "если" in lt)

# --- test ---
tp = root / "tests/unit/test_max_intake.py"
tt = tp.read_text(encoding="utf-8")
if "test_upload_accepted_in_production" in tt:
    tt = tt.replace("test_upload_accepted_in_production", "test_upload_blocked_in_production")
    tt = tt.replace(
        'monkeypatch.setattr(\n'
        '        "sfrfr.integrations.max.handler._notify_staff_chat_docs",\n'
        "        lambda **_k: None,\n"
        "    )\n\n",
        'monkeypatch.setenv("CABINET_PUBLIC_URL", "https://cabinet.proverkastaza.ru")\n',
    )
    tt = tt.replace("accepted = handle_max_update", "blocked = handle_max_update")
    tt = tt.replace("accepted.action == \"upload\"", "blocked.action == \"upload_blocked\"")
    tt = tt.replace("accepted.ok is True", "blocked.ok is False")
    tt = tt.replace(
        'assert "приняли" in (accepted.reply or "").lower() or "принят" in (accepted.reply or "").lower()\n'
        '    assert "кабинет" in (accepted.reply or "").lower()\n'
        "    assert bot.attachments[-1]",
        'assert "не принимаются" in (blocked.reply or "").lower()\n'
        '    assert "сайте" in (blocked.reply or "").lower()\n'
        '    blob = str(bot.attachments[-1])\n'
        '    assert "Кабинет на сайте" in blob\n'
        '    assert "cabinet.proverkastaza.ru" in blob',
    )
    tp.write_text(tt, encoding="utf-8")
    print("test fixed")
else:
    print("test already ok or different")

print("DONE")
