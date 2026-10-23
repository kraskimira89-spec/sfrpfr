-- SFRFR-93: fiscal reconcile state on public.payments (additive only).
-- Design: docs/ops/design-sfrfr-93-fiscal-reconcile.md (rev12).

ALTER TABLE public.payments
  ADD COLUMN IF NOT EXISTS reconcile_attempts integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS reconcile_pre_error_streak integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_reconcile_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS reconcile_post_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS reconcile_post_payload jsonb NULL,
  ADD COLUMN IF NOT EXISTS reconcile_last_outcome text NULL,
  ADD COLUMN IF NOT EXISTS reconcile_alerted_at timestamptz NULL;

COMMENT ON COLUMN public.payments.reconcile_attempts IS
  'Increments only at POST create start (single UPDATE with post_at/payload).';
COMMENT ON COLUMN public.payments.reconcile_pre_error_streak IS
  'Consecutive error_before_post ticks; alert at >= 12; reset only after full fetch+list OK or POST start.';
COMMENT ON COLUMN public.payments.last_reconcile_at IS
  'Lease stamp (DB now()); overwritten every tick, never used as TTL anchor.';
COMMENT ON COLUMN public.payments.reconcile_post_at IS
  'Moment of POST create (DB now()); TTL anchor for Idempotence-Key; lease does not touch it.';
COMMENT ON COLUMN public.payments.reconcile_post_payload IS
  'Snapshot of first POST body (contains email/phone); NULL after succeeded or reset.';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'payments_reconcile_last_outcome_chk'
      AND conrelid = 'public.payments'::regclass
  ) THEN
    ALTER TABLE public.payments
      ADD CONSTRAINT payments_reconcile_last_outcome_chk CHECK (
        reconcile_last_outcome IS NULL OR reconcile_last_outcome IN (
          'error_before_post', 'post_started', 'unknown_after_post',
          'canceled', 'succeeded', 'pending', 'rejected',
          'skip_reg', 'skip_pending'
        )
      );
  END IF;
END $$;

-- Lease / TTL / alert claim: только now() базы (не Python).

CREATE OR REPLACE FUNCTION public.try_fiscal_reconcile_lease(
  p_payment_id uuid,
  p_lease_secs integer DEFAULT 120
)
RETURNS SETOF public.payments
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.payments
  SET last_reconcile_at = now()
  WHERE id = p_payment_id
    AND (
      last_reconcile_at IS NULL
      OR last_reconcile_at < now() - make_interval(secs => p_lease_secs)
    )
  RETURNING *;
$$;

CREATE OR REPLACE FUNCTION public.fiscal_reconcile_ttl_alive(
  p_payment_id uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT (
    reconcile_post_at IS NOT NULL
    AND now() - reconcile_post_at < interval '24 hours' - interval '15 minutes'
  )
  FROM public.payments
  WHERE id = p_payment_id;
$$;

CREATE OR REPLACE FUNCTION public.mark_fiscal_reconcile_post_started(
  p_payment_id uuid,
  p_attempts integer,
  p_payload jsonb
)
RETURNS SETOF public.payments
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.payments
  SET
    reconcile_attempts = p_attempts,
    reconcile_pre_error_streak = 0,
    reconcile_post_at = now(),
    reconcile_post_payload = p_payload,
    reconcile_last_outcome = 'post_started'
  WHERE id = p_payment_id
  RETURNING *;
$$;

CREATE OR REPLACE FUNCTION public.claim_fiscal_reconcile_alert(
  p_payment_id uuid
)
RETURNS SETOF public.payments
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.payments
  SET reconcile_alerted_at = now()
  WHERE id = p_payment_id
    AND reconcile_alerted_at IS NULL
  RETURNING *;
$$;

GRANT EXECUTE ON FUNCTION public.try_fiscal_reconcile_lease(uuid, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.fiscal_reconcile_ttl_alive(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.mark_fiscal_reconcile_post_started(uuid, integer, jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_fiscal_reconcile_alert(uuid) TO service_role;
