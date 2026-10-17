# 2026-10-17 — копия WP на Яндекс.Диск «застыла»

## Канон

| Что | Куда | Расписание | Секреты |
|-----|------|------------|---------|
| Архивы UpdraftPlus (`wp-content/updraft`) | `disk:/SFRFR-ops/wp-backups` | WP cron weekly + `/etc/cron.d/sfrfr-wp-updraft-yadisk` пн 04:30 | `YANDEX_OAUTH_ACCESS_TOKEN`, `YANDEX_DISK_ENABLED` в `/opt/sfrfr/.env` (локально `secrets/yandex-workspace.env`) |
| Зеркало дел (отдельно) | `disk:/SFRFR-cases/…` | best-effort при upload | тот же OAuth |

Скрипт: `scripts/wp_updraft_sync_yandex_disk.sh`. Лог: `/var/log/sfrfr-wp-updraft-yadisk.log`.

## Причина

1. В WP пропали cron-события `updraft_backup` / `updraft_backup_database` (остался только `updraftplus_clean_temporary_files`).
2. Локальные архивы не обновлялись с **2026-08-13**; weekly sync на Диск лишь перезаливал тот же набор (mtime на Диске выглядел «свежим» от overwrite).
3. `updraft_service=""` → предупреждения `methods/"".php`.

OAuth / квота / cutover supabase — не виноваты (Disk API 200, токен живой).

## Что сделано

- Восстановлен schedule Updraft; `updraft_service=none`.
- Снят зависший `updraft_jobdata_*` / semaphore после ручного `boot_backup`.
- Прогнан свежий бэкап `2026-10-17-1155` и sync → Диск `ok=8 failed=0`.
- В репо: `wp_updraft_ensure_schedule.sh` + sync только свежего набора + retry 5xx; cron ensure ежедневно 03:50.
