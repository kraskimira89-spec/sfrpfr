# Prod smoke: STAZH-1 (кабинет → Tracker)

**Задача:** [STAZH-1](https://tracker.yandex.ru/STAZH-1) — **закрыта 2026-09-02** (resolution fixed)  
**Smoke issue:** [STAZH-4](https://tracker.yandex.ru/STAZH-4) (`case_ref=636685c28d33`)

## Предусловия

- [x] Deploy `deploy-vps` completed success
- [x] Миграция `20260823150000_case_tracker_issues.sql` на prod (+ RLS `20260902170000`)
- [x] Env на VPS (`/opt/sfrfr/.env`):

```env
TRACKER_ENABLED=true
TRACKER_TOKEN=...
TRACKER_ORG_ID=...
TRACKER_QUEUE=STAZH
TRACKER_CASE_REF_SECRET=...
```

## Smoke (без ПДн) — 2026-09-02

1. **Health API** (admin JWT): `{"ok": true, "queue": "STAZH", "status_code": 200}`
2. **Создана задача** `process_improvement` → **STAZH-4**, запись в `case_tracker_issues`
3. Связь case ↔ issue: `case_ref` 12 символов hash OK

## Rollback

`TRACKER_ENABLED=false` + restart API — кнопка вернёт 503, таблицу не удалять.
