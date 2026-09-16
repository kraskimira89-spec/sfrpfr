# Доступ к production

> Секреты сюда **не** пишем: ни приватные SSH-ключи, ни `.env`, ни токены, ни connection strings.
> Фактические IP/VM/пользователи — в `infrastructure-inventory.md` (этот файл ссылается туда, а не дублирует).

## Принципы

- Postgres **не публикуется** в интернет (порты 5432/5433 закрыты для внешних сетей).
- Supabase Studio **не публикуется** в интернет (порт 8000 закрыт снаружи; доступ только через SSH-туннель).
- SSH разрешён только с конкретных CIDR `/32`, через VPN/bastion или через console.
- SSH-доступ выполняется **только по ключу**; пароли отключены там, где это совместимо с текущей конфигурацией.
- Для Studio используется SSH-туннель, а не inbound-правило на порт 8000.
- Секреты хранятся вне Git: secret manager (YC Lockbox), CI secrets или локальный `.env`.

## Доступ по SSH

| Поле | Значение |
|---|---|
| Production VM (приложение) | `infrastructure-inventory.md` → VM B (reg.ru) |
| Production VM (БД) | `infrastructure-inventory.md` → VM C (YC supabase) |
| SSH user | VM B — `root`; VM C — `sfrfr` (по IaC/cloud-init) |
| Порт | 22 |
| Key location | локальный защищённый путь; точное имя ключа здесь не фиксируется (см. правило ниже) |
| Allowed source | текущий публичный IPv4 администратора с `/32`; обновлять при смене сети |
| Emergency access | console провайдера (reg.ru / YC) либо bastion/VPN |

### Правило про ключи

Не фиксировать в этом документе абсолютные пути к приватным ключам, если они раскрывают личные данные (например, `C:\Users\<имя>\.ssh\...`). Вместо этого использовать нейтральные плейсхолдеры:

- приложение (VM B): ключ владельца `id_ed25519` и deploy-ключ (GitHub Actions) — оба в `authorized_keys` у `root`;
- БД (VM C): публичный ключ задаётся через `ssh_public_key_path` в Terraform (`infra/yandex-cloud`) и попадает в cloud-init.

### Управление allowlist

- Allowlist задаётся:
  - VM B — через firewall/Security Groups панели reg.ru;
  - VM C — через Terraform `allowed_ssh_cidrs` в `infra/yandex-cloud/terraform.tfvars` (с последующим `plan`/`apply`).
- Источник IP администратора — только публичный IPv4 с маской `/32`.
- При динамическом IP провайдера: обновлять allowlist при смене сети или использовать VPN/bastion с фиксированным IP.
- Никогда не ставить `0.0.0.0/0` и `::/0`.

## SSH-туннель к Studio/API Supabase (VM C)

```bash
# Studio доступен только локально на ВМ (localhost:8000).
# С машины администратора — туннель, без открытия 8000 наружу:
ssh -L 8000:localhost:8000 <ssh_user>@<vm_c_public_ip>
# затем открыть http://localhost:8000
```

## Запрещено

- `0.0.0.0/0` (и `::/0`) на TCP/22, 5432/5433 или 8000.
- Публиковать `.env`, SSH-ключи, `terraform.tfvars`, Terraform state, DB URL, service keys.
- Выполнять DDL/DML без backup и preflight.
- Хранить приватные ключи в репозитории или в рабочих каталогах, не защищённых от утечки.

## Ответственные

- Кто меняет allowlist/firewall: владелец аккаунта (reg.ru / YC), по согласованию — инженер.
- Кто выдаёт доступ: только после подтверждения production VM по `infrastructure-inventory.md`.
