# Marketing — пакет агента «Маркетолог»

Рабочая папка агента для отдельного чата Cursor.  
Стратегия и foundation лежат уровнем выше в `docs/marketing-sales/`; здесь — роль, промпт и операционные шаблоны.

## Быстрый старт

1. Новый чат Agent → имя **«Маркетолог»**.
2. Скопировать блок из [prompt-agent-marketer.md](prompt-agent-marketer.md).
3. При необходимости одной строкой задать фокус (MAX / Директ / отчёт / только документы).

## Файлы пакета

| Файл | Назначение |
|------|------------|
| [prompt-agent-marketer.md](prompt-agent-marketer.md) | **Промпт** — вставить в новый чат |
| [role-marketer.md](role-marketer.md) | Роль, зона ответственности, KPI |
| [checklist-p0.md](checklist-p0.md) | Чеклист работ без рекламного бюджета |
| [template-hypothesis.md](template-hypothesis.md) | Шаблон рекламной / контентной гипотезы |
| [template-channel-post.md](template-channel-post.md) | Шаблон поста канала (MAX и др.) |

## Канон вне этой папки (читать, не дублировать)

- Операционное ТЗ чата: [`../spec-marketing-agent-chat.md`](../spec-marketing-agent-chat.md)
- **Воронка / оффер / возражения:** [`../playbook-sales-clarity-funnel.md`](../playbook-sales-clarity-funnel.md)
- Квалификация: [`../playbook-sales-qualification.md`](../playbook-sales-qualification.md)
- Индекс маркетинга: [`../README.md`](../README.md)
- Стратегия: [`../strategy-2026-2028.md`](../strategy-2026-2028.md)
- Foundation: [`../spec-marketing-sales-foundation.md`](../spec-marketing-sales-foundation.md)
- Статус: [`../reports/2026-08-09-implementation-status.md`](../reports/2026-08-09-implementation-status.md)
- MAX 1000: [`../research-launchi-max-1000-subscribers.md`](../research-launchi-max-1000-subscribers.md)
- Бренд v2: [`../../brand/brand-platform-v2.md`](../../brand/brand-platform-v2.md)
- Подача: `scripts/assets/copy/submission-position.md`
- Чат бренда: [`../../brand/prompt-agent-brand-rollout.md`](../../brand/prompt-agent-brand-rollout.md)

## Куда класть результаты работы

- Исследования и гипотезы → `docs/marketing-sales/research-*.md` или `reports/`
- Playbook’и → `docs/marketing-sales/playbook-*.md`
- Черновики постов MAX (если в ассетах) → `scripts/assets/max-channel/`
- Яндекс Бизнес copy → `scripts/assets/yandex-business/`
- История сессии → `docs/history/`

Не хранить ПДн, токены, пароли и базы контактов.
