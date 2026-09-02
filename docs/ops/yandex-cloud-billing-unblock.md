# Яндекс.Облако: разблокировка биллинга (AI Studio / ресурсы)

**Организация / облака (создано 2026-07-28; live-проверка 2026-09-02):**

| Облако | ID | Статус |
|--------|-----|--------|
| **`sfrfr-ai`** (рабочее) | `b1gkscu5sqpjtf5d5rbi` | ✅ существует; каталог `default` ACTIVE; VM staging RUNNING |
| `cloud-infoproverkastazaru` | — | старое; не основное |

**Каталог в `sfrfr-ai`:**

| Каталог | `folder_id` |
|---------|-------------|
| **`default`** (выбран) | `b1g0mhpm9tr4lrurk1bu` |

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
- Поддержка Cloud: org id `bpf25prvoq8uqqlvujim`, cloud `b1gkscu5sqpjtf5d5rbi`, folder `b1g0mhpm9tr4lrurk1bu`.

### Прямые ссылки

1. Каталог: https://console.yandex.cloud/folders/b1g0mhpm9tr4lrurk1bu  
2. Облако: https://console.yandex.cloud/cloud?id=b1gkscu5sqpjtf5d5rbi  

> Workspace (`proverkastaza@…` почта/Диск) ≠ членство в **организации Yandex Cloud**. Это разные контуры.

> Это **не** Яндекс Workspace (почта/Диск/Календарь/Телемост) — OAuth ТЗ-14 живёт отдельно.

---

## Сделано

- [x] Облако/каталог для AI: `sfrfr-ai` → каталог `default` (`folder_id` выше)
- [ ] Биллинг разблокирован
- [ ] SA + API-ключ

---

## Сейчас — только биллинг

Каталоги готовы; **создание ресурсов всё ещё недоступно** (жёлтый баннер).

### Вариант A — пополнить (нужен для AI Studio)

1. В шапке — баланс **0,00 ₽** или [Биллинг](https://console.yandex.cloud/billing).
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

Каталог уже выбран: `default` / `folder_id=b1g0mhpm9tr4lrurk1bu`.

1. В каталоге `default` → **IAM** → **Сервисные аккаунты**.
2. Создать SA (например `sfrfr-ai-llm`) + роль `ai.languageModels.user`.
3. **Создать API-ключ** со scope `yc.ai.languageModels.execute`.
4. Ключ **не** в чат / **не** в git → в `.env` / VPS:
   - `YANDEX_FOLDER_ID=b1g0mhpm9tr4lrurk1bu`
   - `YANDEX_API_KEY=…`
   - при необходимости те же в `LLM_FOLDER_ID` / `LLM_API_KEY`

Кнопка **«Перейти в AI Studio»** — шаг 2 (тест в UI), когда ключ уже есть.

---

## Чеклист

- [x] Каталог `default` в облаке `sfrfr-ai`, `folder_id` зафиксирован
- [ ] Баланс / статус платёжного аккаунта ок
- [ ] Баннер «Облако заблокировано» исчез
- [ ] Форму гранта закрыли или осознанно отправили
- [ ] _(дальше)_ SA + API-ключ AI Studio
