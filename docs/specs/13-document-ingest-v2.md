# ТЗ-13: Document ingest v2

**Статус:** проектирование (реализация поверх `src/sfrfr/ocr/engine.py`)  
**Связано:** [01-architecture.md](01-architecture.md), [04-admin-cabinet.md](04-admin-cabinet.md), [06-integrations-and-security.md](06-integrations-and-security.md), [07-mvp-roadmap.md](07-mvp-roadmap.md)

## 1. Цель

Качественно и дёшево получать **текст и структуру** из документов дела:

1. Цифровые PDF (Госуслуги / СФР) — **текстовый слой**, без OCR картинок.
2. Сканы и фото — OCR только где нужно (Yandex Vision → Tesseract fallback).
3. LLM (Yandex AI Studio) — **не** как OCR, а classify / extract / draft после текста.
4. Сотрудник — сверка сканов, правка текста и периодов при ошибках (HITL).

**Источник истины для OCR (вход байтов):** локальные оригиналы
`storage/uploads/{case_id}/` (настройка `storage_local_path`) **и**
Яндекс.Диск `disk:/SFRFR-cases/{ФИО|uuid}/` (`incoming/` для сканов клиента,
при необходимости `outgoing/` для подготовленных комплектов).
Supabase Storage `pension-docs` — **не** основной вход OCR (см. §3.7 и §15).
Артефакты ingest (`extracted.md`, `ingest.json`) и метаданные job — рядом с
пайплайном (Storage/БД). Сверка ИЛС↔трудовая — код (`audit_ils`), не LLM.

---

## 2. База (as-is)

Текущий `sfrfr.ocr.engine.extract_text`:

| Вход | Поведение |
|------|-----------|
| `.txt` / `.md` / `.csv` | чтение как текст |
| `.pdf` | `pypdf` extract; если пусто → `pdf2image` + Tesseract |
| изображения | Pillow + Tesseract (`rus+eng`) |
| ошибка | строка `[ocr_error]…` / `[ocr_empty]…`, пайплайн не падает |

Ограничения v1: нет постраничных порогов, нет Vision, нет метаданных `source`, нет отдельного HITL на ingest, один «плоский» `ocr_texts[]` без страниц.

---

## 3. Принципы v2

1. **Сначала текст, потом пиксели.** PDF с достаточным текстовым слоем не растеризовать.
2. **Постранично.** Смешанный PDF (текст + скан-страницы) обрабатывается по страницам.
3. **Не конвертировать в Word** как промежуточный формат пайплайна. Целевой текст — plain/markdown + JSON метаданных.
4. **YandexGPT не заменяет OCR.** Vision OCR — для сканов; GPT — для смысла по уже извлечённому тексту (с `redact_for_llm`).
5. **ПДн:** полные оригиналы и полный OCR — только local/Disk (оригиналы) + admin (expert+) / артефакты в private bucket; в amoCRM / Sheets / логи — без текстов документов.
6. **Идемпотентность:** повторный ingest того же `content_hash` переиспользует артефакты (опционально в MVP+).
7. **Единый async worker на VPS:** OCR не в HTTP-запросе upload; очередь job → worker → движки по порядку §6.

### 3.7. Роли хранилищ (OCR vs кабинет)

| Контур | Роль в ТЗ-13 |
|--------|----------------|
| **Local `storage/uploads/{case_id}/`** | **Primary OCR input.** Байты оригинала после upload / MAX / backfill (`save_upload`). Путь на VPS через `storage_local_path`. |
| **Яндекс.Диск `SFRFR-cases/{ФИО\|uuid}/`** | **Primary OCR input** (тот же оригинал байт-в-байт). Типично `incoming/` (сканы клиента); `outgoing/` — если OCR нужен для исходящих комплектов. Не публичный канал; банковские выписки не кладём без явного флага. |
| **Supabase Storage `pension-docs`** | Кабинет / quarantine / verified / signed URL для превью HITL; метаданные `documents.storage_path`. **Не** SoT для чтения байтов в OCR worker (целевой контракт). |
| **Supabase Postgres** | Очередь `document_ingest_jobs`, статусы `documents.*`, audit — метаданные, не файлы. |
| **Артефакты ingest** | `extracted.md` + `ingest.json` (см. §7): пишутся после OCR; могут жить в private bucket рядом с verified-копией. |

