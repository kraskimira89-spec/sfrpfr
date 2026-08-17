Прямой Postgres :5433 (bypass Supavisor) для dbt с app-VPS 91.229.11.147.

Канон:
  cd /opt/sfrfr-supabase/supabase/docker
  COMPOSE_FILE в .env уже включает docker-compose.sfrfr-direct-pg.yml
  supabase-db: 0.0.0.0:5433->5432
  supabase-pooler: host :5432 (не трогать)

При любом обновлении Compose:
  cd /opt/sfrfr-supabase/supabase/docker && docker compose up -d
  (не только pull). Проверять 5433 в docker ps.

Нельзя:
  docker compose -f docker-compose.yml up   # без override снимет :5433
  публиковать db как 5432:5432 (конфликт с pooler)
  открывать 5432/5433/8000/22 в 0.0.0.0/0
  docker compose down всего стека без нужды (уронит supabase.proverkastaza.ru)

Reboot ВМ: отдельного systemd для Compose нет; контейнеры RestartPolicy=unless-stopped
(Docker сам поднимает с теми же PortBindings).
