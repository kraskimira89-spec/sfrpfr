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
Supabase Storage `pension-docs` — **не** обязательный вход OCR на этапе ТЗ-13
(реестр / доступ / backup / артефакты; OCR-read только при флаге fallback —
см. §3.7 и §16). Артефакты ingest (`extracted.md`, `ingest.json`) и метаданные
job — рядом с пайплайном (Storage/БД). Сверка ИЛС↔трудовая — код (`audit_ils`),
не LLM.

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
| **Supabase Storage `pension-docs`** | Реестр доступа / quarantine / verified / signed URL / backup / целевой контур миграции; метаданные `documents.storage_path`. **Не** обязательный вход OCR на этапе ТЗ-13. |
| **Supabase Postgres** | Очередь `document_ingest_jobs`, статусы `documents.*`, audit — метаданные (реестр), не файлы-оригиналы для OCR. |
| **Артефакты ingest** | `extracted.md` + `ingest.json` (см. §7): после OCR; типично private bucket `ingest/…`. Каталог `storage/processed/` в репозитории **не используется**. |

Порядок разрешения байтов для OCR worker (целевой MVP = шаги 1–2):

```text
1) local storage/uploads/{case_id}/…  (файл есть И size+sha256(+version) = реестр)
2) иначе Диск SFRFR-cases/… по yandex_disk_path из реестра (temp → OCR → finally delete)
3) иначе Storage pension-docs — ТОЛЬКО если SUPABASE_STORAGE_OCR_FALLBACK
   или INGEST_OCR_STORAGE_FALLBACK=true (не обязателен для MVP ТЗ-13)
4) иначе fail safe: job → needs_review / failed; OCR не вызывать
```

Связь с [14-yandex-workspace.md](14-yandex-workspace.md): Диск — **равный primary-вход OCR** вместе с local; кабинетный Storage остаётся для UI/security. Layout папок Диска — как в ТЗ-14 (`{ФИО|uuid}`); OCR **не** ищет файл по ФИО, только по path из реестра.

---

## 4. Конвейер ingest

```text
upload (cabinet / MAX)
  → SHA-256 (+ size) → реестр documents
  → сохранить оригинал: local uploads + Диск SFRFR-cases (primary)
  → (кабинет) quarantine/метаданные в Supabase; enqueue job
  → async worker (VPS):
        resolve bytes: local → Disk → (Storage только при флаге fallback)
        зафиксировать ocr_source_used + document_version на job
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
        → (кабинет) verified-копия / артефакты в pension-docs — не SoT OCR
  → дальше: classify → extract → audit_ils → draft → human_review
     (ИИ только после подтверждённого OCR / accept; не по superseded версии)
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
| **D** | Worker: resolve bytes local → Disk; Storage **только** при `*_OCR_FALLBACK=true`; fail safe без источника |
| **E** | Кэш по `content_hash`, уведомления клиенту «переснять» |

MVP ТЗ-13 = этапы **A+B**; Vision — **C** после ключей в `.env`/VPS;
смена SoT входа OCR — **D** (спека §3.7 / §16; код — миграция §15; **без** обязательного Storage-чтения для MVP).

---

## 12. Критерии приёмки

- [ ] PDF с текстовым слоем (типичная выписка) → `source=text_layer`, **без** вызова Vision/Tesseract.
- [ ] PDF без слоя / мало символов на странице → OCR только этих страниц.
- [ ] Worker берёт байты из **local и/или Disk** по порядку §3.7; Storage — только при явном флаге fallback; иначе fail safe.
- [ ] На job зафиксирован один `ocr_source_used`; проверка sha256(+size/+version) до OCR.
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
# Storage как OCR-вход — только явно (MVP может быть false):
# SUPABASE_STORAGE_OCR_FALLBACK=false
# INGEST_OCR_STORAGE_FALLBACK=false   # алиас того же флага
```

---

## 15. Расхождение с кодом (as-is → целевой SoT)

**Спека (этот документ + §16):** primary вход OCR = local `storage/uploads` + Диск
`SFRFR-cases`; Storage — **не** обязателен для OCR на этапе ТЗ-13 (только явный
fallback-флаг); движки: text-layer → Vision → Tesseract; async worker.

**Код на момент фиксации спеки** (`document_ingest_worker.process_document_ingest_job`):
байты для OCR скачиваются из Supabase Storage `pension-docs` по
`documents.storage_path` (quarantine → verified). Local/Disk уже пишутся при
upload/mirror (`save_upload`, `mirror_case_document_safe`), но worker их
**ещё не читает** как SoT. Download API Диска **нет**. Колонок
`local_path` / `yandex_disk_path` / `document_version` / `ocr_source_used` **нет**.

Миграция (этап **D** / coding Phase 1, **без** смены движков / без toggle
`INGEST_OCR_ENGINE` в первом PR):

1. В job/метаданных хранить `local_path` и/или `yandex_disk_path` (+ version/hash).
2. Worker: читать local → Disk → Storage **только** если fallback-флаг; иначе fail safe.
3. Quarantine/antivirus/verified в Storage остаются для кабинетного контура.
4. Тесты: ingest без download из bucket, если local есть и hash совпал.

