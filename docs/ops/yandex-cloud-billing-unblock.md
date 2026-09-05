# Яндекс.Облако: разблокировка биллинга (AI Studio / ресурсы)

**Организация / облака (создано 2026-07-28; live-проверка 2026-09-02):**

| Облако | ID | Статус |
|--------|-----|--------|
| **`sfrfr-ai`** (рабочее) | `b1gkscu5sqpjtf5d5rbi` | ✅ существует; каталог `default` ACTIVE; VM staging RUNNING |
| `cloud-infoproverkastazaru` | — | старое; не основное |

**Каталоги (важно: два folder_id):**

| Каталог / роль | `folder_id` |
|----------------|-------------|
| **`default`** в billing/Terraform-доках | `b1g0mhpm9tr4lrurk1bu` |
| **Рабочий LLM / AI Studio ключ** (smoke, `secrets/yandexAI_studio.env`) | `b1gp3rqkf5t6kqmqaf7c` |

### Folder mismatch (зафиксировано 2026-09-05)

- Billing-runbook и ссылки консоли часто указывают на `default` → `b1g0mhpm9tr4lrurk1bu` (инфра / staging VM).
- API-ключ LLM выпущен в другом каталоге → `b1gp3rqkf5t6kqmqaf7c` (комментарий в secrets, без самого ключа).
- Runtime: `YANDEX_FOLDER_ID` / URI `gpt://…` должны совпадать с каталогом **ключа**, иначе 403/не тот ресурс.
- Не подставлять `b1g0mhpm9tr4lrurk1bu` в LLM `.env` «по умолчанию из этого файла» без проверки, где выпущен ключ.

## Не вижу облако / «нет доступа к каталогу»

Облако **не удалено**. Live (2026-09-02): каталог `default` ACTIVE, VM `sfrfr-staging-supabase` RUNNING.

### Диагноз со скрина (403 на folder)

Сообщение *«У вас нет доступа к объектам в данном каталоге»* при открытии  
https://console.yandex.cloud/folders/b1g0mhpm9tr4lrurk1bu  
под именем **«Проверка Стажа»** значит:

| Факт | Значение |
|------|----------|
| Организация Cloud | `proverkastaza` (`bpf25prvoq8uqqlvujim`), title «Проверка стажа» |
| Логин на скрине | скорее `proverkastaza@yandex.ru` (userAccount `ajeofnteq3gl1j2rsai5`) |
| Права на каталоге | у **людей** нет; только SA (`sfrfr-terraform`, `sfrfr-ai-studio`, …) |
| Почему CLI не чинит | `add-access-binding` → *User must be a member of organization* |

**Вывод:** `proverkastaza@yandex.ru` **не состоит** в организации Cloud `proverkastaza`.  
Владелец организации — **другой** Яндекс ID (личный, которым создавали Cloud 2026-07-28 / биллинг).

### Что сделать

**Вариант A — войти владельцем организации (быстро)**

1. Выйти из консоли / сменить пользователя (не «Проверка Стажа» Workspace).
2. Войти **личным** Яндекс ID, с которого заводили Yandex Cloud / платёжный аккаунт.
3. Открыть снова: https://console.yandex.cloud/folders/b1g0mhpm9tr4lrurk1bu  
4. Если открылось — в организации → **Пользователи** → пригласить `proverkastaza@yandex.ru` (роль admin / editor).
5. После принятия приглашения — снова войти как `proverkastaza` и обновить страницу.

**Вариант B — не помните владельца**

