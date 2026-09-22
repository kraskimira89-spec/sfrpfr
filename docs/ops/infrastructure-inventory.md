# Реестр инфраструктуры SFRFR

> Статус: черновик, заполнен по фактам 2026-09-15. Production-контур подтвержден частично (см. «Требуют подтверждения»).
> Обновлять при смене провайдера, VM, IP, домена, доступа или deploy-процесса.
> Не хранить здесь токены, пароли, приватные SSH-ключи, `.env` и connection strings.
>
> Источники: `[R]` — репозиторий (код/IaC/док); `[N]` — сетевая проверка 2026-09-15; `[P]` — панель провайдера (скриншоты пользователя); `[—]` — не подтверждено.

## Production: подтвержденный контур

Production SFRFR состоит из **двух VM**: приложение (reg.ru) и база данных (Yandex Cloud).

### VM B — приложение (production, подтверждено)

| Поле | Значение | Как подтверждено | Проверено |
|---|---|---|---|
| Cloud provider | reg.ru Cloud | `[P]` панель reg.ru | 2026-09-15 |
| Account | личный кабинет reg.ru | `[P]` | 2026-09-15 |
| VM name / ID | «reg target» / `6047189` | `[P]` | 2026-09-15 |
| Public IP | `91.229.11.147` | `[P]` + `[N]` DNS | 2026-09-15 |
| Private IP | `192.168.0.231` | `[P]` | 2026-09-15 |
| Region / DC | РФ, конкретная площадка — TBD | `[—]` | — |
| OS / image | TBD (предположительно Ubuntu) | `[—]` вкладка «Информация» | — |
| SSH user | `root`, порт 22 | `[R]` docs/ops/vps-ssh.md | 2026-09-15 |
| DNS | `proverkastaza.ru`, `www`, алиасы `proverka-staza.ru`, `prostaz.ru`, `taxi-doroga-dobra.ru` | `[N]` → `91.229.11.147` | 2026-09-15 |
| API / cabinet domains | `api.` / `cabinet.` / `admin.`proverkastaza.ru | `[N]` → `91.229.11.147` | 2026-09-15 |
| Сервисы | Apache vhosts (`docs/apache-vhost-*.conf`), каталоги `/var/www/taxi-doroga-dobra*` | `[R]` + `[P]` скрин файлового менеджера | 2026-09-15 |
| Database location | **Не на этой VM.** Клиент app-сервера ходит в БД по `DATABASE_URL`; фактический адресат — см. VM C, состояние требует подтверждения | `[R]` | — |
| Deployment method | GitHub Actions `deploy-vps.yml` → SSH → `sudo bash /opt/sfrfr/scripts/vps_deploy.sh` (git fetch + reset --hard origin/main, venv reinstall, `systemctl restart sfrfr-api` + Next-кабинеты) | `[R]` | 2026-09-15 |
| systemd units | `sfrfr-api`, `sfrfr-cabinet`, `sfrfr-admin`, `sfrfr-document-ingest`, `sfrfr-case-chat-outbox` | `[R]` scripts/vps_deploy.sh, vps_apply_supabase_yc_env.sh | 2026-09-15 |
| Migration runner | Не здесь (на VM C) | `[R]` | 2026-09-15 |
| Backup method | TBD | `[—]` | — |

### VM C — база данных / self-hosted Supabase (Yandex Cloud)

| Поле | Значение | Как подтверждено | Проверено |
|---|---|---|---|
| Cloud provider | Yandex Cloud | `[R]` IaC | 2026-09-15 |
| Account / folder | cloud `b1gkscu5sqpjtf5d5rbi` / folder `b1g0mhpm9tr4lrurk1bu` | `[R]` tfvars | 2026-09-15 |
| VM name | `sfrfr-staging-supabase` | `[R]` IaC | 2026-09-15 |
| Public IP | `51.250.13.240` | `[R]` + `[N]` DNS `supabase.proverkastaza.ru` | 2026-09-15 |
| Private IP | TBD (консоль YC) | `[—]` | — |
| Region / zone | `ru-central1-a` | `[R]` IaC | 2026-09-15 |
| OS / image | `ubuntu-2404-lts`, platform `standard-v3`, 4 vCPU / 8 GB, non-preemptible | `[R]` IaC | 2026-09-15 |
| Диски | boot network-ssd 30 GB + data network-ssd 100 GB (`/data`), `auto_delete=false` | `[R]` IaC | 2026-09-15 |
| SSH user | `sfrfr`, порт 22 | `[R]` IaC/cloud-init | 2026-09-15 |
| DNS | `supabase.proverkastaza.ru` → `51.250.13.240` | `[N]` | 2026-09-15 |
| Сервисы (по IaC/докам) | Docker Compose Supabase в `/opt/sfrfr-supabase/supabase/docker`; Postgres `supabase-db` :5433 direct / :6432 Supavisor; Studio — только туннель | `[R]` docs/ops/supabase-selfhost-yandex-cloud.md, README.sfrfr-ports.txt | **требует перепроверки на ВМ — см. «Требуют подтверждения» п.1** |
| Database location | Postgres контейнер `supabase-db` (по документации 2026-08) | `[R]` | требует подтверждения |
| Migration runner | `scripts/vm_supabase_apply_migrations.sh` — docker exec psql в `supabase-db`; реестр `sfrfr_ops.schema_migrations` | `[R]` | 2026-09-15 |
| Backup method | `scripts/vm_supabase_backup.sh` (`pg_dump -Fc` → `/data/backups`), бакет `sfrfr-staging-backup-b1g0mhpm` (SSE-KMS, versioning, lifecycle 90 дн.), restore-drill `vm_supabase_restore_drill.sh` | `[R]` IaC + scripts | 2026-09-15 (фактическое расписание cron — TBD) |