Порядок разрешения байтов для OCR worker (целевой):

```text
1) local storage/uploads/{case_id}/…  (если файл есть и hash/имя сходятся)
2) иначе Диск SFRFR-cases/…/incoming|outgoing/…
3) иначе (fallback / переходный период) — Storage pension-docs по storage_path
```

Связь с [14-yandex-workspace.md](14-yandex-workspace.md): Диск для дел — не «только зеркало для глаз сотрудника», а **равный primary-вход OCR** вместе с local; кабинетные upload/quarantine в Supabase остаются для UI и security-контура.

---

## 4. Конвейер ingest

```text
upload (cabinet / MAX)
  → сохранить оригинал: local uploads + Диск SFRFR-cases (primary)
  → (кабинет) quarantine/метаданные в Supabase; enqueue job
  → async worker (VPS):
        resolve bytes: local → Disk → (fallback Storage)
        → detect mime / pages
        → per page / per file:
              text_layer? ──да (порог OK)──► source=text_layer
                    │
                    нет / мало символов
                    ▼
              OCR: Yandex Vision → Tesseract fallback
                    │
                    ▼
              source=ocr_vision | ocr_tesseract | failed
        → артефакты (extracted.md + ingest.json)
        → quality gate → ocr_done | needs_ingest_review
        → (опционально) verified-копия / артефакты в pension-docs
  → дальше: classify → extract → audit_ils → draft → human_review
```

### 4.1. Встраивание в статусы кейса

| Статус | Смысл для ingest |
|--------|------------------|
| `documents_received` | файлы приняты (local/Disk ± кабинетный Storage), ingest ещё не прошёл / в очереди |
| `ocr_done` | все обязательные файлы извлечены, quality gate OK **или** эксперт подтвердил текст |
| *(флаг)* `needs_ingest_review` | не отдельный enum MVP: флаг на деле/документе + очередь в admin; статус может остаться `documents_received` или `ocr_done` с предупреждением |
| `human_review` | проверка сверки/черновика (как сейчас); **дополнительно** ingest-HITL может вернуть дело сюда раньше |

Минимально для v2: поле/флаг `ingest_review_required` на уровне дела или документа (см. §8), без ломки `CaseStatus` enum. При необходимости позже: статус `ingest_review`.

---

## 5. Пороги и эвристики

Конфиг (env / settings), значения по умолчанию:

| Параметр | Default | Назначение |
|----------|---------|------------|
| `INGEST_MIN_CHARS_PER_PAGE` | `80` | меньше → страница считается «без текста» → OCR |
| `INGEST_MIN_CHARS_DOC` | `120` | после склейки страниц: ниже → `ocr_empty` / review |
| `INGEST_OCR_DPI` | `200` | растеризация PDF для OCR |
| `INGEST_MAX_PAGES` | `40` | защита от гигантских PDF |
| `INGEST_OCR_ENGINE` | `auto` | `auto` \| `vision` \| `tesseract` |
| `INGEST_VISION_FALLBACK_TESSERACT` | `true` | при ошибке/пустом Vision → Tesseract |
| `TESSERACT_LANG` | `rus+eng` | как сейчас |

### 5.1. Правила решения по странице PDF

1. Извлечь text layer (PyMuPDF предпочтительно; fallback `pypdf` — совместимость с v1).
2. Нормализовать whitespace; посчитать `char_count` (без пробелов — опционально второй метрикой).
3. Если `char_count >= INGEST_MIN_CHARS_PER_PAGE` → `source=text_layer`.
4. Иначе OCR страницы → `source=ocr_*`.
5. Если OCR вернул пусто / `[ocr_error]` → `source=failed`, страница в review.

