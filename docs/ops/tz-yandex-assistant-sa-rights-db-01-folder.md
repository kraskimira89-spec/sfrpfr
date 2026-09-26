## Техническое задание для Яндекс Cloud AI-ассистента

### Цель
Выдать сервисному аккаунту `terraform` (id `aje5drfub36p22lspljm`) полные права на каталог новой ВМ Supabase, чтобы агент мог сам читать и править ВМ, security groups и диски этого каталога без ручных действий в консоли.

### Контекст
- Каталог новой ВМ: `b1grtprgfugidt9u073i`.
- ВМ: `sfrfr-supabase-db-01` / id `fhmkkkr7if3ggu6h29uq` / IP `51.250.69.237` (сейчас на неё указывает DNS `supabase.proverkastaza.ru`).
- Security group: `enpf27it4pe5d1brj6as` (`sfrfr-supabase-db-sg`).
- Сервисный аккаунт `terraform` (id `aje5drfub36p22lspljm`) создан в другом облаке/каталоге (`b1g0mhpm9tr4lrurk1bu`, облако `b1gkscu5sqpjtf5d5rbi`). Сейчас на каталог `b1grtprgfugidt9u073i` у него PERMISSION_DENIED (403 при `compute.instances.list`).
- Владелец разрешил «все права» на этот каталог.

### Шаги
1. Открыть каталог `b1grtprgfugidt9u073i` → «Права доступа» (Access bindings).
2. Добавить субъект: сервисный аккаунт с id `aje5drfub36p22lspljm` (тип `serviceAccount`). Если консоль не находит аккаунт из другого облака — добавить через «Назначить роли» по id или через API/CLI:
   `yc resource-manager folder add-access-binding b1grtprgfugidt9u073i --role admin --service-account-id aje5drfub36p22lspljm`
3. Роль: **`admin`** на каталог `b1grtprgfugidt9u073i`.
4. Если `admin` на аккаунт из другого облака назначить нельзя — назначить набор: `editor`, `compute.admin`, `vpc.admin`, `vpc.securityGroups.admin`, `iam.serviceAccounts.user`, и написать, что сделано вместо `admin`.
5. Вернуть список access bindings каталога после изменения (роль → субъект).

### Ограничения
- Не удалять и не менять существующие права других пользователей/аккаунтов.
- Не менять ВМ, диски, SG, DNS, Lockbox в рамках этого задания.
- Не выдавать права на уровне организации или облака — только на каталог `b1grtprgfugidt9u073i`.
- Не создавать новые ключи сервисного аккаунта и не показывать секреты.

### Критерии готовности
- В access bindings каталога `b1grtprgfugidt9u073i` есть `admin` (или перечисленный набор ролей) для `serviceAccount:aje5drfub36p22lspljm`.
- Краткий отчёт: что назначено, id операции.

---
Это техническое задание для выполнения Яндекс-ассистентом.
