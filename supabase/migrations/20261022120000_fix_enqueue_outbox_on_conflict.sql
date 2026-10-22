-- Fix 42P10: ON CONFLICT (message_id) must include the partial unique index predicate.
-- Index: case_chat_outbox_message_uidx ON (message_id) WHERE message_id IS NOT NULL
-- Without WHERE, INSERT into case_messages (channel_origin cabinet/admin/bot) fails
-- in trigger private.enqueue_case_chat_outbox → pay/cabinet messages missing from timeline.

create or replace function private.enqueue_case_chat_outbox()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  target_max_user_id text;
begin
  if new.channel_origin not in ('cabinet', 'admin', 'bot')
     or new.body like '[[internal]]%'
     or new.body like '[Документ] %'
  then
    return new;
  end if;

  select cl.max_user_id
    into target_max_user_id
    from public.cases ca
    join public.clients cl on cl.id = ca.client_id
   where ca.id = new.case_id;

  if nullif(trim(target_max_user_id), '') is not null then
    insert into public.case_chat_outbox (
      case_id,
      message_id,
      max_user_id,
      body
    )
    values (
      new.case_id,
      new.id,
      trim(target_max_user_id),
      new.body
    )
    on conflict (message_id) where message_id is not null do nothing;
  end if;

  return new;
end;
$$;

revoke all on function private.enqueue_case_chat_outbox() from public, anon, authenticated;
grant execute on function private.enqueue_case_chat_outbox() to service_role;
