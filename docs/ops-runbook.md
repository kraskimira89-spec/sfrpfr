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
