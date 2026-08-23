# VK — пакет канала ВКонтакте

Рабочая папка чата Cursor про **ВКонтакте** для «Проверки стажа» (SFRFR).

## Быстрый старт

1. Новый чат Agent → имя **«VK»** / **«ВКонтакте»**.
2. Скопировать блок из [prompt-agent-vk.md](prompt-agent-vk.md).
3. Уточнить режим: сообщество / органика / лид-форма / ads / API.

## Файлы пакета

| Файл | Назначение |
|------|------------|
| [prompt-agent-vk.md](prompt-agent-vk.md) | Промпт для нового чата |
| [playbook-vk-community.md](playbook-vk-community.md) | Сообщество: ритм, CTA, тарифы 3/5/8, лид-форма, UTM |
| [copy-community-launch.md](copy-community-launch.md) | Копипаст запуска: описание, закреп, автоответ, 3 поста, чеклист UI |
| [research-vk-api.md](research-vk-api.md) | API VK: что нужно сервису, границы, ссылки на доки |

## Роль канала в воронке

```text
ВК (пост / ads / форма)
  → сайт (сегмент / тарифы) или личный чат MAX
  → квалификация
  → кабинет (согласие, документы, оплата)
```

ВК — **охват и доверие**, не место для сканов и не замена кабинета.

## Канон (не дублировать длинно здесь)

- Подача: `scripts/assets/copy/submission-position.md`
- Цены: `scripts/assets/trust/tarify.html` → **3 000 / 5 000 / 8 000 ₽** поэтапно + Word 100 ₽/разворот
- Стратегия каналов: `docs/marketing-sales/strategy-2026-2028.md` §5.3
- ТЗ VK/ОК: `docs/marketing-sales/spec-marketing-sales-foundation.md` §11
- Исследование: `docs/marketing-sales/research-audience-channels-2026-08.md`
- MAX-контент (адаптировать, не копировать слепо): `docs/marketing-sales/playbook-max-channel-month-2026-08.md`

## Жёсткие границы

- Не принимать СНИЛС, паспорт, ИЛС, сканы, текст решения СФР в комментариях, ЛС сообщества и лид-форме.
- Не обещать перерасчёт и сумму выплат; нет «калькулятора пенсии» как продукта сервиса.
- Токены VK / ads — только в `secrets/` и на VPS `.env`, **не в git**.
- Платный запуск — только после лимита владельца, ERID и baseline Метрики/amo (см. `docs/marketing-sales/reports/2026-08-09-implementation-status.md`).
