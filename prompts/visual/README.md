# Visual prompts — два слоя

Конвейер обложек для «Проверка стажа»: **сначала смысл (матрица)**, потом промпты под модели.

```text
Тема → агент (VisualMatrix JSON) → валидатор бренд-ограничений
     → compiler.ts → Midjourney | GPT Image/DALL·E | negative | alt | editor_note
     → человек утверждает метафору и картинку → публикация
```

| Файл | Назначение |
|------|------------|
| [system-prompt.md](system-prompt.md) | System prompt агента (ответ только JSON) |
| [brand-guardrails.md](brand-guardrails.md) | Запреты и бренд |
| [visual-matrix.schema.json](visual-matrix.schema.json) | JSON Schema матрицы |
| [compiler.ts](compiler.ts) | Компилятор Midjourney / DALL·E (без Image API) |
| [examples/](examples/) | Эталонные матрицы + golden compiled |

Методика: [docs/brand/methodology-visual-metaphor-publication.md](../../docs/brand/methodology-visual-metaphor-publication.md)  
Вход агента Cursor: [docs/brand/prompt-agent-brand-visual-metaphor.md](../../docs/brand/prompt-agent-brand-visual-metaphor.md)

## Форматы

| Канал | aspect_ratio |
|-------|----------------|
| Статья / Дзен / обложка | 16:9 |
| Карточка сайта | 4:3 |
| MAX / квадрат | 1:1 |
| Сторис / вертикаль | 9:16 |

Заголовок **не** рисовать внутри картинки — зона `text_safe_area`.

## Принцип

Автоматизируем подготовку промптов. **Не публикуем** визуал без человеческой проверки.
