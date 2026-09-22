-- Один active payment на заказ (follow-up к B1).
--
-- Инвариант: для одного order_id существует не более одного платежа
-- в нетерминальном статусе (pending и т.п.). Гарантия уровня БД:
-- два конкурентных POST /pay физически не смогут оба захватить слот.
--
-- Порядок применения важен:
--   1) created_at — колонка, которую уже читает find_active_payment();
--   2) preflight активных дублей — миграция падает с понятной ошибкой,
--      а не молча не создаёт индекс;
--   3) partial unique index — атомарная гарантия.
-- Очистку существующих данных миграция не выполняет.

alter table public.payments
  add column if not exists created_at timestamptz not null default now();

comment on column public.payments.created_at is
  'Момент создания записи платежа; используется для упорядочивания платежей заказа';

-- Preflight: при наличии активных дублей индекс не создать — падаем явно.
do $$
begin
  if exists (
    select 1
    from public.payments
    where lower(coalesce(status, '')) not in
      ('succeeded', 'paid', 'canceled', 'cancelled', 'failed', 'expired', 'refunded')
    group by order_id
    having count(*) > 1
  ) then
    raise exception
      'Cannot create payments_one_active_per_order_uidx: active payment duplicates exist';
  end if;
end
$$;

create unique index if not exists payments_one_active_per_order_uidx
  on public.payments (order_id)
  where lower(coalesce(status, '')) not in
    ('succeeded', 'paid', 'canceled', 'cancelled', 'failed', 'expired', 'refunded');
