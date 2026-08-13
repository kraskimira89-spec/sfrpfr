# 2026-08-13 — обновления WP + облачный бэкап

## Обновления (по одному + HTTP 200)
- Astra 4.13.8 → 4.13.9
- Spectra 2.20.0 → 2.20.1
- Rank Math 1.0.274.1 → 1.0.276
- WPForms Lite 2.0.0.2 → 2.0.0.4
- UpdraftPlus 1.26.5 → 1.26.6
- Wordfence 8.2.2 → 9.0.0 (major; настройки firewall переприменены)

Предупреждение: локальный снимок `/root/wp-preupdate-20260813-194139` (db+files).

## Облако
Бесплатный UpdraftPlus **не** умеет Яндекс.Диск (WebDAV = Premium).
Сделан скрипт `scripts/wp_updraft_sync_yandex_disk.sh` → `disk:/SFRFR-ops/wp-backups` через OAuth Disk API.
