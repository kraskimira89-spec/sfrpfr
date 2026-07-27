# ТЗ-13: Document ingest v2

**Статус:** проектирование (реализация поверх `src/sfrfr/ocr/engine.py`)  
**Связано:** [01-architecture.md](01-architecture.md), [04-admin-cabinet.md](04-admin-cabinet.md), [06-integrations-and-security.md](06-integrations-and-security.md), [07-mvp-roadmap.md](07-mvp-roadmap.md)

## 1. Цель

Качественно и дёшево получать **текст и структуру** из документов дела:

1. Цифровые PDF (Госуслуги / СФР) — **текстовый слой**, без OCR картинок.
2. Сканы и фото — OCR только где нужно (Yandex Vision → Tesseract fallback).
3. LLM (Yandex AI Studio) — **не** как OCR, а classify / extract / draft после текста.
4. Сотрудник — сверка сканов, правка текста и периодов при ошибках (HITL).

Источник истины: оригинал в Supabase Storage + артефакты ingest. Сверка ИЛС↔трудовая — код (`audit_ils`), не LLM.

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
5. **ПДн:** оригиналы и полный OCR только в Storage / admin (expert+); в amoCRM / Sheets / логи — без текстов документов.
6. **Идемпотентность:** повторный ingest того же `content_hash` переиспользует артефакты (опционально в MVP+).

---

## 4. Конвейер ingest

```text
upload (cabinet / MAX)
  → сохранить оригинал (Storage)
  → detect mime / pages
  → per page / per file:
        text_layer? ──да (порог OK)──► source=text_layer
              │
              нет / мало символов
              ▼
        OCR engine: Vision (если настроен) → иначе Tesseract
              │
              ▼
        source=ocr_vision | ocr_tesseract | failed
  → собрать артефакты (extracted.md + ingest.json)
  → quality gate → ocr_done | needs_ingest_review
  → дальше: classify → extract → audit_ils → draft → human_review
```

### 4.1. Встраивание в статусы кейса

| Статус | Смысл для ingest |
|--------|------------------|
| `documents_received` | файлы в Storage, ingest ещё не прошёл / в очереди |
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

Оригинал: `cases/{case_id}/docs/{doc_id}/{filename}` (private bucket).

Рядом (тот же префикс или `…/ingest/`):

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

- Signed URL на оригинал ≤ TTL Storage (как сейчас).
- Vision/LLM: по возможности маскировать СНИЛС до отправки; полный скан в Vision неизбежен для OCR — договор / политика ПДн Яндекса.
- Не писать полный OCR в application logs / amo / Sheets.
- Артефакты — private bucket, RLS/роли как у документов дела.

---

## 11. Этапы внедрения

| Этап | Содержание |
|------|------------|
| **A** | Постраничные пороги + PyMuPDF/pypdf + `ingest.json` / `extracted.md`; Tesseract как сейчас |
| **B** | Флаг `needs_ingest_review` + admin split-view + accept/edit/rerun |
| **C** | Yandex Vision + `auto` + fallback Tesseract |
| **D** | Кэш по `content_hash`, уведомления клиенту «переснять» |

MVP ТЗ-13 = этапы **A+B**; Vision — **C** после ключей в `.env`/VPS.

---

## 12. Критерии приёмки

- [ ] PDF с текстовым слоем (типичная выписка) → `source=text_layer`, **без** вызова Vision/Tesseract.
- [ ] PDF без слоя / мало символов на странице → OCR только этих страниц.
- [ ] Артефакты `extracted.md` + `ingest.json` рядом с оригиналом; схема §7.2.
- [ ] `INGEST_OCR_ENGINE=auto`: Vision если настроен, иначе Tesseract; fallback при ошибке Vision.
- [ ] При `failed` / низком char_count → `needs_ingest_review`; classify/extract не стартуют сами.
- [ ] Эксперт: side-by-side скан↔текст, правка, accept, rerun OCR, reject; записи в audit.
- [ ] Оператор не редактирует OCR-текст.
- [ ] В ответе public/amo/Sheets нет текстов OCR.
- [ ] CLI/`extract_text` по-прежнему возвращает строку (обратная совместимость).
- [ ] Юнит-тесты: порог страницы; mixed PDF (mock); quality gate.

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
```
