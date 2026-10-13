# Runbook: Supabase вне Яндекса (DR на reg.ru) и возврат

Аварийный план на случай, когда ВМ `sfrfr-supabase-db-01` (Yandex Cloud, `ru-central1-a`,
51.250.69.237) недоступна, а API Compute не даёт её перезапустить (инцидент SFRFR-73,
октябрь 2026). Секреты в этом файле не хранятся — только имена переменных и пути.

Связанные документы: [supabase-selfhost-yandex-cloud.md](supabase-selfhost-yandex-cloud.md),
[supabase-db01-backups.md](supabase-db01-backups.md), [dns-proverkastaza.md](dns-proverkastaza.md),
[cutover-supabase-db-01.md](cutover-supabase-db-01.md).

## 0. Что уже есть

| Что | Где |
|---|---|
| Свежий дамп db-01 (`postgres.dump`, `_supabase.dump`, `globals.sql`, `rowcounts.txt`, `SHA256SUMS`) | ПК владельца `D:\SFRFR-backups\db01-<UTC-штамп>\`; бакет `sfrfr-supabase-db01-backup` (Object Storage работает и при падении зоны) |
| `JWT_SECRET`, `POSTGRES_PASSWORD`, `ANON_KEY`, `SERVICE_ROLE_KEY`, `DASHBOARD_*`, `SECRET_KEY_BASE` стека | `secrets/supabase-staging.env` (не в git). Проверено HMAC: этим `JWT_SECRET` подписаны текущие ключи на VPS и в `.env` → **приложение не нужно перенастраивать по ключам** |
| Секрет Auth Send Email Hook | VPS `/opt/sfrfr/.env` → `SUPABASE_SEND_EMAIL_HOOK_SECRET` (на стеке — `GOTRUE_HOOK_SEND_EMAIL_SECRETS`) |
| Заявки, принятые пока БД лежала | VPS `/opt/sfrfr/storage/emergency_leads.jsonl` (600, `sfrfr`) |
| Клиенты MAX без дела | VPS `/opt/sfrfr/storage/max_intake.json` (`case_id` пустой) + буфер переписки `max_chat_pending.json` |

Файлы клиентов лежат на VPS (`storage/uploads`), в Supabase Storage — 1 объект; переносить Storage
не требуется.

**Статус 2026-10-13 (SFRFR-73):** резервная ВМ reg.ru `194.67.116.168` — стек healthy;
дамп `db01-20261011T003002Z` восстановлен в Postgres (`public` 32 таблицы; clients/cases
совпали с dump). DNS `A supabase` и `.env` App-VPS **ещё не** переключали — шаги 2.7–2.9.

## 1. Шаги владельца на reg.ru

1. **Сразу (до аренды):** в DNS-зоне `proverkastaza.ru` (ns1/ns2.reg.ru) уменьшить TTL записи
   `A supabase` до **300** (сейчас ~86400 — переключение иначе растянется на сутки). IP не менять.
2. Заказать облачный сервер (VPS) reg.ru:
   - Ubuntu **22.04** или **24.04**;
   - не меньше **2 vCPU / 4 ГБ RAM / 40 ГБ SSD** (лучше 4 vCPU / 8 ГБ);
   - публичный IPv4, регион — РФ.
3. При создании в поле «SSH-ключ» вставить публичный ключ ПК агента (файл
   `C:\Users\user\.ssh\id_ed25519.pub`, им же агент ходит на VPS 91.229.11.147):

   ```text
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm user.kraskimira89@gmail.com
   ```

   Это публичная часть, её можно пересылать. Приватный ключ никому не передавать.
4. Прислать агенту **IP сервера** и подтверждение «можно разворачивать». Пароль root не нужен.
5. DNS не трогать — переключение делает агент (через `scripts/regru_add_supabase_a.py`, если есть
   `secrets/regru.env` с API-доступом и IP агента в allowlist) или владелец по инструкции из шага 2.7.

## 2. План агента (после IP от владельца)

Ничего не делать с db-01 и DNS до шага 7. Все команды — по SSH на новый сервер `root@<IP>`.

1. **Базовая настройка:** `apt update && apt -y upgrade`; swap 2 ГБ; часовой пояс UTC;
   UFW: `allow 22/tcp`, `allow 80/tcp`, `allow 443/tcp`, `allow from 91.229.11.147 to any port 5433 proto tcp`,
   `ufw enable`. Postgres 5432/5433 в интернет не открывать.
2. **Docker:** официальный репозиторий Docker CE + compose plugin.
3. **Стек Supabase как на db-01:** `/opt/sfrfr-supabase/supabase/docker` (git clone `supabase/supabase`,
   каталог `docker`); `.env` собрать из `secrets/supabase-staging.env` (те же `JWT_SECRET`, `ANON_KEY`,
   `SERVICE_ROLE_KEY`, `POSTGRES_PASSWORD`, `SECRET_KEY_BASE`, `DASHBOARD_*`),
   `API_EXTERNAL_URL=SUPABASE_PUBLIC_URL=https://supabase.proverkastaza.ru`,
   `SITE_URL=https://cabinet.proverkastaza.ru`. Override прямого Postgres `:5433`
   (`docker-compose.sfrfr-direct-pg.yml` в `COMPOSE_FILE`, см. supabase-selfhost-yandex-cloud.md).
   Передавать `.env` через `scp` с правами 600, не через argv/echo.
   `scripts/vm_supabase_compose_up.sh` → все сервисы healthy.
