# ТЗ: интерфейс разработчика и эксплуатация

## Инструменты

- Swagger FastAPI: `https://api.домен/docs`.
- Supabase Dashboard: миграции, Auth, Storage, RLS.
- Логи VPS: `journalctl -u sfrfr-api`.
- Healthcheck: `https://api.домен/health`.
- GitHub Actions: CI и deploy на VPS.

## Правила эксплуатации

- В production-логах не фиксировать ФИО, СНИЛС, тексты документов и ссылки с токенами.
- Разработчик не выгружает production-ПДн в Google Sheets.
- Изменения схемы БД выполняются миграциями.
- Проверка RLS и private Storage обязательна до релиза кабинетов.
- Секреты находятся только в `.env` на VPS или защищённом хранилище секретов CI.

## Мониторинг

- Проверять `/health` и доступность webhook MAX по HTTPS.
- Отслеживать ошибки OCR, LLM, Storage и webhook.
- Настроить уведомление при недоступности API и при накоплении дел в `failed`.

## Критерии приёмки

- Swagger не требует служебного ключа в браузере.
- Healthcheck возвращает успешный статус без ПДн.
- CI запускает тесты и линтер до deploy.
