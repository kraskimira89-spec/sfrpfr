# Чеклист готовности MVP (ТЗ-07)

Критерий: ПДн только через API, авторизованные кабинеты, private Storage и минимальные интеграции.

| Этап | Статус | Как проверить |
|---|---|---|
| 1. Публичный вход | ✅ | WP: оферта/ПДн/согласие; CTA `/#kak-rabotat`; форма без СНИЛС/файлов; `POST /api/public/leads` → case + Taganay |
| 2. Кабинет эксперта | ✅ | `apps/admin`: реестр, карточка, OCR/findings, чек-лист, черновик |
| 3. Кабинет клиента + каналы | ✅ | OTP, дела, upload, чек-лист; MAX `/docs` `/draft`; выбор канала на витрине |
| 4. Оплаты | ✅ | Admin orders (manual); ЮKassa pay+webhook; кнопка «Оплатить» с fallback |
| 5. Результат + post-payment | ✅ | Upload решения СФР; confirm result; `calc_success_fee`; SF_* после окна 60+ дней |
| 6. CRM и аналитика | ✅ | Taganay sync; Sheets whitelist без ПДн |

## Операционный запуск этапа 1

1. В `.env` API: `PUBLIC_LEAD_TOKEN=…`, `TAGANAY_WEBHOOK_URL=…`
2. На VPS WP: `SFRFR_PUBLIC_LEAD_URL=https://api…/api/public/leads`, `SFRFR_PUBLIC_LEAD_TOKEN=…`
3. Пересидить меню: `bash scripts/wp_seed_site_tz02.sh` (CTA → выбор канала)
4. Обновить форму: `wp eval-file scripts/wp_ensure_lead_form.php`
