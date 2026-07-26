# DNS: переход на proverkastaza.ru (reg.ru)

IP VPS: **`91.229.11.147`**  
NS: `ns1.reg.ru` / `ns2.reg.ru` (как у старого домена).

## Основной домен `proverkastaza.ru`

| Тип | Имя (хост) | Значение |
|-----|------------|----------|
| A | `@` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |
| A | `api` | `91.229.11.147` |
| A | `cabinet` | `91.229.11.147` |
| A | `admin` | `91.229.11.147` |

## Защитные домены (только редирект)

### `proverka-staza.ru`

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |

### `prostaz.ru`

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |

## Старый `taxi-doroga-dobra.ru`

Оставить A `@` / `www` / `api` / `cabinet` / `admin` на тот же IP — после cutover Apache отдаёт **301** на `proverkastaza.ru` (и поддомены API/кабинетов на новые имена).

## После DNS

Проверка с ПК:

```powershell
nslookup proverkastaza.ru
nslookup api.proverkastaza.ru
```

Должен быть `91.229.11.147`. Затем на VPS:

```bash
sudo bash /opt/sfrfr/scripts/vps_cutover_proverkastaza.sh
```

Или с ПК (если код ещё не на VPS): после `git push` дождаться deploy и выполнить скрипт по SSH.

## Ручные шаги после cutover

1. **MAX** → Чат-боты → «Стаж и пенсия» → URL мини-приложения: `https://proverkastaza.ru/app/`
2. **Supabase Auth** → Site URL / Redirect URLs: `https://cabinet.proverkastaza.ru/**` (см. `docs/ops/supabase-auth-redirects.md`)
3. Webhook: `sfrfr max-subscribe` (если `PUBLIC_BASE_URL` сменился)
