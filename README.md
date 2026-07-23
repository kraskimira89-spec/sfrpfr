# SFRFR

Автоматизация аудита пенсионных дел: сверка ИЛС и трудового стажа, OCR документов, AI-черновики заявлений в СФР, CRM-карточки кейсов.

## Стек

- Python 3.11+, FastAPI, Pydantic
- PostgreSQL / Supabase (БД, Auth, Storage)
- OCR: Tesseract (+ опционально Yandex OCR)
- AI: Yandex AI Studio (OpenAI-compatible)
- Клиентский канал: MAX Bot API
- Витрина: WordPress на VPS; API на поддомене (см. `docs/deploy-vps.md`)
- Кабинеты: Next.js `apps/cabinet` / `apps/admin` (JWT → `/api/portal`)
- CLI: Typer

## Быстрый старт

```powershell
cd c:\Users\user\Documents\Cursor\SFRFR
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[ai,dev]"
copy .env.example .env
# заполните SUPABASE_* или поднимите локальную БД:
docker compose up -d db
uvicorn sfrfr.api:app --reload
```

API: http://127.0.0.1:8000/docs

CLI:

```powershell
sfrfr version
sfrfr serve
```

## Структура

```text
src/sfrfr/     исходный код API
apps/          Next.js кабинеты (client / admin)
docs/          документация и история
knowledge/     база знаний для RAG (без ПДн)
storage/       загрузки клиентов (в .gitignore)
tests/         тесты
scripts/       утилиты
```

## B2C (частные клиенты)

ТЗ и модель монетизации:

- `docs/b2c-monetization-tz.md`
- `docs/b2c-monetization-model.md`
- `docs/b2c-customer-journey.md`
- `docs/b2c-architecture.md`
- `docs/contracts/` — черновики оферты и индивидуального заказа

## Автокоммит / автодеплой

- Локально: `.\scripts\auto_commit_push.ps1`
- Cursor stop-hook: `.cursor/hooks.json`
- VPS каталог: `/opt/sfrfr` — `scripts/vps_bootstrap.sh` (один раз), затем GitHub Actions `deploy-vps.yml`
- Инструкция: `docs/deploy-vps.md`

## Важно про ПДн

В git не попадают `.env`, сканы и загруженные документы. В логах используйте маскирование СНИЛС/ФИО (`sfrfr.utils.redact_pii`). База знаний RAG: только обезличенные кейсы `knowledge/cases/` со статусом `verified`/`template` (см. `docs/specs/08-knowledge-rag.md`).
