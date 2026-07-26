# Cutover: ручные хвосты после DNS/SSL

Автоматика (`vps_cutover_proverkastaza.sh`) обновляет Apache, WP `home`/`siteurl`, `.env` (`MAX_MINIAPP_URL`, `CABINET_PUBLIC_URL`, API URL). Ниже — то, что только в UI сторонних кабинетов.

Статус на 2026-07-26:

| Шаг | Статус | Где |
| --- | --- | --- |
| `.env` `MAX_MINIAPP_URL=https://proverkastaza.ru/app/` | ✅ VPS | `/opt/sfrfr/.env` |
| Статика `/app/` отдаёт 200 | ✅ | `https://proverkastaza.ru/app/` |
| URL mini-app в кабинете MAX | ⬜ вручную | business.max.ru |
| Supabase Auth redirect URLs | ⬜ вручную | Dashboard |
| reCAPTCHA Enterprise domains | ⬜ скрипт/консоль | GCP / `ops_patch_recaptcha_domains.py` |

---

## 1) MAX mini-app URL

API бота **не** меняет URL мини-приложения — только UI партнёра.

1. Открыть [платформу MAX для партнёров](https://business.max.ru/) → **Чат-боты** → бот «Стаж и пенсия» (`id8905998693_1_bot`).
2. **Расширенные настройки** → **Настроить**.
3. В поле URL вставить:

```text
https://proverkastaza.ru/app/
```

4. Сохранить. Проверка: в чате с ботом кнопка открытия mini-app грузит новый домен (не `taxi-doroga-dobra.ru`).

Диплинк лендинга без смены: `https://max.ru/id8905998693_1_bot?startapp`.

---

## 2) Supabase Auth redirects

Подробности: [supabase-auth-redirects.md](./supabase-auth-redirects.md).

Dashboard → проект `frualvycousvvyjivybu` → **Authentication** → **URL Configuration**:

- **Site URL:** `https://cabinet.proverkastaza.ru`
- **Additional Redirect URLs:**
  - `https://cabinet.proverkastaza.ru/**`
  - `https://cabinet.proverkastaza.ru/?mode=recover`
  - (временно) `https://cabinet.taxi-doroga-dobra.ru/**`

Проверка: «Забыли пароль» в кабинете → письмо → ссылка открывает recovery без ошибки redirect.

---

## 3) reCAPTCHA Enterprise allowlist

Ключ: `6Lf7UWMtAAAAANDXkb8MR9ufU8QYO9UwZsEC3NHu` (проект GCP `sfrfr-sheets`).

Добавить домены (минимум):

- `proverkastaza.ru`
- `www.proverkastaza.ru`

Опционально (если форма когда-то откроется с алиаса до редиректа): `prostaz.ru`, `www.prostaz.ru`, `proverka-staza.ru`, `www.proverka-staza.ru`.

Старый `taxi-doroga-dobra.ru` можно оставить до полного отказа от домена.

### Вариант A — скрипт на VPS

```bash
cd /opt/sfrfr
sudo -u sfrfr bash -lc '. .venv/bin/activate && set -a && . ./.env && set +a && python scripts/ops_patch_recaptcha_domains.py'
```

Нужны права SA на `recaptchaenterprise.keys.get/update`. Если PATCH 403 — Вариант B.

### Вариант B — Google Cloud Console

1. [reCAPTCHA Enterprise](https://console.cloud.google.com/security/recaptcha) → проект `sfrfr-sheets`.
2. Ключ `sfrpfr-site-key` / `6Lf7UWMt…`.
3. **Domains** → добавить `proverkastaza.ru` (+ www) → Save.

Проверка: отправить лид с формы на `https://proverkastaza.ru/` — тост WPForms без «ОШИБКА…»; в API нет reject по hostname/score из‑за чужого домена.
