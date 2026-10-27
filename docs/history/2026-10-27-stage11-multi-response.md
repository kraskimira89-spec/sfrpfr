# 2026-10-27 — ступень 11: несколько входящих ответов

- PR: https://github.com/kraskimira89-spec/sfrpfr/pull/364 (squash merge)
- Миграция `20261027210000_case_response_reviews_respondent.sql` (`respondent`, `response_kind`)
- Handoff ст.10 → auto-register review `handoff:{document_id}`
- Admin: матрица подача↔ответ, upload с органом, `agency_response`
- AI/Word нейтральные («входящий ответ органа»), package_summary по связанной подаче
- Deploy-vps: success; DDL — применить на БД отдельно (`vm_supabase_apply_migrations.sh` / psql), локальный туннель был недоступен
- Ручная приёмка: 2 подачи × ответ СФР + архив
