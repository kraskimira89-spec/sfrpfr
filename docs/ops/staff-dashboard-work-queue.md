# Дашборд сотрудника: рабочая очередь

Первый экран кабинета — не сводка счётчиков, а очередь дел.

## Что видит сотрудник

- Карточки: ответ, дедлайн сегодня, новые, документы, оплата, риск SLA.
- «Мои задачи сегодня» и таблица «Рабочая очередь».
- «Контроль сроков ответа»: просрочено / час / сегодня / ждём внешнего / пауза.
- Ожидание архива, СФР или документов клиента **не** считается «без ответа».
- Эксперт видит свои дела, оператор и админ — все.

## Поля дела

Миграция `supabase/migrations/20260822180000_cases_next_action.sql`:

- `next_action` — текст следующего шага;
- `next_action_at` — срок;
- `waiting_on` — `staff` / `client` / `archive` / `sfr` / `payment` / `none`.

Если поля пустые, кабинет считает шаг и ожидание по этапу, чек-листу и счетам.

## Применить миграцию

На self-host Postgres (после деплоя кода):

```bash
bash scripts/vm_supabase_apply_migrations.sh
```

Без миграции дашборд всё равно строится из текущих статусов; сохранение шага в карточке заработает после колонок.

## Реестр дел

Таблица с приоритетом, следующим шагом и сроком. Тестовые записи (`is_test` или имя вроде «Тест Клиент AMO») скрыты, пока не выбран фильтр «Тестовые».

Подсказка шага: DeepSeek V4 Flash в Yandex AI Studio, в модель уходят только обезличенные этап/чек-лист, не ФИО и телефон.

Миграция флага: `supabase/migrations/20260822183000_cases_is_test.sql`.

## Rollback

1. Откатить коммит UI/API (`git revert`) и дождаться `deploy-vps`.
2. Колонки можно оставить: код читает их опционально.
3. Если нужно убрать схему:

```sql
alter table public.cases drop column if exists is_test;
alter table public.cases drop column if exists next_action;
alter table public.cases drop column if exists next_action_at;
alter table public.cases drop constraint if exists cases_waiting_on_check;
alter table public.cases drop column if exists waiting_on;
```
