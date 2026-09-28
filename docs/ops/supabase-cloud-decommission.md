# Удаление проекта Supabase Cloud `frualvycousvvyjivybu`: чеклист и акт

> Статус: подготовлено 28.09.2026 агентом. **Удаляет владелец сам**; агент в Supabase Cloud
> ничего не удалял и не менял.
> Основа: [supabase-cloud-drain-checklist.md](./supabase-cloud-drain-checklist.md) (критерии drain),
> [15-data-localization-ru.md](../specs/15-data-localization-ru.md) (cutover 03.08.2026:
> импорт `clients=11`, `cases=9`, `auth.users=10`),
> [processors-assignment-review-2026-09.md](../contracts/processors-assignment-review-2026-09.md),
> письмо в РКН — [rkn-notification-2026-09.md](../contracts/rkn-notification-2026-09.md), п. 10.
> ПДн физлиц, ключи и значения переменных в этот файл не вносить.

## 1. Предусловия (до удаления)

### 1.1. Прод не ссылается на `*.supabase.co` — проверено агентом 28.09.2026

| Где | Результат |
|---|---|
| `src/`, `apps/*/src`, `web/` | ссылок нет |
| `.env` на VPS: `/opt/sfrfr/.env`, `apps/cabinet/.env`, `apps/admin/.env` | 0 совпадений `supabase.co` / `frualvycousvvyjivybu` |
| `.env.example` (корень, `apps/cabinet`, `apps/admin`) | только плейсхолдер `YOUR_PROJECT.supabase.co` |
| GitHub workflows `ci.yml`, `deploy-vps.yml` | только `https://example.supabase.co` для сборки Next (фиктивный адрес) |
| GitHub Actions secrets | переменных Supabase нет |
| Утилиты миграции (не прод): `scripts/cutover_dump_cloud_sql.py`, `scripts/dbt_runtime_probe.py`, `scripts/supabase_patch_auth_emails.py`, `scripts/supabase_enable_auth_send_email_hook.py` | ссылаются на Cloud; после удаления — убрать или пометить устаревшими отдельной задачей |
| Тесты `tests/unit/test_supabase_auth_email.py` | строка `frualvycousvvyjivybu.supabase.co` как тестовые данные — не влияет на прод |
| Локально `secrets/supabase-access.env` | `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF` |

Повторить перед удалением (PowerShell, из корня репо):

```powershell
rg -n "supabase\.co|frualvycousvvyjivybu" src apps web .github .env.example
ssh sfrfr-vps 'sudo grep -cE "supabase\.co|frualvycousvvyjivybu" /opt/sfrfr/.env /opt/sfrfr/apps/*/.env'
```

Ожидание: в `src/apps/web` пусто, в `.env` на VPS — нули.

### 1.2. Сверка данных облака и самохоста — делает владелец

Облако заморожено с 03.08.2026, на самохосте строк больше (новые клиенты). Проверяем,
что **все** строки облака есть на самохосте. Результаты запросов **не сохранять в git**.

**Шаг A. Облако** (Supabase Dashboard → SQL Editor, проект `frualvycousvvyjivybu`):

```sql
select 'clients' t, count(*) n, array_agg(id) ids from public.clients
union all select 'cases', count(*), array_agg(id) from public.cases
union all select 'consents', count(*), array_agg(id) from public.consents
union all select 'documents', count(*), array_agg(id) from public.documents
union all select 'orders', count(*), array_agg(id) from public.orders
union all select 'payments', count(*), array_agg(id) from public.payments
union all select 'case_messages', count(*), array_agg(id) from public.case_messages
union all select 'contract_acceptances', count(*), array_agg(id) from public.contract_acceptances;

-- auth: сверяем по хэшу e-mail (id могли смениться при переносе через Admin API)
select 'auth.users' t, count(*) n, array_agg(md5(lower(email))) keys from auth.users;

-- storage: объекты по бакетам
select bucket_id, count(*) n, array_agg(bucket_id || '/' || name) keys
from storage.objects group by bucket_id;
```

Если какой-то таблицы в облаке нет — убрать её строку. Записать число `n` по каждой строке.

