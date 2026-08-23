# Яндекс Трекер STAZH: контроль качества и улучшений (MVP)

**Дата:** 2026-08-23  
**Очередь:** `STAZH` — https://tracker.yandex.ru/STAZH  
**Цель:** внутренние задачи качества/продукта без ПДн; клиентские дела остаются в admin.

## Что делает MVP

1. В карточке дела admin → ⋮ → **«Создать задачу в Tracker»**.
2. Backend создаёт задачу в очереди **STAZH** через Tracker API (токен только на сервере).
3. В описании — обезличенные поля + `case_ref` = `sha256(case_id + secret)[:12]`.
4. Ключ `STAZH-…` сохраняется в `case_tracker_issues` и `cases.tracker_last_issue_key`.
5. Защита от дублей: открытая задача того же `issue_type` + `case_ref`.
6. Санитар: phone / email / СНИЛС / UUID / cabinet URL → 400.
7. Health: `GET /api/portal/admin/tracker/health` (только admin).

Плагин UI Трекера: `plugins/tracker/sfrfr-issue-wizard` (очередь STAZH + теги `type:*`).

## Env (VPS `/opt/sfrfr/.env` или secrets)

```env
TRACKER_ENABLED=true
TRACKER_TOKEN=...                 # или YANDEX_TRACKER_OAUTH_TOKEN
TRACKER_ORG_ID=...                # или YANDEX_TRACKER_ORG_ID / TRACKER_CLOUD_ORG_ID
TRACKER_QUEUE=STAZH
TRACKER_CASE_REF_SECRET=длинная-случайная-строка
```

Не коммитить токены. Не отдавать токен во frontend.

Локально для скриптов очередей по-прежнему можно использовать `secrets/yandex-tracker.env`.

## Создание очереди

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/create_yandex_tracker_queues.py
```

Создаёт `STAZH`, `PUB`, `FUNNEL` при отсутствии.

## Миграция

`supabase/migrations/20260823150000_case_tracker_issues.sql` → таблица `case_tracker_issues`.

## API

| Метод | Путь | Кто |
|-------|------|-----|
| POST | `/api/portal/admin/cases/{id}/tracker` | staff |
| GET | `/api/portal/admin/cases/{id}/tracker-issues` | staff |
| GET | `/api/portal/admin/tracker/health` | admin |

## Запрещено в Tracker

ФИО, телефон, email, СНИЛС, файлы, OCR/ИЛС, переписка, ссылки `cabinet.` / `admin.` на дело клиента.

## Не в MVP (следующий этап)

- Автосоздание SLA / ошибок интеграций / гипотез по порогу.
- Кастомные типы и статусы Трекера (сейчас `task` + теги `type:*`).
- Отдельные очереди STAZH-OPS / STAZH-DEV / STAZH-CONTENT.

## Rollback

1. `TRACKER_ENABLED=false` на VPS + restart API.  
2. Кнопку UI можно оставить — вернёт 503.  
3. Таблицу не удалять без бэкапа связей.
