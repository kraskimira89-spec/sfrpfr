# ТЗ-16: Terraform-инфраструктура SFRFR в Yandex Cloud

## 1. Цель

Подготовить воспроизводимый Terraform-проект для **staging-контура SFRFR в РФ**:

- VPC, подсеть и Security Group;
- одна Compute Cloud VM для self-hosted Supabase (Docker Compose);
- статический публичный IP;
- private Object Storage для резервных копий;
- IAM-сервисные аккаунты с минимальными ролями;
- Lockbox/KMS там, где это поддерживается выбранной схемой;
- задел для импорта существующих ресурсов в Terraform state.

Первый результат — **готовый пример конфигурации**, а не применение в облаке.  
`terraform apply`, создание платных ресурсов и изменение DNS выполняются только после отдельного подтверждения.

## 2. Контекст Yandex Cloud

| Параметр | Значение |
|---|---|
| Cloud | `sfrfr-ai` |
| `cloud_id` | `b1gkscu5sqpjtf5d5rbi` |
| Folder | `default` |
| `folder_id` | `b1g0mhpm9tr4lrurk1bu` |
| Регион | только РФ, базово `ru-central1` |
| Зона staging | переменная, по умолчанию `ru-central1-a` |
| Домен API Supabase | `supabase.proverkastaza.ru` |
| Текущий prod | VPS `91.229.11.147`, **не изменять** |

> На 2026-07-28 облако было заблокировано из-за нулевого баланса. Перед `plan/apply`
> проверить `docs/ops/yandex-cloud-billing-unblock.md`. Генерация файлов не зависит от биллинга.

## 3. Архитектурное решение первой фазы

```text
Internet
  │ HTTPS 443
  ▼
Static public IP
  ▼
Compute VM (Ubuntu, ru-central1)
  ├── Caddy/Nginx
  ├── Supabase Docker Compose
  │   ├── Kong / Auth / REST / Realtime / Storage
  │   └── PostgreSQL на отдельном data disk
  └── backup job
        └── private Object Storage bucket (РФ)
```

### Почему не Managed PostgreSQL / Kubernetes сразу

Self-hosted Supabase зависит от согласованного набора Postgres-расширений, Auth,
PostgREST, Realtime и Storage. Для staging проще и надёжнее одна VM + официальный
Compose. Managed PostgreSQL, Managed Kubernetes, Functions/API Gateway и Serverless
Containers — отдельная фаза после успешного staging и restore-drill.

## 4. Требуемая структура

AI-ассистент должен создать пример в:

```text
infra/yandex-cloud/
├── README.md
├── versions.tf
├── providers.tf
├── variables.tf
├── locals.tf
├── network.tf
├── security-groups.tf
├── iam.tf
├── compute.tf
├── storage.tf
├── kms.tf
├── outputs.tf
├── cloud-init.yaml.tftpl
├── terraform.tfvars.example
├── backend.hcl.example
└── imports.md
```

Допустимо выделить небольшие модули, но без избыточной абстракции.

## 5. Terraform-ресурсы

### 5.1 Provider и state

- Использовать актуальный официальный provider `yandex-cloud/yandex`.
- Версии Terraform/provider не угадывать: сверить с актуальной документацией.
- Аутентификация без статических секретов в git: профиль `yc`, IAM token или
  авторизованный key-файл вне репозитория.
- Начальный state локальный.
- Подготовить `backend.hcl.example` для последующего переноса state в отдельный
  private bucket, но не коммитить реальные ключи и state.

### 5.2 VPC

- Сеть `sfrfr-staging`.
- Подсеть в одной зоне `ru-central1-*`, CIDR задаётся переменной.
- Security Group:
  - `443/tcp` из интернета;
  - `80/tcp` только для redirect/ACME, если выбран этот TLS-сценарий;
  - `22/tcp` только из `allowed_ssh_cidrs`, **без** `0.0.0.0/0` по умолчанию;
  - внутренний трафик между ресурсами группы;
  - `5432`, Supabase Studio и служебные порты не открывать наружу;
  - egress — только необходимый; допустим полный egress на первой staging-фазе
    с явным комментарием.

### 5.3 Compute

- VM Ubuntu 22.04/24.04 LTS из актуального семейства образов.
- Параметры по умолчанию:
  - 4 vCPU;
  - 8 GB RAM;
  - boot disk 30 GB;
  - отдельный network SSD data disk 100 GB;
  - preemptible/spot — `false`.
- Статический публичный IPv4.
- SSH-ключ передаётся переменной/metadata; приватный ключ не создаётся Terraform.
- `cloud-init`:
  - создаёт непривилегированного пользователя;
  - устанавливает Docker Engine + Compose plugin;
  - монтирует data disk по UUID;
  - создаёт каталог `/opt/sfrfr-supabase`;
  - не содержит паролей/JWT/API-ключей;
  - не запускает прод-cutover.

### 5.4 IAM

Разделить роли:

1. `sfrfr-staging-vm` — доступ VM только к нужным секретам/бакету.
2. `sfrfr-backup-writer` — запись backup-объектов без публичного доступа.
3. Terraform deployer — документировать минимальные роли, но не создавать
   бессрочный key-файл в репозитории.

Не выдавать `editor`/`admin` сервисным аккаунтам приложения без доказанной необходимости.

### 5.5 Object Storage