### 5.2. Quality gate (документ)

После сборки:

- есть хотя бы одна страница `failed` **или** суммарно `< INGEST_MIN_CHARS_DOC` → `needs_ingest_review=true`;
- доля OCR-страниц `>= 50%` и документ классифицирован/помечен как «трудовая / скан» → **рекомендация** review (не блокер, если текст достаточный);
- маркеры `[ocr_error]` / `[ocr_empty]` в итоговом тексте → review.

Пайплайн classify/extract **не запускать** автоматически, пока `needs_ingest_review=true` (кроме явного «продолжить без правки» экспертом).

---

## 6. Vision vs Tesseract

| Движок | Когда | Плюсы | Минусы |
|--------|-------|-------|--------|
| **Yandex Vision OCR** | `INGEST_OCR_ENGINE=vision` или `auto` + заданы credentials Vision | качество кириллицы, таблицы/сканы, единый Яндекс.Облако с AI Studio | платно, сеть, ПДн уходят в облако OCR |
| **Tesseract** | `auto` без Vision; fallback; local/dev | бесплатно, on-prem | хуже на фото/таблицах |
| **YandexGPT vision** | **не использовать** как основной OCR | — | дорого, нестабильно для таблиц ИЛС |

### 6.1. Политика `auto`

```text
if Vision credentials configured:
    try Vision
    if empty/error and FALLBACK: Tesseract
else:
    Tesseract
```

### 6.2. Credentials (не коммитить)

- Vision: ключ/сервисный аккаунт Yandex Cloud (отдельные env, рядом с `YANDEX_*` LLM).
- Tesseract: бинарник + `rus` traineddata на VPS (как сейчас).

В логах: только `engine`, `page`, `char_count`, `duration_ms` — без текста страницы.

---

## 7. Форматы артефактов

**Оригинал для OCR (primary):**
`storage/uploads/{case_id}/…` и/или
`disk:/SFRFR-cases/{ФИО|uuid}/incoming|outgoing/…`.

**Кабинет / quarantine / verified (не SoT OCR):** private bucket `pension-docs`,
типичные префиксы `quarantine/…`, `verified/…` (как в worker as-is).

Рядом с verified или отдельным префиксом `…/ingest/` — артефакты:

### 7.1. `extracted.md` (для человека и LLM)

```markdown
<!-- sfrfr-ingest doc_id=… hash=… -->
## Страница 1
{текст}

## Страница 2
{текст}
```

- Кодировка UTF-8.
- Без встраивания бинарников.
- Это то, что уходит в classify/extract после redact.

### 7.2. `ingest.json` (машина)

```json
{
  "schema_version": 2,
  "doc_id": "uuid",
  "case_id": "uuid",
  "original_name": "ils.pdf",
  "content_hash": "sha256:…",
  "mime": "application/pdf",
  "page_count": 3,
  "needs_ingest_review": false,
  "pages": [
    {
      "page": 1,
      "source": "text_layer",
      "char_count": 4200,
      "engine": null,
      "error": null
    },
    {
      "page": 2,
      "source": "ocr_vision",
      "char_count": 890,
      "engine": "yandex_vision",
      "error": null
    }
  ],
  "totals": {
    "chars": 5090,
    "text_layer_pages": 1,
    "ocr_pages": 1,
    "failed_pages": 0
  },
  "created_at": "ISO-8601"
}
```

`source`: `text_layer` | `ocr_vision` | `ocr_tesseract` | `plain_file` | `failed`.

### 7.3. Хранение в контексте пайплайна

- `CaseContext.ocr_texts` — сохранить совместимость: список строк **по документам** (содержимое `extracted.md` без HTML-комментария) **или** миграция на `ingest_documents[]` с `doc_id` + text + meta.
- В admin API: отдавать expert/admin и текст, и `ingest.json` meta; оператору — только факт «документ загружен / на проверке OCR».

**Не делать** DOCX обязательным артефактом. Опционально позже: экспорт MD→DOCX для скачивания экспертом.

