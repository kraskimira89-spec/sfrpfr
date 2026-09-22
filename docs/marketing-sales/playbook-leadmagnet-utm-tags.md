# UTM и теги: лид-магнит «Папка пенсионных документов» (PUB-6)

**Задача:** [PUB-6](https://tracker.yandex.ru/PUB-6)  
**Посадочная:** https://proverkastaza.ru/chek-list-dokumentov/

## Обязательные UTM (канал)

| Канал | utm_source | utm_medium | utm_campaign |
|-------|------------|------------|--------------|
| MAX (пост → лидмагнит) | `max` | `social` | `leadmagnet_pension_folder` |
| VK | `vk` | `social` | `leadmagnet_pension_folder` |
| Blog | `blog` | `content` | `leadmagnet_pension_folder` |
| Директ (черновик) | `yandex` | `cpc` | `leadmagnet_pension_folder` |
| **Подписка на канал MAX** (реклама / сайт CTA) | см. ниже | | `max_channel_subscribe` |

### Подписка на канал (канон 2026-09)

```text
https://max.ru/channel_proverkastaza?utm_source=<src>&utm_medium=<med>&utm_campaign=max_channel_subscribe&utm_content=<place>
```

| Место | source | medium | content |
|-------|--------|--------|---------|
| Hero главной | `site` | `cta` | `home_hero` |
| Блок «Как выбрать способ связи» | `site` | `cta` | `home_max_guide` |
| Директ охват | `yandex` | `cpc` | `direct_channel` |
| VK / посевы | `vk` | `cpc` или `social` | `vk_ads` |
| QR офлайн | `offline` | `qr` | `print` |

Стратегия: [strategy-ads-to-max-channel-2026-09.md](strategy-ads-to-max-channel-2026-09.md). Холодный трафик — **не** на личный чат.

Пример лидмагнита:
```text
https://proverkastaza.ru/chek-list-dokumentov/?utm_source=max&utm_medium=social&utm_campaign=leadmagnet_pension_folder
```

## Теги Tracker (публикации)

- `publish-leadmagnet`
- `publish-max` / `publish-vk` / `publish-blog` — по каналу
- `marketing`

## CTA A/B (микродействия на посадочной)

| Вариант | Кнопка | Гипотеза |
|---------|--------|----------|
| A | «ИЛС получил(а)» | самопроверка |
| B | «Есть расхождение» | переход к диагностике 3 000 ₽ |

Фиксировать в комментарии PUB-6: дата, канал, клики (без ПДн).

## Связка с диагностикой

После микродействия «Есть расхождение» → staff cabinet: next step «Диагностика 3 000 ₽», дата, ответственный.

## Ограничения

- Не обещать перерасчёт / сумму
- Не просить сканы в MAX
- Marketing consent необязателен на выдаче PDF
