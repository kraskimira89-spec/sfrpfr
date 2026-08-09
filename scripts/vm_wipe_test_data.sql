-- Очистка тестовых ПДн для нового QA. staff_roles и admin auth.user сохраняются.
BEGIN;

TRUNCATE TABLE public.access_audit CASCADE;
TRUNCATE TABLE public.clients CASCADE;
-- cascades: cases, consents, documents, checklist, orders, payments, messages, …

DELETE FROM auth.refresh_tokens;
DELETE FROM auth.sessions;
DELETE FROM auth.mfa_challenges;
DELETE FROM auth.one_time_tokens;
DELETE FROM auth.identities
 WHERE user_id NOT IN (SELECT user_id FROM public.staff_roles WHERE user_id IS NOT NULL);
DELETE FROM auth.users
 WHERE id NOT IN (SELECT user_id FROM public.staff_roles WHERE user_id IS NOT NULL);

COMMIT;

SELECT 'clients' AS t, count(*)::int AS c FROM public.clients
UNION ALL SELECT 'cases', count(*)::int FROM public.cases
UNION ALL SELECT 'checklist_items', count(*)::int FROM public.checklist_items
UNION ALL SELECT 'consents', count(*)::int FROM public.consents
UNION ALL SELECT 'staff_roles', count(*)::int FROM public.staff_roles
UNION ALL SELECT 'auth.users', count(*)::int FROM auth.users;
