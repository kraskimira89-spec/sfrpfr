# Ранбук разработчика и эксплуатации (ТЗ-05)

Связанное ТЗ: [specs/05-developer-operations.md](specs/05-developer-operations.md).

## Инструменты

| Инструмент | URL / команда |
|---|---|
| Swagger | https://api.proverkastaza.ru/docs (без `service_role` в браузере) |
| Health | https://api.proverkastaza.ru/health |
| MAX webhook health | https://api.proverkastaza.ru/api/integrations/max/health |
| Ops status | `GET /ops/status` + заголовок `X-Ops-Token: $OPS_MONITOR_TOKEN` |
| Supabase | Dashboard → миграции, Auth, Storage, RLS |
| Логи API | `journalctl -u sfrfr-api -f` |
| Логи кабинетов | `journalctl -u sfrfr-cabinet -f`, `journalctl -u sfrfr-admin -f` |
| CI | `.github/workflows/ci.yml` — ruff/pytest + lint/build cabinet/admin |
| Deploy | `.github/workflows/deploy-vps.yml` — только после api+cabinet+admin |
| QA ТЗ-09 D | [qa/tz09-stage-d.md](qa/tz09-stage-d.md) |
| QA лид→Taganay | [qa/lead-taganay-e2e.md](qa/lead-taganay-e2e.md) |
| Блог UI §13 | [ops-blog-editor.md](ops-blog-editor.md) + `scripts/wp_deploy_blog_ui.sh` |

## Правила

1. В production-логах нет ФИО, СНИЛС, текстов документов и URL с токенами — фильтр `sfrfr.ops.logging.RedactingFilter`.
2. Схема БД — только через `supabase/migrations/` (+ `apply_migration` / CLI).
3. Перед релизом кабинетов: RLS + private bucket `pension-docs`.
4. Секреты: `.env` на VPS и GitHub Secrets. В кабинетах только publishable/anon.
5. Google Sheets — только обезличенные агрегаты, не production-ПДн.
6. Google Drive — шаблоны/кейсы по `case_id`; сканы ПДн — в Supabase Storage.
7. Calendar / reCAPTCHA / Search Console — см. раздел ниже; Gmail клиентам на MVP не подключаем.
8. dbt запускается отдельно от API и деплоя: роль `analytics_transformer` читает только `analytics_source`, пишет только `analytics`.

## dbt-аналитика

Подробная настройка: [dbt-analytics.md](dbt-analytics.md).

```bash
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
```

Используйте `sfrfr-dbt.timer` от `sfrfr` (ежедневно в 05:30 МСК) с direct PostgreSQL
endpoint после включения IPv4 add-on. Не добавляйте этот запуск в `vps_deploy.sh`.

## Google (MVP) — чеклист

| Сервис | Статус | Действие |
|---|---|---|
| Sheets | код + SA | `sfrfr sheets-sync` |
| Drive | код + SA | `sfrfr drive-init-tree`, `drive-case-mkdir CASE-…` |
| Calendar | код | Расшарить календарь на `sfrpfr-google-calendar@…`, задать `GOOGLE_CALENDAR_ID`, затем `sfrfr calendar-create --case-id … --start …` |
| reCAPTCHA Enterprise | код + GCP domains | Site key `sfrpfr-site-key` / `RECAPTCHA_SITE_KEY`; WP: `action: 'lead'`; API verify через SA; после смены домена — domains в GCP (`docs/ops/cutover-manual-checklist.md`, скрипт `scripts/ops_patch_recaptcha_domains.py` — нужен IAM `keys.get/update`) |
| Search Console | ops | Добавить `https://proverkastaza.ru/`, выдать доступ SA `sfrpfr-google-search-console@…`, `sfrfr gsc-sites` |
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
.\scripts\ops_check.ps1 -Url https://api.proverkastaza.ru
```

Порог алертов: `OPS_FAILED_ALERT_THRESHOLD` (по умолчанию 1).  
Токен ops API: `OPS_MONITOR_TOKEN`.

Рекомендуемый cron (каждые 5 минут) + уведомление (email/MAX) при ненулевом exit code скрипта.

## Smoke после деплоя

```bash
curl -fsS https://api.proverkastaza.ru/health
curl -fsS https://api.proverkastaza.ru/api/integrations/max/health
curl -fsS -o /dev/null -w "%{http_code}\n" https://api.proverkastaza.ru/docs
```

Ожидание: HTTP 200, JSON без ПДн, `/docs` открывается без ключа.
