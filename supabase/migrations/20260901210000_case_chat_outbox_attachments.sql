-- Кнопки системных сообщений общего чата доставляются через тот же outbox.

alter table public.case_chat_outbox
  add column if not exists attachments jsonb not null default '[]'::jsonb;

create unique index if not exists case_chat_outbox_message_uidx
  on public.case_chat_outbox (message_id)
  where message_id is not null;

-- Сообщение и запись доставки создаются одной транзакцией базы.
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
    on conflict (message_id) do nothing;
  end if;

  return new;
end;
$$;

revoke all on function private.enqueue_case_chat_outbox() from public, anon, authenticated;
grant execute on function private.enqueue_case_chat_outbox() to service_role;

drop trigger if exists case_messages_enqueue_max on public.case_messages;
create trigger case_messages_enqueue_max
after insert on public.case_messages
for each row
execute function private.enqueue_case_chat_outbox();