### VM A — прежний staging в YC: **отклонена**

| Поле | Значение |
|---|---|
| VM name | `sfrfr-staging-app` |
| Public IP | `130.193.51.181` |
| DNS | нет ни одной A-записи (`[N]` 2026-09-15) |
| Статус | **rejected** — не участвует в production-контуре; судя по скриншоту панели YC, может быть остановлена/архивирована. Не открывать SSH, не применять миграции |

## Облачные аккаунты

| Provider | Account/folder | Purpose | VM candidates | Production status | Checked |
|---|---|---|---|---|---|
| Yandex Cloud | folder `b1g0mhpm9tr4lrurk1bu` (cloud `b1gkscu5sqpjtf5d5rbi`) | self-host Supabase (ТЗ-15), AI-сервисы | `sfrfr-staging-supabase` / `51.250.13.240`; `sfrfr-staging-app` / `130.193.51.181` | DB-контур (supabase) — подтвержден документально, требует живой сверки; app-контур — rejected | 2026-09-15 |
| reg.ru Cloud | аккаунт Kraskimira89 | приложение, витрина, кабинеты | «reg target» `6047189` / `91.229.11.147` | **confirmed** (приложение) | 2026-09-15 |
| GitHub | `kraskimira89-spec/sfrpfr` | репозиторий, CI/CD | — | repo **private** (проверено: API без токена → 404) | 2026-09-15 |

## Подтверждение production VM

Production VM считается подтвержденной только если выполнены минимум два независимых условия. Текущее состояние:

| Условие | VM B (reg.ru) | VM C (YC supabase) |
|---|---|---|
| IP совпадает с DNS production-домена | ✅ `91.229.11.147` = A `@/api/cabinet/admin` | ✅ `51.250.13.240` = A `supabase` |
| Сервисы SFRFR на VM подтверждены | ✅ Apache vhosts + каталоги витрины `[R]`+`[P]` | ⚠️ только по документации `[R]`; живой docker ps не снят |
| Deploy-каталог/проект совпадает с репо | ✅ `/opt/sfrfr` (workflow, скрипты) | ⚠️ `/opt/sfrfr-supabase` по докам; не сверен на ВМ |
| Health endpoint отвечает | ⏳ не проверялся с этой машины | ⏳ Studio/API :8000 закрыты снаружи (by design), проверка — только туннелем |
| VM/metadata связаны с проектом | ⏳ hostname `sfrfr-VPS-D` `[P]` — да | ✅ labels `project=sfrfr` `[R]` |

**Вывод: VM B подтверждена полностью. VM C подтверждена документально и по DNS; статус «живого» контура БД требует read-only сверки на самой ВМ (Фаза A).**

## Требуют подтверждения (TBD / противоречия)

1. **Состояние Postgres на VM C не подтверждено.** В прошлой operational-сессии поступали противоречивые сведения (отсутствие контейнера `supabase-db`, порты 5432/5433, приватный адрес `10.10.10.29`), которые **не могут быть приняты** без прямой проверки — они расходились с задокументированным контуром и между собой. Фаза A обязана зафиксировать: `docker ps`, фактические listen-порты, `psql`-версию и список БД.
2. **Фактический адресат `DATABASE_URL` на VM B** (какой порт/хост БД используется сейчас) — смотреть только на ВМ, в реестр не выписывать.
3. OS/image и способ управления VM B (панель reg.ru, cloud-init) — вкладка «Информация».
4. Регион/ЦОД reg.ru, способ и расписание backup VM B — нет данных.
5. Рабочее состояние VM A (остановлена/удалена) и её disk-ресурсы — решение по cleanup отдельно.
6. Статус биллинга YC после разблокировки (`docs/ops/yandex-cloud-billing-unblock.md`) — не верифицирован.

## Сетевые проверки (выполнены 2026-09-15, read-only)

| Запись | Результат |
|---|---|
| `proverkastaza.ru` A | `91.229.11.147` |
| `www.proverkastaza.ru` CNAME→A | `91.229.11.147` |
| `api/cabinet/admin.proverkastaza.ru` A | `91.229.11.147` |
| `supabase.proverkastaza.ru` A | `51.250.13.240` |
| `proverka-staza.ru`, `prostaz.ru`, `taxi-doroga-dobra.ru` A | `91.229.11.147` |
| `130.193.51.181` (VM A) | ни одного DNS-имени |
| `github.com/kraskimira89-spec/sfrpfr` (API, без токена) | HTTP 404 → репозиторий приватный |

## Правила ведения

- Любая смена IP/VM/DNS/провайдера — править этот файл в том же PR, что и изменения.
- Секреты (`.env`, ключи, connection strings, service keys) сюда **не** переносятся никогда.
- Статусы: `confirmed` / `candidate` / `rejected` / `TBD`. `confirmed` — только при ≥2 независимых подтверждениях из таблицы выше.