---

## 8. Работа сотрудника (HITL ingest)

Связь с [04-admin-cabinet.md](04-admin-cabinet.md): расширить карточку дела.

### 8.1. Роли

| Роль | Ingest |
|------|--------|
| Оператор | видит статус «нужна проверка текста/скана»; может запросить у клиента перезагрузку; **не** правит OCR и периоды |
| Эксперт | сверка скана↔текст, правка `extracted` / периодов, accept/reject, re-run OCR |
| Админ | всё экспертное + настройки движков |

### 8.2. Очередь «Ingest review»

Фильтр реестра: `needs_ingest_review=true`.

Карточка документа:

1. Превью оригинала (signed URL, короткий TTL).
2. Текст `extracted.md` (editable textarea / split view по страницам).
3. Бейджи: `text_layer` / `Vision` / `Tesseract` / `failed` на страницах.
4. Предупреждения quality gate.

### 8.3. Действия эксперта

| Действие | Результат |
|----------|-----------|
| **Подтвердить текст** | сохранить правки → `needs_ingest_review=false` → разрешить classify/extract |
| **Перезапустить OCR** (страница/документ) | Vision или Tesseract по выбору; новая ревизия артефактов |
| **Пометить страницу «нечитаемо»** | чек-лист клиенту: «переснять / прислать PDF с Госуслуг» |
| **Пропустить extract** | редко: ручной ввод периодов без LLM |
| **Отклонить документ** | статус файла rejected; дело не двигается по OCR для этого файла |

Все действия — в `access_audit` (`ingest_accept`, `ingest_edit`, `ingest_rerun_ocr`, `ingest_reject`).

### 8.4. Сверка скана (UI)

- Слева: страница скана; справа: текст страницы.
- Подсветка `failed` / низкий `char_count`.
- После accept — тот же путь, что `ocr_done` → classify…

### 8.5. Ошибки и клиент

Если эксперт пометил «нечитаемо»:

- уведомление клиенту (MAX / кабинет): короткий текст без ПДн («Нужен более чёткий скан трудовой, стр. 2»);
- checklist item `owner=client`, status open.

### 8.6. Связь с `human_review`

- Ingest HITL — **до** надёжного extract/audit.
- `human_review` после draft — проверка findings и черновика (как сейчас).
- Эксперт может вернуть дело на ingest (`needs_ingest_review=true`), если на audit видно мусор в периодах из-за плохого OCR.

---

## 9. Изменения в коде (целевой контракт)

Модуль: расширить `sfrfr.ocr` (не ломая `extract_text` / `extract_texts` сразу):

```text
sfrfr/ocr/
  engine.py          # thin facade → ingest_document()
  pdf_text.py        # text layer (PyMuPDF / pypdf)
  ocr_tesseract.py
  ocr_vision.py      # Yandex Vision
  artifacts.py       # write extracted.md + ingest.json
  quality.py         # пороги, needs_review
```

`extract_text(path) -> str` — сохранить для CLI/тестов; внутри вызывать v2 и возвращать только склеенный текст.

Оркестратор: перед classify проверять `needs_ingest_review`; при true → StepResult с сообщением «ожидает сверки ingest».

---

## 10. Безопасность

- Превью HITL: signed URL на копию в Storage ≤ TTL **или** стрим из local/Disk только для expert+ (без долгоживущих публичных ссылок).
- Vision/LLM: по возможности маскировать СНИЛС до отправки; полный скан в Vision неизбежен для OCR — договор / политика ПДн Яндекса.
- Не писать полный OCR в application logs / amo / Sheets.
- Артефакты — private bucket (или local рядом с uploads), доступ как у документов дела (expert+).
- Диск `SFRFR-cases`: папка по ФИО/UUID, без телефона/СНИЛС в путях; не публичный шаринг.

---

## 11. Этапы внедрения

