# Ранбук разработчика и эксплуатации (ТЗ-05)

Связанное ТЗ: [specs/05-developer-operations.md](specs/05-developer-operations.md).

## Инструменты

| Инструмент | URL / команда |
|---|---|
| Swagger | https://api.taxi-doroga-dobra.ru/docs (без `service_role` в браузере) |
| Health | https://api.taxi-doroga-dobra.ru/health |
| MAX webhook health | https://api.taxi-doroga-dobra.ru/api/integrations/max/health |
| Ops status | `GET /ops/status` + заголовок `X-Ops-Token: $OPS_MONITOR_TOKEN` |
| Supabase | Dashboard → миграции, Auth, Storage, RLS |
| Логи API | `journalctl -u sfrfr-api -f` |
| Логи кабинетов | `journalctl -u sfrfr-cabinet -f`, `journalctl -u sfrfr-admin -f` |
| CI | `.github/workflows/ci.yml` — ruff/pytest + lint/build cabinet/admin |
| Deploy | `.github/workflows/deploy-vps.yml` — только после api+cabinet+admin |

## Правила

1. В production-логах нет ФИО, СНИЛС, текстов документов и URL с токенами — фильтр `sfrfr.ops.logging.RedactingFilter`.
2. Схема БД — только через `supabase/migrations/` (+ `apply_migration` / CLI).
3. Перед релизом кабинетов: RLS + private bucket `pension-docs`.
4. Секреты: `.env` на VPS и GitHub Secrets. В кабинетах только publishable/anon.
5. Google Sheets — только обезличенные агрегаты, не production-ПДн.
6. Google Drive — шаблоны/кейсы по `case_id`; сканы ПДн — в Supabase Storage.
7. Calendar / reCAPTCHA / Search Console — см. раздел ниже; Gmail клиентам на MVP не подключаем.

## Google (MVP) — чеклист

| Сервис | Статус | Действие |
|---|---|---|
| Sheets | код + SA | `sfrfr sheets-sync` |
| Drive | код + SA | `sfrfr drive-init-tree`, `drive-case-mkdir CASE-…` |
| Calendar | код | Расшарить календарь на `sfrpfr-google-calendar@…`, задать `GOOGLE_CALENDAR_ID`, затем `sfrfr calendar-create --case-id … --start …` |
| reCAPTCHA Enterprise | код | Site key `sfrpfr-site-key` / `RECAPTCHA_SITE_KEY`; WP: `action: 'lead'`; API verify через SA |
| Search Console | ops | Добавить `https://taxi-doroga-dobra.ru/`, выдать доступ SA `sfrpfr-google-search-console@…`, `sfrfr gsc-sites` |
| Looker Studio | ops | Новый отчёт → Google Sheets → spreadsheet Analytics (без ПДн) |
| Gmail / Meet / Forms / Docs API / Vision | отложено | — |

### WP: reCAPTCHA Enterprise (лид)

```html
<script src="https://www.google.com/recaptcha/enterprise.js?render=6Lf7UWMtAAAAANDXkb8MR9ufU8QYO9UwZsEC3NHu"></script>
```

Перед отправкой формы (action **обязательно** `lead`, не `LOGIN`):

```js
const token = await grecaptcha.enterprise.execute(
  '6Lf7UWMtAAAAANDXkb8MR9ufU8QYO9UwZsEC3NHu',
  { action: 'lead' }
);
// добавить в JSON webhook: "recaptcha_token": token
```

Бэкенд: `POST /api/public/leads` → `RecaptchaVerifier` (SA), `expectedAction=lead`, `min_score` из `RECAPTCHA_MIN_SCORE`.

В GCP включите **reCAPTCHA Enterprise API** для проекта `sfrfr-sheets`, если ещё не включена.

WP reCAPTCHA: site key на форме + поле/`recaptcha_token` в JSON webhook на `/api/public/leads`. Не слать телефоны/ФИО в GTM/Метрику.

## Мониторинг и алерты

Локально / на VPS:

```bash
# публичный health
sfrfr ops-check-remote

# health + счётчик pipeline_status=failed (exit 1 при алерте)
sfrfr ops-health --fail-on-alert

# cron-обёртка
APP_DIR=/opt/sfrfr /opt/sfrfr/scripts/ops_check.sh
```

Windows:

```powershell
.\scripts\ops_check.ps1
.\scripts\ops_check.ps1 -Url https://api.taxi-doroga-dobra.ru
```

Порог алертов: `OPS_FAILED_ALERT_THRESHOLD` (по умолчанию 1).  
Токен ops API: `OPS_MONITOR_TOKEN`.

Рекомендуемый cron (каждые 5 минут) + уведомление (email/MAX) при ненулевом exit code скрипта.

## Smoke после деплоя

```bash
curl -fsS https://api.taxi-doroga-dobra.ru/health
curl -fsS https://api.taxi-doroga-dobra.ru/api/integrations/max/health
curl -fsS -o /dev/null -w "%{http_code}\n" https://api.taxi-doroga-dobra.ru/docs
```

Ожидание: HTTP 200, JSON без ПДн, `/docs` открывается без ключа.