- Почта: письма от `cloud.yandex.ru` / биллинга за июль 2026 («облако создано», счёт).
- [Биллинг](https://console.yandex.cloud/billing) под каждым вашим Яндекс ID — у кого виден платёжный аккаунт, привязанный к `sfrfr-ai`.
- Поддержка Cloud: org id `bpf25prvoq8uqqlvujim`, cloud `b1gkscu5sqpjtf5d5rbi`, folder `b1g0mhpm9tr4lrurk1bu` (инфра) или LLM-folder `b1gp3rqkf5t6kqmqaf7c`.

### Прямые ссылки

1. Каталог (инфра `default`): https://console.yandex.cloud/folders/b1g0mhpm9tr4lrurk1bu  
2. Каталог (LLM / AI Studio ключ): https://console.yandex.cloud/folders/b1gp3rqkf5t6kqmqaf7c  
3. Облако: https://console.yandex.cloud/cloud?id=b1gkscu5sqpjtf5d5rbi  

> Workspace (`proverkastaza@…` почта/Диск) ≠ членство в **организации Yandex Cloud**. Это разные контуры.

> Это **не** Яндекс Workspace (почта/Диск/Календарь/Телемост) — OAuth ТЗ-14 живёт отдельно.

---

## Сделано (обновлено 2026-09-05)

- [x] Облако/каталог для AI: `sfrfr-ai`; инфра `default` (`b1g0mhpm9tr4lrurk1bu`); LLM-ключ в `b1gp3rqkf5t6kqmqaf7c`
- [x] Биллинг разблокирован **по API-доказательствам** (после пополнения): локальный smoke LLM OK; prod `ops_llm_enabled=yes`
- [ ] Баннер «Облако заблокировано» в UI консоли — **владелец: подтвердить в консоли** (в этой сессии UI не проверяли)
- [x] SA + API-ключ работают (ключ в secrets / VPS; значение не в git)

---

## Биллинг (справка)

Каталоги готовы. Раньше блокер был жёлтый баннер / баланс 0 ₽.

### Вариант A — пополнить (нужен для AI Studio)

1. В шапке — баланс или [Биллинг](https://console.yandex.cloud/billing).
2. Платёжный аккаунт, привязанный к облаку **`sfrfr-ai`** (и при необходимости к старому `cloud-infoproverkastazaru`).
3. Статус не `SUSPENDED` / не «заблокирован».
4. Пополнить (даже небольшая сумма).
5. Обновить главную: баннер «Облако заблокировано» исчез, замок у `sfrfr-ai` пропал.

📖 [Биллинг](https://yandex.cloud/ru/docs/billing/) · [Проблемы с платежами](https://yandex.cloud/ru/docs/billing/qa/billing-account)

### Вариант B — грант (опционально)

Только если нужен грант миграции. Иначе вкладку закрыть.  
Грант **не заменяет** активный биллинг для API.

---

## После снятия блока — шаг 1 (AI Studio ключ)

Рабочий LLM-каталог: `folder_id=b1gp3rqkf5t6kqmqaf7c` (не путать с инфра-`default`).

1. В каталоге ключа → **IAM** → **Сервисные аккаунты**.
2. SA с ролью `ai.languageModels.user` (уже есть для текущего ключа).
3. **API-ключ** со scope `yc.ai.languageModels.execute`.
4. Ключ **не** в чат / **не** в git → в `.env` / VPS:
   - `YANDEX_FOLDER_ID=<folder ключа>` (сейчас `b1gp3rqkf5t6kqmqaf7c`)
   - `YANDEX_API_KEY=…`
   - при необходимости те же в `LLM_FOLDER_ID` / `LLM_API_KEY`
5. Канон модели: DeepSeek в AI Studio (`deepseek-v4-flash`), см. `src/sfrfr/ai/llm.py` — не dual-model YandexGPT Pro.

Кнопка **«Перейти в AI Studio»** — шаг 2 (тест в UI), когда ключ уже есть.

---

## Чеклист (2026-09-05)

- [x] Каталог `default` (инфра) в `sfrfr-ai` зафиксирован: `b1g0mhpm9tr4lrurk1bu`
- [x] Folder mismatch задокументирован: LLM `b1gp3rqkf5t6kqmqaf7c` vs инфра `b1g0mhpm9tr4lrurk1bu`
- [x] Баланс / биллинг ок **по API** (после пополнения): локальный smoke + prod ops LLM
- [ ] Баннер «Облако заблокировано» исчез — **владелец: подтвердить в консоли**
- [ ] Форму гранта закрыли или осознанно отправили — **владелец**
- [x] SA + API-ключ AI Studio работают (smoke / prod health)
- [x] Локальный smoke `scripts/_tmp_check_yandex_llm.py` (2026-09-05): `available=True`, `chat_ok`, model `deepseek-v4-flash` / folder LLM
- [x] Prod: `ops_llm_enabled=yes` (health; SSH env не перепроверяли в этой сессии)
- [ ] **VPS / ops:** убедиться, что в `/opt/sfrfr/.env` заданы `YANDEX_API_KEY` + `YANDEX_FOLDER_ID` (= folder ключа) — **владелец/ops**, если SSH недоступен агенту

### Smoke (локально, без печати ключей)

```powershell
# подгрузить secrets/yandexAI_studio.env в env процесса, затем:
.\.venv\Scripts\python.exe scripts\_tmp_check_yandex_llm.py
```

Ожидание: `available True`, `chat_ok`, `resolved_model` с folder `b1gp3rqkf5t6kqmqaf7c` и `deepseek-v4-flash`.
