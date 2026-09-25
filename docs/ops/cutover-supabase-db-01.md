# Cutover: `supabase.proverkastaza.ru` → ВМ `sfrfr-supabase-db-01`

**Дата плана:** 2026-09-25  
**Новая ВМ:** `sfrfr-supabase-db-01` (`fhmkkkr7if3ggu6h29uq`)  
**Каталог:** `b1grtprgfugidt9u073i`  
**Публичный IP:** `51.250.69.237` · внутренний `10.70.20.26`  
**SG:** `enpf27it4pe5d1brj6as` (`sfrfr-supabase-db-sg`)  
**Старый IP (DNS сейчас):** `51.250.13.240` (каталог `b1g0mhpm9tr4lrurk1bu` — без доступа, не трогаем)

DNS зоны `proverkastaza.ru` — **reg.ru**, не Yandex Cloud.

## Блокер (факт 2026-09-25)

В SG сейчас только:

| INGRESS | Порт | CIDR |
|---------|------|------|
| TCP | 22 | `146.158.1.12/32` |

**Нет** 80/443 снаружи → cutover DNS бесполезен, пока не открыть HTTPS.  
Postgres 5432/5433 в интернет **не** открывать.

Текущий IP админа с рабочей станции (пример): `185.77.216.28` — **не** совпадает с `146.158.1.12` → SSH с этой сети не пройдёт, пока не добавить `/32` в SG.

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

## Шаг 3 — DNS (reg.ru)

1. DNS-зона `proverkastaza.ru` → A `supabase`.
2. Было: `51.250.13.240` → стало: **`51.250.69.237`**.
3. Проверка: `nslookup supabase.proverkastaza.ru 8.8.8.8`
4. `curl -I https://supabase.proverkastaza.ru`

## Шаг 4 — Smoke

- [ ] Cabinet login (OTP / magic link)
- [ ] API health на VPS (`SUPABASE_URL` остаётся `https://supabase.proverkastaza.ru`)
- [ ] При необходимости обновить SG/allowlist Postgres на новый IP для VPS

## Шаг 5 — После 24–72 ч

- Stop старой ВМ `51.250.13.240` (когда будет доступ к каталогу `b1g0mhpm…`)
- Обновить `docs/ops/infrastructure-inventory.md`

## Запрещено

- Открывать Postgres в интернет
- Менять DNS до рабочего HTTPS на `51.250.69.237`
- Трогать Lockbox / каталог `b1g0mhpm9tr4lrurk1bu` без владельца `sfrfr-ai`
