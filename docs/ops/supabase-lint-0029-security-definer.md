# Lint 0029 — SECURITY DEFINER и Data API

## Симптом

Security Advisor / Database Linter:

`authenticated_security_definer_function_executable` на

- `public.can_access_case`
- `public.is_case_client`
- `public.is_case_representative`
- `public.is_case_staff`

Смысл: роль `authenticated` может вызвать `SECURITY DEFINER` через `/rest/v1/rpc/…`.

Studio «Exposed functions: 0 of 6» **не отменяет** этот риск: PostgREST смотрит на schema + `EXECUTE`, а не на UI-тогглы.

## Правильный фикс (сделано)

Хелперы для RLS перенесены в **неэкспонируемую** schema `private` (как уже был `private.is_staff`):

`supabase/migrations/20260902163000_private_case_access_helpers.sql`

- RLS продолжает вызывать функции (по OID / `private.*`).
- Data API schemas = `public` (+ graphql) → `/rpc/can_access_case` → **404 PGRST202**.
- `EXECUTE` у `authenticated` оставлен — нужен для выражений в политиках.
- `anon` без `EXECUTE`.

Новые политики писать так: `using (private.can_access_case(case_id))`, **не** `public.*`.

## Что не делать

- Не переводить эти хелперы в `SECURITY INVOKER` без переписывания RLS (риск рекурсии / отказ доступа).
- Не возвращать обёртки в `public` «для удобства RPC».
- Не полагаться только на «Exposed functions» в Studio.

## Связанное замечание по Studio

«Automatically expose new tables» = ON увеличивает поверхность API для новых таблиц в exposed schemas. Для продакшена лучше OFF + явные GRANTs (см. `supabase/config.toml` `auto_expose_new_tables`).
