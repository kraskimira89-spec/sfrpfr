# Cutover: `supabase.proverkastaza.ru` → ВМ `sfrfr-supabase-db-01`

**Дата плана:** 2026-09-25  
**Новая ВМ:** `sfrfr-supabase-db-01` (`fhmkkkr7if3ggu6h29uq`)  
**Каталог:** `b1grtprgfugidt9u073i`  
**Публичный IP:** `51.250.69.237` · внутренний `10.70.20.26`  
**SG:** `enpf27it4pe5d1brj6as` (`sfrfr-supabase-db-sg`)  
**Старый IP (DNS сейчас):** `51.250.13.240` (каталог `b1g0mhpm9tr4lrurk1bu` — без доступа, не трогаем)

DNS зоны `proverkastaza.ru` — **reg.ru**, не Yandex Cloud.

## Статус SG (2026-09-25) — ✅ сделано

| INGRESS | Порт | CIDR | Статус |
|---------|------|------|--------|
| TCP | 22 | `146.158.1.12/32` | было |
| TCP | 22 | `185.77.216.28/32` | добавлено; **удалено 2026-09-26** (выход VPN Creanova, см. `docs/history/2026-09-25-yc-sg-ssh-cleanup.md`) |
| TCP | 22 | `91.229.11.147/32` | добавлено 2026-09-26 (запасной вход через App-VPS) |
| TCP | 443 | `0.0.0.0/0` | добавлено |
| TCP | 80 | `0.0.0.0/0` | добавлено |

Postgres 5432/5433/8000 в интернет **не** открыты (правильно).

## Статус доступа / переноса (2026-09-25)

- ✅ SSH на **новую** `sfrfr-supabase-db-01` (`51.250.69.237`) и на **старую** `sfrfr-staging-supabase` (`51.250.13.240`) с ключом агента.
- ✅ Стек скопирован и поднят на новой ВМ: Kong, DB, Auth, Storage, **Caddy** (80/443 слушают).
- ✅ Swap 4 GiB добавлен (RAM ВМ 3.8 GiB — впритык).
- ⏳ DNS `supabase.proverkastaza.ru` всё ещё → `51.250.13.240` → Let's Encrypt на новой ВМ **ещё не выдан** (challenge ходит на старый IP).
- ❌ Браузерный доступ к старому каталогу не нужен для cutover (перенос сделан через SSH/SA).

**Следующий шаг владельца:** в reg.ru A `supabase` → **`51.250.69.237`**, подождать DNS + LE, smoke `curl -I https://supabase.proverkastaza.ru`. Старую ВМ не гасить 24–72 ч.

## Шаг 1 — Security Group (Yandex Cloud)

В `sfrfr-supabase-db-sg` добавить INGRESS (как в `infra/yandex-cloud/security-groups.tf`):

| Протокол | Порт | CIDR | Зачем |
|----------|------|------|-------|
| TCP | 443 | `0.0.0.0/0` | HTTPS / Kong / Caddy |
| TCP | 80 | `0.0.0.0/0` | HTTP → HTTPS, Let's Encrypt ACME |
| TCP | 22 | `<ваш_публичный_ip>/32` | SSH (дополнить к existing, не `0.0.0.0/0`) |

**Не добавлять:** 5432, 5433, 8000 (Studio) в `0.0.0.0/0`.

Опционально позже: 5433 только с `91.229.11.147/32` (app-VPS) для dbt/`DATABASE_URL`.

## Шаг 2 — SSH-проверка стека

С IP из allowlist:

```bash
ssh <user>@51.250.69.237

docker --version; docker compose version
docker ps -a
sudo ss -tlnp | grep -E ':443|:80|:5432|:5433'
sudo find /opt /srv /data /root -maxdepth 3 -name 'docker-compose*.yml' 2>/dev/null
ls -la /data 2>/dev/null; du -sh /data 2>/dev/null
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health
```

Снаружи (после открытия 443):

```powershell
curl.exe -vk https://51.250.69.237/ --max-time 10
```

Если стека нет — **не** менять DNS; сначала поднять Compose + Caddy (`PROXY_DOMAIN=supabase.proverkastaza.ru`), те же JWT/ключи, что в проде.

## Порядок cutover (ACME / DNS)

**Не** менять DNS, пока на ВМ нет слушателя на 80/443 (иначе простой без пользы).

1. **SSH / serial console** — стек up: `docker ps`, `ss` показывает `:80`/`:443` (хотя бы локально).
2. Caddy (или аналог) сконфигурирован на `supabase.proverkastaza.ru`, секреты/JWT как в проде.
3. **reg.ru:** A `supabase` → `51.250.69.237`.
4. Дождаться DNS (`dig`/`nslookup` → новый IP).
5. Caddy сам запросит LE по **HTTP-01** (нужны открытые 80+443) — обычно минуты.
6. Smoke: `curl -I https://supabase.proverkastaza.ru`, cabinet OTP.

Альтернатива без окна «DNS уже новый, а cert ещё нет»: **DNS-01** challenge (API reg.ru / TXT) — сертификат до смены A. Для текущего Caddy-стека обычно достаточно HTTP-01 после шага 3.

**Окно простоя:** с момента смены A до выдачи cert HTTPS на домене может кратко отдавать ошибку TLS — держать TTL низким, cutover в спокойное время.


## Шаг 4 — Smoke

- [ ] Cabinet login (OTP / magic link)
- [ ] API health на VPS (`SUPABASE_URL` остаётся `https://supabase.proverkastaza.ru`)
- [ ] При необходимости обновить SG/allowlist Postgres на новый IP для VPS

## Шаг 5 — После 24–72 ч

- Stop старой ВМ `51.250.13.240` (когда будет доступ к каталогу `b1g0mhpm…`)
- Обновить `docs/ops/infrastructure-inventory.md`

## Запрещено

- Открывать Postgres в интернет
- Менять DNS до того, как на ВМ есть слушатель 80/443 и поднят Compose/Caddy
- Трогать Lockbox / каталог `b1g0mhpm9tr4lrurk1bu` без владельца `sfrfr-ai`
