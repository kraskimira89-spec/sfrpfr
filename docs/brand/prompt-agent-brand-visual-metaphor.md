# Промпт агента: Visual Prompt Architect

Самодостаточный вход для чата Cursor / YandexGPT / OpenAI.

1. Прикрепите `@prompts/visual/system-prompt.md` и `@prompts/visual/brand-guardrails.md`.
2. Дайте тему публикации и платформу (блог 16:9 / сайт 4:3 / MAX 1:1 / сторис 9:16).
3. Утвердите **metaphor** и **core_message** до генерации картинки.
4. Промпты для моделей: из ответа агента или через `prompts/visual/compiler.ts`.

Полный system prompt — в [prompts/visual/system-prompt.md](../../prompts/visual/system-prompt.md).

Методика двух слоёв: [methodology-visual-metaphor-publication.md](methodology-visual-metaphor-publication.md).

## Краткий чеклист ответа агента

Ответ **только JSON** с полями: topic, problem, emotion_before, desired_state,
core_message, metaphor, action, format, aspect_ratio, text_safe_area, style,
midjourney_prompt, midjourney_parameters, dalle_prompt, negative_prompt,
alt_text, editor_note.

## Продуктовые якоря

- Позиция подачи: готовим план — подаёт клиент — решает СФР.
- Кабинет только на сайте; вложения в MAX принимаются (не пугать «запретом чата»).
- Цены/оффер в картинку не тащить; денег и «роста пенсии» нет.
