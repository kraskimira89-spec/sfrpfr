-- Идемпотентность POST кабинета и dedupe ответов бота.

alter table public.case_messages
  add column if not exists client_message_id uuid,
  add column if not exists reply_to_message_id uuid references public.case_messages (id) on delete set null;

create unique index if not exists case_messages_client_message_id_uidx
  on public.case_messages (case_id, client_message_id)
  where client_message_id is not null;

create unique index if not exists case_messages_bot_reply_to_uidx
  on public.case_messages (reply_to_message_id)
  where author_kind = 'system' and reply_to_message_id is not null;
