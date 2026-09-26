# Бэкапы Supabase db-01 (`sfrfr-supabase-db-01`)

Канон с 2026-09-26. ВМ `fhmkkkr7if3ggu6h29uq` (51.250.69.237), каталог
`b1grtprgfugidt9u073i`, облако `b1gv0ltmj1v9cne0qntm`. ВМ в UTC; время ниже — МСК.
Секреты в этом файле не хранятся.

## Три слоя

| Слой | Что | Когда (МСК) | Где | Хранение |
|---|---|---|---|---|
| pg_dump | `postgres`, `_supabase` (`pg_dump -Fc`) + `globals.sql` (роли без паролей) + `rowcounts.txt` + `SHA256SUMS` | ежедневно 03:30 | бакет `sfrfr-supabase-db01-backup` (COLD), префикс `supabase-db01/<UTC-штамп>/`; локально `/srv/supabase-data/backups/supabase-db01/` | бакет 30 дней (lifecycle), локально 7 дней |
| Снапшот диска | загрузочный диск `fhmfek33qj5ogtpsbr9t` (там Postgres) | воскресенье 05:00 | Compute snapshots, расписание `sfrfr-db01-boot-weekly` | 2 снапшота |
| Cloud Backup | вся ВМ (агент Киберпротект), всегда инкрементально | ежедневно 01:00–01:30 (22:00 UTC + до 30 мин случайной задержки) | политика `sfrfr-db01-daily-7d` | 7 копий |

Диск данных `fhmp7dlua2v2kqqf34lh` (`/srv/supabase-data`) снапшотами не покрывается: там
только локальные копии дампов, их оригиналы — в бакете.

## Ресурсы

| Ресурс | Имя | id |
|---|---|---|
| Бакет | `sfrfr-supabase-db01-backup` (приватный, max 5 ГБ, lifecycle `expire-30d` + abort multipart 1 день) | `e3eqhms59k3gh65mjn2f` |
| SA записи дампов | `sfrfr-db01-backup-writer` — только `storage.uploader` на бакет | `ajefvsvo7ojojp8rp6sr` |
| Статический ключ writer | на ВМ `/etc/sfrfr-backup.env` (root, 600); копия `secrets/yc-db01-backup-writer.env` (не в git) | `ajeqkgidkcsv02bc1m48` |
| Расписание снапшотов | `sfrfr-db01-boot-weekly`, cron `0 2 * * 0` (UTC), snapshotCount=2 | `fd87e0fbma581mbck2s9` |
| SA агента Cloud Backup | `sfrfr-db01-backup-agent` — `backup.user` на каталог, привязан к ВМ | `ajenrn0s4dn4nrqv3php` |
| Политика Cloud Backup | `sfrfr-db01-daily-7d` (daily 22:00 время ВМ, ALWAYS_INCREMENTAL, maxCount 7) | `cdgiuxcujofludfotdrp` |
| Ресурс Cloud Backup | агент 18.1.41198 | `ac6fd2c4-e0f3-4488-a877-4930b873facc` |

Политики по умолчанию (`Default daily/weekly/monthly`) не менялись и к ВМ не привязаны.

## pg_dump: как устроено

- Скрипт `scripts/vm_supabase_backup.sh` → на ВМ `/usr/local/sbin/sfrfr-supabase-backup.sh`.
- Юнит и таймер: `docs/systemd/sfrfr-supabase-backup.{service,timer}` → `/etc/systemd/system/`.
  Параметры db-01 (путь, `DUMP_USER=supabase_admin`, список БД, префикс) заданы в юните.
- Выгрузка — `rclone` (пакет Ubuntu), ключи из `/etc/sfrfr-backup.env` через `RCLONE_CONFIG_YC_*`
  (секрет не попадает в argv). Ошибка любого шага → ненулевой код, юнит `failed`.
- Лог: `/var/log/sfrfr-supabase-backup.log`.

Проверка:

```bash
systemctl list-timers sfrfr-supabase-backup.timer
systemctl status sfrfr-supabase-backup.service
sudo tail -n 30 /var/log/sfrfr-supabase-backup.log
```

Ручной запуск: `sudo systemctl start sfrfr-supabase-backup.service`.

## Восстановление

### Из дампа (точечно, данные)

1. Взять дамп: локально `/srv/supabase-data/backups/supabase-db01/<штамп>/postgres.dump`
   или скачать из бакета (writer-ключ имеет чтение через `storage.uploader`):
   `rclone copy yc:sfrfr-supabase-db01-backup/supabase-db01/<штамп> /tmp/restore --config /dev/null`
   (переменные `RCLONE_CONFIG_YC_*` — как в скрипте бэкапа). Сверить `sha256sum -c SHA256SUMS`.
2. Проверочно — во временную БД, рабочие не трогая:

```bash
sudo BACKUP_ROOT=/srv/supabase-data/backups/supabase-db01 DRILL_DB=restore_drill_tmp \
  DRILL_USER=supabase_admin /usr/local/sbin/sfrfr-supabase-restore-drill.sh
# сверка counts, затем:
cd /opt/sfrfr-supabase/supabase/docker && \
  sudo docker compose exec -T db psql -U supabase_admin -d postgres -c 'drop database restore_drill_tmp'
```

3. Боевое восстановление в `postgres` — только отдельным решением владельца (останавливает
   запись приложения; план: стоп API на App-VPS → `pg_restore --clean` → миграции → старт).

### Из снапшота (весь загрузочный диск)

Compute → Снимки дисков → создать диск из снапшота → новая ВМ или замена загрузочного диска
у остановленной ВМ. Данные — на момент снапшота (до 7 дней назад).

### Из Cloud Backup (вся ВМ)

Консоль → Cloud Backup → ВМ `sfrfr-supabase-db-01` → копия → «Восстановить» на ту же или
другую ВМ (у целевой ВМ должен быть агент). Шаг — сутки, глубина — 7 копий.

## Агент Cloud Backup и RAM

- Установлен официальным `agent_installer.sh`, модуль ядра `snapapi26`, без перезагрузки.
- Лимит кэша: `/usr/lib/Acronis/system_libs/config` → `export A3_CACHE_SIZE=512M`.
- Простой: ~460 МБ RSS (`mms` ~230 МБ). Во время копии `service_process` ~0,8 ГБ.
- При обновлении ядра нужны `linux-headers-$(uname -r)`, иначе агент не соберёт модуль.
- SG: исходящий ANY уже есть; входящих правил агент не требует.

## Стоимость (оценка, цены SKU 2026-05, с НДС, 720 ч/мес)

| Статья | Тариф | Объём | ₽/мес |
|---|---|---|---|
| Cloud Backup: ВМ подключена | 0,39 ₽/ч | 1 ВМ | ~281 |
| Cloud Backup: хранилище | ~4,97 ₽/ГБ | первая полная 6,7 ГБ (из 14,8 ГБ) + инкременты, ~7–10 ГБ | ~35–50 |
| Снапшоты | ~3,67 ₽/ГБ | 2 снапшота по ~17 ГБ занятых блоков (верхняя оценка) | ~60–125 |
| Object Storage COLD | ~1,27 ₽/ГБ | 30 × <1 МБ | <1 |
| **Итого** | | | **~380–460** |

Первая копия Cloud Backup 2026-09-26: FULL, `750a9f53-0b7d-4529-9be8-6fab98f74a3e`, 6,68 ГБ,
~6 мин. Фактический объём — в консоли Cloud Backup и Биллинге через неделю работы.