| Этап | Содержание |
|------|------------|
| **A** | Постраничные пороги + PyMuPDF/pypdf + `ingest.json` / `extracted.md`; Tesseract как сейчас |
| **B** | Флаг `needs_ingest_review` + admin split-view + accept/edit/rerun |
| **C** | Yandex Vision + `auto` + fallback Tesseract |
| **D** | Worker читает байты **сначала** из local / Disk (порядок §3.7); Storage — fallback |
| **E** | Кэш по `content_hash`, уведомления клиенту «переснять» |

MVP ТЗ-13 = этапы **A+B**; Vision — **C** после ключей в `.env`/VPS;
смена SoT входа OCR — **D** (спека уже зафиксирована, код — миграция §15).

---

## 12. Критерии приёмки

- [ ] PDF с текстовым слоем (типичная выписка) → `source=text_layer`, **без** вызова Vision/Tesseract.
- [ ] PDF без слоя / мало символов на странице → OCR только этих страниц.
- [ ] Worker берёт байты из **local и/или Disk** по порядку §3.7; Storage — только fallback.
- [ ] Артефакты `extracted.md` + `ingest.json`; схема §7.2.
- [ ] `INGEST_OCR_ENGINE=auto`: Vision если настроен, иначе Tesseract; fallback при ошибке Vision.
- [ ] При `failed` / низком char_count → `needs_ingest_review`; classify/extract не стартуют сами.
- [ ] Эксперт: side-by-side скан↔текст, правка, accept, rerun OCR, reject; записи в audit.
- [ ] Оператор не редактирует OCR-текст.
- [ ] В ответе public/amo/Sheets нет текстов OCR.
- [ ] CLI/`extract_text` по-прежнему возвращает строку (обратная совместимость).
- [ ] Юнит-тесты: порог страницы; mixed PDF (mock); quality gate; resolve bytes local→Disk.

---

## 13. Вне scope

- Обязательный экспорт в DOCX/Word.
- Распознавание рукописного текста как SLA.
- Обучение своих OCR-моделей.
- Автоисправление юридической силы документа.
- OCR внутри WordPress / публичного сайта.

---

## 14. Env (сводка)

```text
INGEST_MIN_CHARS_PER_PAGE=80
INGEST_MIN_CHARS_DOC=120
INGEST_OCR_DPI=200
INGEST_MAX_PAGES=40
INGEST_OCR_ENGINE=auto
INGEST_VISION_FALLBACK_TESSERACT=true
TESSERACT_LANG=rus+eng
# Vision (этап C): YANDEX_VISION_* или переиспользование SA облака
# Пути оригиналов (этап D): storage_local_path + YANDEX_DISK_* / SFRFR-cases
```

---

## 15. Расхождение с кодом (as-is → целевой SoT)

**Спека (этот документ):** primary вход OCR = local `storage/uploads` + Диск
`SFRFR-cases`; движки: text-layer → Vision → Tesseract; async worker.

**Код на момент фиксации спеки** (`document_ingest_worker.process_document_ingest_job`):
байты для OCR скачиваются из Supabase Storage `pension-docs` по
`documents.storage_path` (quarantine → verified). Local/Disk уже пишутся при
upload/mirror (`save_upload`, `mirror_case_document_safe`), но worker их
**ещё не читает** как SoT.

Миграция (этап **D**, без смены движков OCR):

1. В job/метаданных хранить `local_path` и/или disk-path (или резолвить по
   `case_id` + имени/`content_hash`).
2. Worker: читать local → Disk → fallback Storage.
3. Quarantine/antivirus в Storage можно оставить для кабинетного контура;
   после accept — не требовать Storage как единственный источник байтов.
4. Тесты: ingest без download из bucket, если local есть.

До закрытия этапа D критерии §12 про resolve bytes — целевые; as-is
покрывает движки и артефакты, но не SoT входа.

**Coding ТЗ (фазы, resolver, OCRAdapter, тесты):**  
➜ [13a-document-ocr-coding-tz.md](13a-document-ocr-coding-tz.md) — Phase 1 = source resolver only.
