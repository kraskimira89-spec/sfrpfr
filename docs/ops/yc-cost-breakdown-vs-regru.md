# Разбор стоимости YC (~8500 ₽) vs Reg.ru VM 1:1

Дата: 2026-08-14.  
Live-ресурсы: folder `b1g0mhpm9tr4lrurk1bu`, VM `sfrfr-staging-supabase` (`51.250.13.240`).  
Прайс YC: Compute / VPC / KMS / Lockbox с **30.04.2026**, расчёт **720 ч/мес**, ₽ с НДС.

Canvas: `.cursor/projects/.../canvases/yc-vs-regru-cost.canvas.tsx`

## Важно про «8500»

| Что | Комментарий |
|-----|-------------|
| Грант ~8 217 ₽ (скрин биллинга, до ~05.09.2026) | Остаток гранта, не «тариф» |
| Always-on инфра по прайсу | **~7 567 ₽/мес** |
| Ваша цифра «8500 в месяц» | Совпадает с грантом/порядком burn; почти всё — **ВМ+диски**, не DBaaS |

Старая оценка в `infra/yandex-cloud/README.md` (~3800) **устарела** после прайса 2026.

## Чек по сервисам (фиксированные)

| Сервис | Конфиг | Ставка | ₽/мес |
|--------|--------|--------|------:|
| Compute vCPU | 4 × Ice Lake (`standard-v3`) 100% | 1,24 ₽/vCPU·ч | 3 571 |
| Compute RAM | 8 ГБ | 0,33 ₽/ГБ·ч | 1 901 |
| Boot disk | 30 ГБ `network-ssd` | 0,0199 ₽/ГБ·ч | 430 |
| Data disk | 100 ГБ `network-ssd` | 0,0199 ₽/ГБ·ч | 1 433 |
| Public IP | статический, активный | 0,26352 ₽/ч | 190 |
| Lockbox | 2 секрета × 1 версия | 0,0274 ₽/вер·ч | 39 |
| KMS | 1 симм. ключ | 0,00439 ₽/ч | 3 |
| **Итого always-on** | | | **~7 567** |

### Переменные (поверх)

| Сервис | Модель | Ожидание MVP |
|--------|--------|--------------|
| SmartCaptcha | до 10k ok/мес бесплатно | ≈ 0 ₽ |
| AI Studio / Vision | токены / OCR | сотни–тысячи при нагрузке |
| Object Storage | бакет `sfrfr-staging-backup-…` | ≈ 0–100 ₽ (сейчас почти пуст) |
| Исходящий трафик | льготный порог | обычно мало |

**Остановленная ВМ:** CPU/RAM не тарифицируются, но диски + IP (активный/резерв) + Lockbox/KMS ≈ **~2 340 ₽/мес**.

## YC vs Reg.ru VM 1:1

Сравниваем **хост под Docker Compose Supabase**, не managed PostgreSQL со скрина `cloud.reg.ru`.

| Компонент | Yandex Cloud | Reg.ru VPS (публичный прайс) |
|-----------|--------------|------------------------------|
| CPU/RAM/диск | 4 / 8 / 130 ГБ SSD + IP | **High C4-M8-D120** — 4 / 8 / 120 ГБ NVMe |
| Цена хоста | **~7 525 ₽** (CPU+RAM+диски+IP) | **~4 360 ₽/мес** |
| Экономия железа | — | **~3 100 ₽/мес** |
| Auth/Storage/RLS | Compose на ВМ | то же, если перенести Compose |
| Lockbox / KMS / Object Storage | есть | заменить (файлы, свой S3/бэкап) |
| SmartCaptcha + AI Studio | usage в YC | **не переносятся** — остаются в YC |

Ближайшие альтернативы Reg.ru: High C4-M8-D80 (~3 880, диск 80 ГБ — тесно под 130 ГБ).

Managed PG Reg.ru (START-2 ~1k, START-4-8-50 ~5.8k) — **не 1:1**, без GoTrue/Storage/PostgREST.

## Рекомендации

1. **Сверить факт** в [Биллинг](https://console.yandex.cloud/billing) → детализация за полный месяц (SA terraform без `billing.viewer`).
2. **Не менять** на managed PG Reg.ru ради «дешевле 8500».
3. Если цель — экономия на железе: либо downsize/CVoS в YC, либо перенос **только** Supabase-ВМ на Reg.ru VPS (~4.4k), AI+Captcha оставить в YC.
4. После исчерпания гранта (~сентябрь 2026) always-on ~7.5k+usage станет реальной оплатой.

## Ссылки

- [Compute pricing](https://yandex.cloud/ru/docs/compute/pricing)
- [VPC pricing](https://yandex.cloud/ru/docs/vpc/pricing)
- [Reg.ru / Cloud VPS](https://www.reg.ru/vps/)
- Terraform: `infra/yandex-cloud/`
