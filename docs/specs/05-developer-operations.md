# ТЗ: интерфейс разработчика и эксплуатация

Ранбук: [../ops-runbook.md](../ops-runbook.md).

## Инструменты

- Swagger FastAPI: `https://api.домен/docs`.
- Supabase Dashboard: миграции, Auth, Storage, RLS.
- Логи VPS: `journalctl -u sfrfr-api` (+ `sfrfr-cabinet`, `sfrfr-admin`).
- Healthcheck: `https://api.домен/health`.
- Ops: `GET /ops/status` (`X-Ops-Token`), CLI `sfrfr ops-health` / `scripts/ops_check.sh`.
- GitHub Actions: CI (API + Next.js cabinet/admin) и deploy API на VPS **после** успешного CI.

## Правила эксплуатации

- В production-логах не фиксировать ФИО, СНИЛС, тексты документов и ссылки с токенами.
- Разработчик не выгружает production-ПДн в Google Sheets.
- Изменения схемы БД выполняются миграциями.
- Проверка RLS и private Storage обязательна до релиза кабинетов.
- Секреты находятся только в `.env` на VPS или защищённом хранилище секретов CI.
- Браузерные кабинеты используют только publishable/anon ключ; `service_role` — только FastAPI.

## Мониторинг

- Проверять `/health` и доступность webhook MAX по HTTPS.
- Отслеживать ошибки OCR, LLM, Storage и webhook.
- Уведомление при недоступности API и при накоплении дел в `failed` (`ops-health` / cron).

## Критерии приёмки

- Swagger не требует служебного ключа в браузере.
- Healthcheck возвращает успешный статус без ПДн.
- CI запускает тесты API и lint/build кабинетов до deploy.