**Шаг B. Самохост** (db-01, read-only): подставить массив из шага A вместо `'{…}'`.

```sql
select count(*) from public.clients where id = any('{…}'::uuid[]);  -- = n из облака
-- так же для cases, consents, documents, orders, payments, case_messages, contract_acceptances
select count(*) from auth.users where md5(lower(email)) = any('{…}'::text[]);
select count(*) from storage.objects where bucket_id || '/' || name = any('{…}'::text[]);
```

Запуск на db-01 (сессия только для чтения):

```powershell
Get-Content .\tmp\check.sql | ssh sfrfr@51.250.69.237 "cd /opt/sfrfr-supabase/supabase/docker && sudo docker compose exec -T db psql -U postgres -tA -c 'set default_transaction_read_only=on' -f -"
```

Критерий: по каждой строке счётчик самохоста = `n` облака. Расхождение — **стоп**,
не удалять, разобраться (догрузить недостающее).

Справочно, самохост на 28.09.2026: 32 таблицы в `public`, `auth.users` = 145,
`storage.objects` = 10 (бакет `pension-docs`), `consents` = 76.

### 1.3. Финальный дамп — только при расхождении

Если шаг B сошёлся, отдельный дамп облака **не нужен**: данные уже в самохосте и в его
ежедневных бэкапах (Yandex Object Storage, 30 дней). Лишняя копия продлевает хранение ПДн.

Если нужна копия (например, спорные строки): `pg_dump` облака в зашифрованный бакет
Yandex Object Storage (РФ) с lifecycle ≤ 90 дней; объекты storage — выгрузить туда же.
Утилита переноса: `scripts/cutover_dump_cloud_sql.py`. Факт дампа записать в акт (раздел 4).

### 1.4. Прочее

- [ ] Критерии из [supabase-cloud-drain-checklist.md](./supabase-cloud-drain-checklist.md) выполнены.
- [ ] Свежий бэкап самохоста: `systemctl show sfrfr-supabase-backup.service -p Result` на db-01
      (28.09.2026 00:30 UTC — `success`).
- [ ] Записать из Dashboard: регион проекта (Settings → General → Region) и тариф — нужны
      для письма в РКН (страна трансграничной передачи в период MVP) и для акта.

## 2. Удаление в консоли Supabase (владелец)

Скриншоты с датой и временем — в юридический архив (не в git): **С1–С6**.