До закрытия этапа D критерии §12 про resolve bytes — целевые; as-is
покрывает движки и артефакты, но не SoT входа.

**Coding ТЗ (фазы, resolver, OCRAdapter, тесты):**  
➜ [13a-document-ocr-coding-tz.md](13a-document-ocr-coding-tz.md) — Phase 1 = source resolver only.

---

## 16. Дополнение: OCR из local + Яндекс.Диск

Канон (зафиксировано 2026-09-24). Не отменяет §3.7 / §15; уточняет MVP и реестр.

### 16.1. Решение

| Контур | Роль на этапе ТЗ-13 |
|--------|---------------------|
| Local `storage/uploads` на VPS | **Primary** байты OCR |
| Яндекс.Диск `SFRFR-cases` | **Primary** при отсутствии/повреждении local |
| Supabase Storage `pension-docs` | Реестр доступа, backup/target, артефакты; **не** обязательный OCR-read |

Правило:

> Worker выбирает **один** источник оригинала на job (версия/hash), сверяет size + SHA-256 с реестром, фиксирует `ocr_source_used`, затем OCR. Без прошедшего источника — fail safe, OCR не вызывать.

Executor: `sfrfr-document-ingest.service` → `scripts/document_ingest_worker.py`. Без Celery. Без смены `INGEST_OCR_ENGINE` в шаге resolver.

### 16.2. Приоритет источников

```text
1. local_storage   — есть файл + size/sha256/(version) = реестр
2. yandex_disk     — download во temp → verify → OCR → finally delete
3. supabase_storage — только SUPABASE_STORAGE_OCR_FALLBACK /
                      INGEST_OCR_STORAGE_FALLBACK=true
4. fail safe
```

Значения `ocr_source_used` / `primary_ocr_source`:

```text
local_storage | yandex_disk | supabase_storage | none
```

(Алиасы в коде Phase 1 допустимы: `local` / `storage` — маппить 1:1.)

**Local (as-is path):** `storage/uploads/{case_id}/{8hex}_{safe_name}`  
(`storage_local_path`). Целевой layout с `{document_id}/` — опционально позже; привязка OCR **не** по имени alone, а по `document_id` + hash (+ version).

**Диск:** path **только** из реестра (`yandex_disk_path`). Запрещено: public links; поиск по ФИО; токены в git/логах; оставлять temp после OCR. Layout папки дела — ТЗ-14 (`{ФИО|uuid}/incoming|outgoing`); ФИО в path Диска — ops-layout, не ключ поиска OCR.

### 16.3. Реестр документа (целевые поля)

Минимум (часть уже есть as-is — см. 13a §2.5 / Phase 2):

```text
document_id, case_id, document_version
original_filename, safe_filename, mime_type, size_bytes, sha256
local_path, local_status
yandex_disk_path, yandex_disk_status
supabase_storage_path (= storage_path), supabase_storage_status
primary_ocr_source, ocr_source_used, ocr_source_verified_at
```

Правила: sha256 при приёме; новая загрузка → новая `document_version`; OCR-результат связан с version+hash+source; старые OCR → `superseded`; ИИ не на superseded.

Job audit (целевой; as-is enum статусов **не ломать** без нужды):

```text
job_id, document_id, document_version, expected_sha256
status, attempt_count, max_attempts, locked_at/by
ocr_source_used (один на run), source_attempts, last_safe_error_code
```

As-is статусы job: `queued|running|completed|needs_review|failed`  
(целевые имена из paste `processing` / `failed_retryable` / … — маппить, не форсить rename в Phase 1).

### 16.4. Пайплайн (целевой порядок записи)

```text
Upload → SHA-256 → local + зеркало Disk → запись documents + enqueue
  → worker: local → Disk → (Storage по флагу) → text-layer/OCR
  → quality gate → HITL → ИИ только на подтверждённых данных
```

As-is gap: mirror часто **после** OCR из Storage (`_mirror_document_after_security`) — целевой порядок выше; Phase 1 resolver читает то, что уже лежит.

### 16.5. Движки / quality / security (без смены в Phase 1)

Как §5–§6 и §10: `INGEST_OCR_ENGINE=auto`; text-layer → Vision → Tesseract; GPT-vision запрещён; трудовые → всегда manual review (Phase 4 coding); amoCRM вне контура; логи без байтов/полного OCR/ПДн.

### 16.6. Приёмка дополнения (поверх §12)

1. Файл из local → `ocr_source_used=local_storage`.  
2. Нет local / hash mismatch → Disk temp → `yandex_disk`; temp удалён.  
3. SHA-256 до OCR.  
4. Без флага Storage fallback и без local/Disk → fail safe, не Storage.  
5. Text-layer PDF без Vision/Tesseract.  
6. Трудовая → review.  
7. amoCRM не затронута.

**Следующий код после подтверждения:** только source resolver (13a Phase 1).