4. **Загрузка данных:** скопировать `D:\SFRFR-backups\db01-<штамп>\` на сервер (`scp`),
   `sha256sum -c SHA256SUMS`. Затем:
   - `psql -U supabase_admin -f globals.sql` (роли без паролей; ошибки «already exists» ожидаемы);
   - `pg_restore -U supabase_admin -d postgres --clean --if-exists postgres.dump`
     (ошибки по объектам самого Supabase, которые уже созданы стеком, — фиксировать, не править вручную);
   - `_supabase.dump` — в БД `_supabase` тем же способом.
5. **Сверка:** счётчики из `rowcounts.txt` (минимум `public.clients`, `public.cases`,
   `public.case_messages`, `auth.users`) совпадают с восстановленной БД.
6. **Auth-письма:** `GOTRUE_HOOK_SEND_EMAIL_SECRETS` = значение `SUPABASE_SEND_EMAIL_HOOK_SECRET` с VPS,
   `scripts/vm_supabase_enable_auth_email_hook.sh`.
7. **DNS:** `A supabase` → новый IP (TTL 300). Ждать `nslookup supabase.proverkastaza.ru 8.8.8.8`.
8. **TLS:** `scripts/vm_supabase_enable_caddy.sh` (`PROXY_DOMAIN=supabase.proverkastaza.ru`), Let's Encrypt
   выпустится после DNS.
9. **Приложение на VPS:** `SUPABASE_URL` не меняется (домен тот же). Меняются только хосты прямого
   Postgres — `DATABASE_URL`, `DBT_HOST` в `/opt/sfrfr/.env` (51.250.69.237 → новый IP). Это правка
   прод-конфига вне GitHub Actions → **отдельное согласие владельца**, затем рестарт `sfrfr-api` и воркеров.
10. **Проверки:** `GET https://supabase.proverkastaza.ru/rest/v1/` с anon → 200; `api/health` 200;
    вход сотрудника по email-OTP (письмо дошло); вход через ops-бота MAX; тестовая заявка с сайта создаёт
    дело (не `lead_buffered`).
11. **Доимпорт аварийного буфера:**
    `cd /opt/sfrfr && sudo -u sfrfr env PYTHONPATH=src .venv/bin/python scripts/import_emergency_leads.py`
    (dry-run, смотреть `to_import`), затем то же с `--apply`. Повторный запуск ничего не дублирует.
12. **MAX:** переписка клиентов без дела доливается сама, когда клиент пишет снова (бот создаёт дело и
    вызывает `flush_pending_case_chat`). Принудительно — `scripts/flush_max_chat_pending.py --dry-run`,
    затем без флага. Клиентов из `max_intake.json` с пустым `case_id` за период сбоя — передать
    специалистам для ответа.
13. **Миграции:** догнать недостающие объекты (`case_messages.read_at_client`,
    `case_messages.external_message_id`, таблица `document_groups`) — только аддитивные, после свежего
    `pg_dump`. Удаляющие/меняющие данные — не применять без владельца.
14. **Бэкапы:** `scripts/vm_supabase_backup.sh` + таймер (как на db-01) с выгрузкой в бакет
    `sfrfr-supabase-db01-backup` под отдельным префиксом `supabase-regru/`.

## 3. Возврат в Яндекс

Временный сервер становится **единственным источником правды** с момента переключения DNS.
db-01 после восстановления зоны содержит данные на 10.10 ~15:52 МСК и **не должен** снова принимать
запись, иначе данные разойдутся.

1. Когда зона `ru-central1-a` поднимется, db-01 можно запустить: записи туда не будет, потому что
   VPS обращается к домену, а домен уже указывает на reg.ru. Проверить, что `DATABASE_URL`/`DBT_HOST`
   на VPS не указывают на 51.250.69.237.
2. Окно переключения (вечер, 15–30 мин): остановить запись (`systemctl stop sfrfr-api` и воркеры на VPS
   — с согласия владельца), снять `pg_dump -Fc` с временного сервера.
3. На db-01: свежий `pg_dump` текущего состояния (на всякий случай) → `pg_restore --clean` дампа
   с временного сервера → сверка счётчиков.
4. DNS `A supabase` → 51.250.69.237; хосты Postgres на VPS обратно; старт сервисов; проверки как в 2.10.
5. Временный сервер держать выключенным ещё 7 дней (не удалять), затем — удалить вместе с дисками,
   так как на нём ПДн.

## 4. Чего не делать

- Не открывать Postgres в интернет; `5433` — только с 91.229.11.147.
- Не генерировать новый `JWT_SECRET`: сломает ключи на VPS, в кабинете и админке.
- Не держать два работающих источника записи (db-01 и временный) одновременно.
- Не класть дамп и `.env` стека в git и в публичные места.