1. Войти в [Supabase Dashboard](https://supabase.com/dashboard) под аккаунтом-владельцем проекта.
2. **С1.** Settings → General: имя проекта, ref `frualvycousvvyjivybu`, регион.
3. **С2.** Database → Backups: список бэкапов (что именно будет удалено).
4. **С3.** Storage: список бакетов и число объектов.
5. Settings → General → **Delete project** → ввести имя проекта → Delete
   ([документация](https://supabase.com/docs/guides/platform/delete-project)).
   Альтернатива: `supabase projects delete frualvycousvvyjivybu`.
6. **С4.** Список проектов организации без `frualvycousvvyjivybu` (дата и время на экране).
7. **С5.** Account → Access Tokens: отозвать personal access token, который лежит в
   `secrets/supabase-access.env` как `SUPABASE_ACCESS_TOKEN`; скрин списка после отзыва.
8. Если организация Supabase больше не нужна — удалить её и платёжные данные (Organization
   → Settings / Billing). **С6.**

Что отозвать и удалить у себя (только имена, значения не публиковать):

| Где | Что |
|---|---|
| `secrets/supabase-access.env` (локально) | `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF` — удалить файл после подтверждения удаления |
| VPS `/opt/sfrfr/.env`, `apps/*/.env` | Cloud-переменных уже нет (проверено 28.09) — повторить grep из 1.1 |
| GitHub Actions secrets | переменных Supabase нет (проверено 28.09) |
| Cursor: `%USERPROFILE%\.cursor\mcp.json`, плагин Supabase (`mcp.supabase.com`) | убрать `project_ref=frualvycousvvyjivybu`, отключить OAuth-подключение к Cloud |
| Менеджер паролей / заметки | старые `anon` / `service_role` ключи и пароль БД Cloud — удалить |

Ключи проекта (`anon`, `service_role`, пароль БД) Supabase аннулирует сам при удалении проекта.

## 3. Письмо в поддержку Supabase

Куда: [supabase.com/dashboard/support/new](https://supabase.com/dashboard/support/new)
(категория «Account / Billing» или «Other»), от аккаунта-владельца.

Что известно из официальных источников (проверено 28.09.2026):

- [Deleting your project](https://supabase.com/docs/guides/platform/delete-project):
  «We cannot recover deleted projects. All data, backups, and configurations are permanently
  removed». Срок, когда копии физически исчезают из инфраструктуры, не опубликован.
- [Database backups](https://supabase.com/docs/guides/platform/backups): при удалении проекта
  удаляются все связанные данные, включая бэкапы в S3.
- [DPA, п. 11.2 Deletion and Return](https://supabase.com/legal/dpa): после окончания договора
  Supabase хранит данные **30 дней** (Retention Period) для возврата по запросу, затем удаляет все
  копии, в т. ч. у субобработчиков.
- Сторонние блоги пишут о «grace period ~90 дней» — это не официальные данные, на них не ссылаться.

Поэтому просим письменно подтвердить удаление и дату, когда исчезнут последние копии.

```text
Subject: Confirmation of project deletion and backup destruction — project ref frualvycousvvyjivybu

Hello Supabase team,

We are the data controller for the project with reference ID frualvycousvvyjivybu
(organization: <FILL IN>). We deleted this project on <FILL IN: date, time UTC> via
Settings > General > Delete project.

To comply with personal data protection law (Russian Federal Law No. 152-FZ), we need
written confirmation of the following:

1. The project, its Postgres database, Auth data, Storage objects, Edge Functions and logs
   have been permanently deleted.
2. All backups and point-in-time recovery snapshots of this project, including copies held
   by your sub-processors, have been deleted, or the date by which they will be deleted.
3. Whether any copies are retained after deletion (for example, under the 30-day Retention
   Period in section 11.2 of your DPA, or in logs), for how long, and the exact date when
   the last copy will be destroyed.
4. The region where the project data and its backups were stored.

Please do not restore the project. We do not request a copy of the data.

Thank you,
<FILL IN: name, title>
OOO "POD PRISMOTROM"
```

Ответ Supabase (PDF или скрин тикета с номером) — в юрархив, номер тикета — в акт.

## 4. Акт об уничтожении ПДн (приказ РКН от 28.10.2022 № 179)

Источник: [приказ № 179](https://pravo.ppt.ru/prikaz/roskomnadzor/n-179-273960)
(действует с 01.03.2023 до 01.03.2029). Обработка была автоматизированной, поэтому
подтверждение = **акт** (п. 3) + **выгрузка из журнала** регистрации событий (п. 2, 5).
Если выгрузка не содержит сведений п. 5 — их вносят в акт (п. 6). Акт и выгрузку хранить
**3 года** с даты уничтожения (п. 8). Электронный акт — с подписью по 63-ФЗ (п. 4).

**Готовый акт хранить в юридическом архиве оператора, не в git.**

```text
АКТ № ЗАПОЛНИТЬ об уничтожении персональных данных

г. Ноябрьск                                                        «ЗАПОЛНИТЬ» ________ 2026 г.

1. Оператор (п. 3 «а»): ООО «ПОД ПРИСМОТРОМ», ИНН 8905066468, ОГРН 1208900000572;
   адрес: 629804, ЯНАО, г. Ноябрьск, ул. Рабочая, д. 109Б, кв. 4.

2. Лицо, обрабатывавшее ПДн по поручению оператора (п. 3 «б»): Supabase, Inc.;
   адрес: ЗАПОЛНИТЬ (из договора / DPA Supabase).

3. Субъекты, чьи ПДн уничтожены (п. 3 «в»): клиенты, пользователи личного кабинета и
   представители клиентов онлайн-сервиса «Проверка стажа», чьи записи находились в проекте
   `frualvycousvvyjivybu` на дату удаления. Перечень — в приложении 1 (ЗАПОЛНИТЬ: список
   идентификаторов клиентов / учётных записей, ЗАПОЛНИТЬ: количество).

4. Категории уничтоженных ПДн (п. 3 «д»): ЗАПОЛНИТЬ по фактическому составу, ориентир —
   ФИО; телефон; адрес электронной почты; идентификаторы пользователя, дела и MAX; сведения о
   входах; IP-адрес; сведения о браузере; сведения о трудовой деятельности и стаже; СНИЛС и
   сведения из ИЛС (если были загружены); копии документов в хранилище; переписка по делу;
   сведения о заказах и платежах.

5. Информационная система (п. 3 «ж»): ИСПДн онлайн-сервиса «Проверка стажа» — облачный проект
   Supabase `frualvycousvvyjivybu` (Postgres, Auth, Storage, резервные копии), регион ЗАПОЛНИТЬ.

6. Способ уничтожения (п. 3 «з»): удаление проекта средствами облачной платформы
   (Settings → General → Delete project), включая базу данных, учётные записи, объекты
   хранилища и резервные копии; отзыв ключей доступа. Подтверждение провайдера — тикет
   № ЗАПОЛНИТЬ от ЗАПОЛНИТЬ; дата удаления последних резервных копий по ответу провайдера —
   ЗАПОЛНИТЬ.

7. Причина уничтожения (п. 3 «и»): прекращение обработки ПДн в иностранном облачном сервисе
   после переноса в инфраструктуру на территории РФ (ч. 5 ст. 18 152-ФЗ); достижение цели
   хранения резервной копии для отката (перенос завершён 03.08.2026, данные сверены
   ЗАПОЛНИТЬ: дата сверки по разделу 1.2).

8. Дата уничтожения (п. 3 «к»): ЗАПОЛНИТЬ.

9. Лица, уничтожившие ПДн (п. 3 «г»):
   ЗАПОЛНИТЬ: должность ____________ ЗАПОЛНИТЬ: ФИО ____________ подпись ________
   ЗАПОЛНИТЬ: должность ____________ ЗАПОЛНИТЬ: ФИО ____________ подпись ________

Приложения:
1. Перечень субъектов (идентификаторы) — ЗАПОЛНИТЬ.
2. Выгрузка из журнала регистрации событий (п. 5 приказа № 179) — см. ниже.
3. Скриншоты С1–С6 и ответ поддержки Supabase.
```

**Выгрузка из журнала** должна содержать (п. 5): субъектов (ФИО или иную информацию о них),
категории ПДн, наименование ИСПДн, причину и дату уничтожения. Supabase не даёт журнала
событий по удалённому проекту, поэтому:

- до удаления сохранить скрин/экспорт журнала аудита организации Supabase
  (Organization → Audit logs, если доступно на тарифе) с событием удаления;
- приложение 1 сформировать из шага A раздела 1.2 (идентификаторы, без лишних ПДн);
- недостающие сведения п. 5 внести в сам акт (п. 6) — пункты 3–8 шаблона это покрывают.

## 5. После удаления

1. **Политика ПДн** (`docs/contracts/pdn-policy.md` + `scripts/assets/sfrfr-privacy.html`):
   убрать фразу про «ранее созданную техническую копию» в разделе 10 и п. 11.3; добавить строку
   в историю редакций. **Согласие** (`pdn-consent.md` + `sfrfr-consent.html`): абзаца об
   остаточной копии там нет — проверить и не менять. Версию согласия **не поднимать**
   (обработка сужается). После деплоя — обновить страницы WP на VPS.
2. **Письмо в РКН** (`docs/contracts/rkn-notification-2026-09.md`, п. 0 и п. 10): поле
   трансграничной передачи — «не осуществляется», указать дату удаления и номер тикета;
   период MVP — по решению юриста.
3. **Документы репо:** отметить шаг 7 в `docs/specs/15-data-localization-ru.md` и пункты в
   `supabase-cloud-drain-checklist.md`; строка в `docs/history/` (дата, номер тикета, без ПДн).
4. **Код:** отдельной задачей убрать или пометить устаревшими Cloud-утилиты из таблицы 1.1.
5. **Трекер:** комментарий в SFRFR-68 с датой удаления и номером тикета.
