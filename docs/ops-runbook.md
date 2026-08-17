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
| QA лид→amoCRM | [qa/lead-amocrm-e2e.md](qa/lead-amocrm-e2e.md) |
| Яндекс Workspace OAuth | [ops/yandex-workspace-setup.md](ops/yandex-workspace-setup.md) (ТЗ-14) |
| Блог UI §13 | [ops-blog-editor.md](ops-blog-editor.md) + `scripts/wp_deploy_blog_ui.sh` |

## Правила

1. В production-логах нет ФИО, СНИЛС, текстов документов и URL с токенами — фильтр `sfrfr.ops.logging.RedactingFilter`.
2. Схема БД — только через `supabase/migrations/` (+ `apply_migration` / CLI).
3. Перед релизом кабинетов: RLS + private bucket `pension-docs`.
4. Секреты: `.env` на VPS и GitHub Secrets. В кабинетах только publishable/anon.
5. Управленческий контур: dbt → DataLens; runtime Google Sheets отключён 3 августа 2026 года.
6. Документы и резервные копии — только в self-hosted Supabase/Yandex Cloud в РФ.
7. Календарь, почта и защита формы — Yandex Workspace/SmartCaptcha.
8. dbt запускается отдельно от API и деплоя: роль `analytics_transformer` читает только `analytics_source`, пишет только `analytics`.

## dbt-аналитика

Подробная настройка: [dbt-analytics.md](dbt-analytics.md).

```bash
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
```

Используйте `sfrfr-dbt.timer` от `sfrfr` (ежедневно в 05:30 МСК) с **прямым**
Postgres YC `:5433` (`DBT_PORT=5433`, `DBT_SSLMODE=disable`). Не добавляйте
этот запуск в `vps_deploy.sh`. Не используйте Supavisor `:5432` для dbt DDL.

## Российский рабочий контур

| Сервис | Статус | Действие |
|---|---|---|
| База/Auth/Storage | self-hosted Supabase в Yandex Cloud | `https://supabase.proverkastaza.ru`; резервные копии в РФ |
| Аналитика | dbt + DataLens | Google Sheets/Looker не используются |
| Календарь/почта | Yandex Workspace | Не отправлять сканы через почту/Диск |
| Защита формы | Yandex SmartCaptcha | `CAPTCHA_PROVIDER=yandex`; Google fallback запрещён в production |
| Статистика сайта | Яндекс Метрика | Только после выбора «Разрешить», вебвизор выключен |
| Search Console | служебная поисковая статистика | Не передавать данные клиентов |

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

Ожидание: health — HTTP 200 и JSON без ПДн; `/docs` в production — HTTP 404.
