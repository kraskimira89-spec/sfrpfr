# 2026-09-26 — бэкапы Supabase db-01

Решение владельца: ежедневный pg_dump в Object Storage (30 копий), еженедельный снапшот
загрузочного диска (2 копии), Cloud Backup всей ВМ, удалить учебную БД `restore_drill`.

## Что сделано

1. Бакет `sfrfr-supabase-db01-backup` (COLD, приватный, 5 ГБ, lifecycle 30 дней), SA
   `sfrfr-db01-backup-writer` с `storage.uploader` только на бакет, статический ключ — на ВМ
   `/etc/sfrfr-backup.env` (600) и в `secrets/` (не в git).
2. `scripts/vm_supabase_backup.sh`: список БД, `globals.sql`, локальный ретеншн, выгрузка через
   rclone с ненулевым кодом при ошибке (дефолты staging сохранены). `vm_supabase_restore_drill.sh`:
   параметр `DRILL_USER`. systemd-таймер 03:30 МСК (`docs/systemd/sfrfr-supabase-backup.*`).
3. Первый дамп 20260926T133354Z: `postgres.dump` 691 КБ, `_supabase.dump` 13 КБ — в бакете.
   Проверочное восстановление в `restore_drill_tmp`: `pg_restore` exit 0, `public` 32 = 32 таблицы,
   cases 149, clients 153, case_messages 1359, auth.users 137 — совпало с оригиналом; временная
   БД удалена.
4. `DROP DATABASE restore_drill` (11 МБ; подключений и ссылок в конфигах не было). Остались
   `postgres` 16 МБ и `_supabase` 7,8 МБ.
5. `fstrim -av`, расписание снапшотов `sfrfr-db01-boot-weekly` (`fd87e0fbma581mbck2s9`):
   вс 05:00 МСК, 2 шт., только загрузочный диск.
6. Cloud Backup: SA `sfrfr-db01-backup-agent` (`backup.user`), привязан к ВМ без остановки; агент
   18.1.41198 без перезагрузки; `A3_CACHE_SIZE=512M`; политика `sfrfr-db01-daily-7d`
   (`cdgiuxcujofludfotdrp`), 01:00 МСК. Первая копия вручную: FULL 6,68 ГБ (из 14,8 ГБ),
   ~6 мин, API на App-VPS всё время отвечал 200.

## Замечания

- В одной рабочей копии параллельно работал другой агент (удалил временные файлы в `tools/`);
  работа продолжена в отдельном `git worktree`.
- Роль агенту — `backup.user` (минимум по документации), а не `backup.editor`.
- Агент Cloud Backup: ~460 МБ RSS в простое, до ~0,8 ГБ во время копии на ВМ 4 ГБ.

Канон: `docs/ops/supabase-db01-backups.md`.
