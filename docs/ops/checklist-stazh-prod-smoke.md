# Prod smoke: STAZH-1 (кабинет → Tracker)

**Задача:** [STAZH-1](https://tracker.yandex.ru/STAZH-1)  
**Дата:** 2026-09-01

## Предусловия

- [ ] Deploy `deploy-vps` completed success
- [ ] Миграция `20260823150000_case_tracker_issues.sql` на prod (см. `scripts/verify_prod_migrations_tz27_31.py`)
- [ ] Env на VPS (`/opt/sfrfr/.env`):

```env
TRACKER_ENABLED=true
TRACKER_TOKEN=...
TRACKER_ORG_ID=...
TRACKER_QUEUE=STAZH
TRACKER_CASE_REF_SECRET=...
```

## Smoke (без ПДн)

1. **Health API** (admin JWT):

```http
GET /api/portal/admin/tracker/health
```

Ожидание: `{"ok": true, "queue": "STAZH", ...}`

2. **Создать задачу из дела** (тестовое дело, staff):

- Admin → карточка дела → ⋮ → «Создать задачу в Tracker»
- Тип: `quality` / `bug` (без ФИО, телефона, СНИЛС, ссылок cabinet)
- Ожидание: ключ `STAZH-N`, запись в `case_tracker_issues`

3. **Проверить связь case ↔ issue**

```http
GET /api/portal/admin/cases/{case_id}/tracker-issues
```

Ожидание: список с `issue_key`, `case_ref` (12 символов hash)

4. **Дубликат** — повтор с тем же `issue_type` + `case_ref` → 409 или существующий ключ

5. **Санитар** — текст с телефоном/email → 400

## После smoke

- Комментарий в STAZH-1: дата, `STAZH-N`, health OK
- Закрыть STAZH-1 resolution «Решен»

## Rollback

`TRACKER_ENABLED=false` + restart API — кнопка вернёт 503, таблицу не удалять.
