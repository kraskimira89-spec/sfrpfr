-- SFRFR-93: fiscal reconcile state on public.payments (additive only).
-- Design: docs/ops/design-sfrfr-93-fiscal-reconcile.md (rev11).

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
  'Consecutive error_before_post ticks; alert at >= 12; reset on POST start / full successful pre-POST pass.';
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
