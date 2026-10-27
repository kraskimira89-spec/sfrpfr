-- Один активный/оплаченный DOCS (ACCOMP ≤ 6500 ₽) на дело.
-- Гонка двух POST /orders не создаёт два счёта (как payments_one_active_per_order).
-- Канон суммы: funnel_board._DOCS_AMOUNT_MAX = 6500.

do $$
begin
  if exists (
    select 1
    from public.orders
    where upper(coalesce(package_code, '')) = 'ACCOMP'
      and coalesce(amount_rub, 0) > 0
      and coalesce(amount_rub, 0) <= 6500
      and lower(coalesce(status, '')) not in ('cancelled', 'canceled', 'refunded')
    group by case_id
    having count(*) > 1
  ) then
    raise exception
      'Cannot create orders_one_open_docs_per_case_uidx: duplicate open/paid DOCS orders exist';
  end if;
end
$$;

create unique index if not exists orders_one_open_docs_per_case_uidx
  on public.orders (case_id)
  where upper(coalesce(package_code, '')) = 'ACCOMP'
    and coalesce(amount_rub, 0) > 0
    and coalesce(amount_rub, 0) <= 6500
    and lower(coalesce(status, '')) not in ('cancelled', 'canceled', 'refunded');

comment on index public.orders_one_open_docs_per_case_uidx is
  'Не больше одного открытого или оплаченного DOCS (ACCOMP≤6500) на case_id';
