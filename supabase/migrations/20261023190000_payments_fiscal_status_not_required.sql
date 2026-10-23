-- SFRFR-93: fiscal_status='not_required' — чек не нужен (smoke/1₽/чужой контур).
-- Предфильтр reconcile исключает registered + not_required (см. FISCAL_STATUS_OR).

ALTER TABLE public.payments
  DROP CONSTRAINT IF EXISTS payments_fiscal_status_chk;

ALTER TABLE public.payments
  ADD CONSTRAINT payments_fiscal_status_chk
  CHECK (
    (fiscal_status IS NULL)
    OR (
      fiscal_status = ANY (
        ARRAY[
          'registered'::text,
          'pending'::text,
          'not_required'::text
        ]
      )
    )
  );

COMMENT ON COLUMN public.payments.fiscal_status IS
  'registered = чек есть; pending = в полёте; not_required = чек не нужен '
  '(smoke/тест/не наш shop); NULL = неизвестно, кандидат reconcile';
