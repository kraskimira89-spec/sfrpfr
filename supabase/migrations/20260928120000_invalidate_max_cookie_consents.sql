-- Отметки cookies-site-2026-09-22, записанные кнопкой «Начать» в MAX (до PR #115),
-- не являются согласием на cookies: отдельного выбора клиент не делал.
-- Ничего не удаляем: помечаем недействительными. Повторный запуск ничего не меняет.
alter table public.consents
  add column if not exists invalidated_at timestamptz,
  add column if not exists invalidated_reason text;

alter table public.clients
  add column if not exists cookie_consent_invalidated_at timestamptz,
  add column if not exists cookie_consent_invalidated_reason text;

-- Сервер писал эти строки без IP и без source (_ensure_cookie_consent_row).
update public.consents
set invalidated_at = now(),
    invalidated_reason = 'записано кнопкой Начать в MAX без отдельного выбора (до PR #115)'
where version = 'cookies-site-2026-09-22'
  and ip is null
  and invalidated_at is null;

update public.clients
set cookie_consent_invalidated_at = now(),
    cookie_consent_invalidated_reason = 'записано кнопкой Начать в MAX без отдельного выбора (до PR #115)'
where cookie_consent_version = 'cookies-site-2026-09-22'
  and cookie_consent_invalidated_at is null;

comment on column public.consents.invalidated_at is
  'Когда отметка признана недействительной (строка сохраняется как история)';
comment on column public.consents.invalidated_reason is
  'Почему отметка недействительна';
comment on column public.clients.cookie_consent_version is
  'Версия согласия на cookies сайта; только отдельный выбор посетителя, не кнопка «Начать» в MAX (с PR #115)';
comment on column public.clients.cookie_consent_accepted_at is
  'Когда посетитель отдельно принял cookies сайта; при заполненном cookie_consent_invalidated_at — недействительно';
comment on column public.clients.cookie_consent_invalidated_at is
  'Когда отметка cookie-согласия признана недействительной (значения не стираются)';
comment on column public.clients.cookie_consent_invalidated_reason is
  'Почему отметка cookie-согласия недействительна';
