# Задание AI-ассистенту Yandex Cloud: Terraform staging SFRFR

Подготовь готовый пример Terraform-конфигурации для проекта SFRFR.

## Сначала прочитай

1. `@prompts/system/yandex-cloud-agent.md`
2. `@docs/specs/16-yandex-cloud-terraform.md`
3. `@docs/specs/15-data-localization-ru.md`
4. `@docs/ops/supabase-selfhost-yandex-cloud.md`
5. `@docs/ops/yandex-cloud-billing-unblock.md`

## Наш контекст

```text
cloud_name = sfrfr-ai
cloud_id   = b1gkscu5sqpjtf5d5rbi
folder     = default
folder_id  = b1g0mhpm9tr4lrurk1bu
region     = ru-central1
environment = staging
public Supabase host = supabase.proverkastaza.ru
current production VPS = 91.229.11.147 (не трогать)
```

Биллинг мог быть заблокирован. Не выполняй создание платных ресурсов, `apply`,
импорт или изменение DNS без отдельного подтверждения. Сейчас нужен код и
проверяемый `plan`.

## Что создать

Создай в репозитории `infra/yandex-cloud/`:

- provider/versions/variables/locals/outputs;
- VPC + subnet;
- Security Group: HTTPS, ограниченный SSH, без публичного Postgres/Studio;
- статический IP;
- Compute VM 4 vCPU / 8 GB;
- boot disk 30 GB + data disk 100 GB;
- безопасный `cloud-init` с Docker Compose, без секретов;
- IAM SA с минимальными ролями;
- private Object Storage bucket для backup, versioning/lifecycle;
- KMS key;
- пример backend и инструкция миграции state;
- `terraform.tfvars.example` с публичными `cloud_id/folder_id`;
- `imports.md` с шаблонами импорта;
- README с командами `init`, `fmt`, `validate`, `plan`, `apply`, rollback/destroy.

## Архитектурное решение

Первая фаза — **одна VM + официальный Supabase Docker Compose**. Не заменяй это
на Managed PostgreSQL или Kubernetes: они P2 после staging. Functions, API Gateway,
Serverless Containers и ALB тоже не включай в первый plan.

## Безопасность

- Не создавай и не коммить API key, authorized key, private SSH key, пароли,
  JWT/anon/service-role tokens.
- `allowed_ssh_cidrs` не имеет небезопасного default.
- `5432`, Supabase Studio и служебные порты не открыты в интернет.
- Бакеты private, без website/public ACL.
- Секреты Supabase не должны попадать в Terraform state.
- Все ресурсы и backups — только РФ.

## Режим работы

1. Проверь актуальную документацию provider и реальные имена аргументов.
2. Не выдумывай ID ресурсов. Используй variables/placeholders.
3. Делай минимальный понятный Terraform без лишней модульности.
4. Если Terraform установлен — выполни:

```bash
terraform fmt -check
terraform init -backend=false
terraform validate
```

5. Не выполняй `terraform apply`.
6. В финале дай:
   - созданные файлы;
   - результат validate;
   - какие значения должен дать пользователь;
   - ориентировочный перечень платных ресурсов;
   - риски/блокеры;
   - следующую безопасную команду для `plan`.

## Готовность

Результат принят, когда выполнены критерии из
`docs/specs/16-yandex-cloud-terraform.md` §11 и plan не затрагивает текущий prod.
