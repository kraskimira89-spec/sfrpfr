-- Синтетические данные для staging (ТЗ-15 фаза 1). НЕ прод-ПДн.
-- Идемпотентно: фиксированные UUID.

insert into public.clients (id, full_name, phone, email, preferred_channel)
values
  (
    '11111111-1111-1111-1111-111111111111',
    'SYNTH Client One',
    '+70000000001',
    'synth.client1@example.invalid',
    'web_cabinet'
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'SYNTH Client Two',
    '+70000000002',
    'synth.client2@example.invalid',
    'max_miniapp'
  )
on conflict (id) do update set
  full_name = excluded.full_name,
  phone = excluded.phone,
  email = excluded.email;

insert into public.cases (
  id, client_id, pipeline_status, b2c_status, segment, region_bucket, problem_type
)
values
  (
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'intake',
    'lead',
    'synth',
    'RU-TEST',
    'staging_seed'
  ),
  (
    '44444444-4444-4444-4444-444444444444',
    '22222222-2222-2222-2222-222222222222',
    'intake',
    'lead',
    'synth',
    'RU-TEST',
    'staging_seed'
  )
on conflict (id) do update set
  pipeline_status = excluded.pipeline_status,
  b2c_status = excluded.b2c_status;

-- Мини-проверка RLS: anon не должен видеть строки без политики (ожидаем 0 для anon — проверяется отдельно).
select 'seed_ok' as status,
  (select count(*) from public.clients where full_name like 'SYNTH %') as synth_clients,
  (select count(*) from public.cases where problem_type = 'staging_seed') as synth_cases;
