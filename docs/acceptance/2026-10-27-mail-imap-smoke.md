# Smoke почты / IMAP (2026-10-27)

| Проверка | Итог |
|---|---|
| Timer `sfrfr-mail-inbound-docs.timer` | active |
| Ручной poll | `{"ok": true, "processed": 0, "detail": "empty_inbox"}` |
| Последние journal | success empty_inbox (ранее был 1× `imap_error` CAPABILITY — восстановился) |
| Браузер mail.yandex | вкладки открыты; полный inbound с вложением сегодня не гоняли (приёмка #342/#343 уже закрыта) |

Новый end-to-end inbound не требовался; health IMAP OK.