- Private bucket для backup: имя через переменную с уникальным суффиксом.
- Public ACL / website hosting выключены.
- Versioning включён.
- Lifecycle:
  - удалить/перевести старые backup по заданному сроку;
  - срок задаётся переменной, безопасное значение по умолчанию — 90 дней.
- Server-side encryption с KMS, если provider и выбранный API это поддерживают.
- Бакет документов приложения в первой итерации **не создавать**, если Storage
  остаётся внутри Supabase Compose. Подготовить опциональный флаг на следующую фазу.

### 5.6 Lockbox/KMS

- Создать KMS symmetric key с rotation period.
- Подготовить Lockbox secret-контейнеры/имена, но реальные значения не задавать в
  `.tfvars` и не помещать в state.
- Объяснить безопасный способ загрузки значений после `apply`.

## 6. DNS и TLS

- Terraform должен вывести публичный IP и рекомендуемую DNS-запись:
  `supabase.proverkastaza.ru A <IP>`.
- На первой итерации **не менять DNS автоматически**.
- TLS: Caddy/Nginx на VM или ALB + Certificate Manager. Для staging по умолчанию
  выбрать Caddy/Nginx как более простой вариант; ALB вынести в optional phase.
- Supabase Studio доступна только через SSH tunnel/VPN.

## 7. Supabase и приложение

Terraform не должен хранить `POSTGRES_PASSWORD`, `JWT_SECRET`, `ANON_KEY`,
`SERVICE_ROLE_KEY`, SMTP credentials.

После создания VM:

1. Развернуть официальный self-hosted Supabase Compose.
2. Секреты загрузить отдельно из Lockbox/защищённого файла.
3. Применить `supabase/migrations/`.
4. На staging переключить только env:
   `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
   `DATABASE_URL`, `NEXT_PUBLIC_SUPABASE_*`.
5. Прод-VPS и DNS не переключать.

## 8. Импорт существующих ресурсов

Сформировать `imports.md` с безопасной последовательностью:

1. `terraform import` только после сверки `cloud_id/folder_id`.
2. Сначала импорт VPC/subnet/SG/IP/VM/bucket по фактическим ID.
3. После каждого импорта — `terraform plan`; ожидается отсутствие destructive changes.
4. Если ресурс не соответствует конфигурации — адаптировать код, а не пересоздавать.
5. Не импортировать/не трогать текущий VPS вне Yandex Cloud.

Привести шаблоны команд, но не выдумывать resource ID:

```bash
terraform import yandex_vpc_network.staging <NETWORK_ID>
terraform import yandex_compute_instance.supabase <INSTANCE_ID>
```

## 9. Переменные

Обязательные:

- `cloud_id`, `folder_id`, `zone`;
- `environment`, `project_name`;
- `network_cidr`, `allowed_ssh_cidrs`;
- `ssh_username`, `ssh_public_key_path`;
- VM CPU/RAM/disk sizes;
- backup bucket name/retention;
- labels (`project=sfrfr`, `environment=staging`, `managed_by=terraform`).

В `terraform.tfvars.example` можно зафиксировать публичные ID folder/cloud, но:

- без токенов;
- без приватных ключей;
- без паролей;
- без реального домашнего IP пользователя.

## 10. Задачи для AI-ассистента

### P0 — обязательный результат

1. Прочитать это ТЗ и связанные документы.
2. Проверить актуальные схемы provider.
3. Создать структуру `infra/yandex-cloud/`.
4. Реализовать VPC/subnet/SG/static IP/VM/data disk.
5. Реализовать IAM least privilege, backup bucket, KMS.
6. Добавить безопасный `cloud-init`.
7. Добавить outputs и `terraform.tfvars.example` под наш folder.
8. Добавить `README.md`: init → fmt → validate → plan → apply.
9. Добавить `imports.md`.
10. Выполнить `terraform fmt -check` и `terraform validate` локально, если Terraform доступен.

### P1 — после P0

- Backend для remote state с отдельным bootstrap-шагом.
- DNS zone/record как опция `manage_dns=false`.
- Snapshot schedule / backup job.
- Monitoring/alerts по VM и диску.

### P2 — не включать в первый apply

- Managed PostgreSQL;
- Managed Kubernetes;
- Serverless Containers / Functions / API Gateway;
- Application Load Balancer;
- перенос FastAPI/WordPress;
- prod-cutover и импорт клиентских данных.

## 11. Критерии приёмки

- `terraform fmt -check` проходит.
- `terraform validate` проходит.
- `terraform plan` не требует секретов в командной строке/репозитории.
- В plan нет публичного `5432`, Studio или SSH `0.0.0.0/0`.
- Создаётся только staging, prod не изменяется.
- Бакет private, versioning/lifecycle включены.
- VM имеет отдельный data disk и непубличные секреты.
- Outputs не содержат ключей/паролей.
- README содержит destroy/rollback, оценку ресурсов и предупреждение о биллинге.
- Конфигурация привязана к folder `b1g0mhpm9tr4lrurk1bu`, но переносима через variables.

## 12. Связанные документы

- `prompts/system/yandex-cloud-agent.md`
- `prompts/tasks/yandex-cloud-terraform-staging.md`
- `docs/specs/15-data-localization-ru.md`
- `docs/ops/supabase-selfhost-yandex-cloud.md`
- `docs/ops/yandex-cloud-billing-unblock.md`
- `docs/ops/cutover-manual-checklist.md`
