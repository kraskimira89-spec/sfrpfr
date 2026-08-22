# Карта решений по URL блога (ТЗ-18, недели 3–6)

Дата: 2026-08-03  
Источник: `scripts/assets/blog/` + live sitemap + `situations/html/index.json`.

Легенда: **ядро** | **поддержка** | **noindex+301** | **оставить** | **усилить**.

Итого публичных blog-URL ≈ **51** (21 индексных + 30 thin), плюс витрина trust вне блога.

## Кластеры → целевые страницы

| Кластер | Ядро (индекс) | Thin → 301 |
|---|---|---|
| ИЛС / заказ / чтение | `kak-zakazat-vypisku-ils`, `kak-proverit-stazh-v-vypiske-ils` | S03, S19 → ИЛС; заказ — отдельный hub |
| Сверка трудовая ↔ ИЛС | `kak-sverit-trudovuyu-knizhku-i-ils` | S05, S15 → сверка |
| Неучтённый период | `chto-delat-esli-period-raboty-ne-uchten` | S08 |
| Архив | `arhivnaya-spravka-dlya-sfr-zachem-i-kuda` | S09 |
| Документы / комплект | `kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr` | S16, S20 |
| Подача | `kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc`, `chek-list-pered-zapisju-v-mfc` | — |
| Отказ / границы СФР | `otkaz-sfr-chto-proverit-v-dokumentah`, `pochemu-reshenie-prinimaet-tolko-sfr` | S13, S24, A03 |
| Север | `severnyy-stazh-i-rayonnyy-koefficient` | S02, S04, S06, S21, S25, A01 |
| Льготный / пед. | `lgotnyy-i-pedagogicheskiy-stazh` | S01, S12, S23, A05 |
| ЕДВ | `edv-i-pensiya-chto-proveryat-otdelno` | S10, S14, S18, A02 |
| ФИО / трудовая | `rashozhdeniya-fio-i-zapisi-trudovoy` | S17, S22, A04 |
| Навигация сценариев | `tipichnye-situacii-proverki-stazha` | S07, S11 |
| Услуга / FAQ | `chem-otlichaetsya-…`, `chto-vy-poluchite-…`, `kak-rabotat-v-max-…`, `chastye-voprosy-…`, `kak-pomoch-rodstvenniku-…`, `pensiya-po-invalidnosti-…` | — |

## Ядро индексации (15 страниц)

1. `kak-zakazat-vypisku-ils` — hub заказ ИЛС  
2. `kak-proverit-stazh-v-vypiske-ils` — pillar ИЛС  
3. `kak-sverit-trudovuyu-knizhku-i-ils` — pillar сверка  
4. `chto-delat-esli-period-raboty-ne-uchten` — pillar неучтённый  
5. `arhivnaya-spravka-dlya-sfr-zachem-i-kuda` — pillar архив  
6. `kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr`  
7. `kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc` — pillar подача  
8. `otkaz-sfr-chto-proverit-v-dokumentah` — pillar отказ  
9. `severnyy-stazh-i-rayonnyy-koefficient`  
10. `edv-i-pensiya-chto-proveryat-otdelno`  
11. `lgotnyy-i-pedagogicheskiy-stazh`  
12. `rashozhdeniya-fio-i-zapisi-trudovoy`  
13. `tipichnye-situacii-proverki-stazha`  
14. `chastye-voprosy-o-proverke-stazha`  
15. `kak-pomoch-rodstvenniku-proverit-stazh`

**Поддержка (индекс, не ядро):** чек-лист МФЦ, диагностика vs сопровождение, границы СФР, результат проверки, MAX/кабинет, инвалидность и стаж.

## Thin: noindex + 301

Все `primer-*` / `analitika-*` уже **noindex** и вне sitemap.  
С 2026-08-03 включены **301** в MU `sfrfr-seo-redirects.php` (карта slug → hub/pillar).

| Бывшие кейсы | 301 → |
|---|---|
| S01, S12, S23, A05 | `lgotnyy-i-pedagogicheskiy-stazh` |
| S02, S04, S06, S21, S25, A01 | `severnyy-stazh-i-rayonnyy-koefficient` |
| S03, S19 | `kak-proverit-stazh-v-vypiske-ils` |
| S05, S15 | `kak-sverit-trudovuyu-knizhku-i-ils` |
| S07, S11 | `tipichnye-situacii-proverki-stazha` |
| S08 | `chto-delat-esli-period-raboty-ne-uchten` |
| S09 | `arhivnaya-spravka-dlya-sfr-zachem-i-kuda` |
| S10, S14, S18, A02 | `edv-i-pensiya-chto-proveryat-otdelno` |
| S13, A03 | `otkaz-sfr-chto-proverit-v-dokumentah` |
| S16, S20 | `kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr` |
| S17, S22, A04 | `rashozhdeniya-fio-i-zapisi-trudovoy` |
| S24 | `pochemu-reshenie-prinimaet-tolko-sfr` |

Контент thin на диске сохранён как черновик; публичный URL уходит на hub.

## Технические URL

| URL | Решение |
|---|---|
| `/glavnaya/` | **301** → `/` |
| `/prezentaciya-dlya-deputata/` | **301** → `/partneram/` (канон посадочной для партнёров) |
| `/partneram/` | **index** — посадочная для приёмных, НКО и партнёров |
| `/app/` | **noindex,nofollow,noarchive** |
| рубрики `situacii`, `analitika` | noindex + вне sitemap |

## Hub’ы (порядок ТЗ)

| Hub | Статус |
|---|---|
| Заказ ИЛС | **добавлен** `kak-zakazat-vypisku-ils` |
| Северный стаж | уже был |
| ЕДВ | уже был |
| Льготный / пед. | уже был |
| ФИО / трудовая | уже был (консолидация) |

Новые hub’ы вне таблицы — **не создавать**, пока ядро не стабилизируется в Вебмастере.

## Статус внедрения

- [x] Кластеры + ядро 15
- [x] Усиление pillar (ИЛС, сверка, неучтённый, архив, подача, отказ)
- [x] Hub заказ ИЛС
- [x] noindex thin + 301 map
- [x] Deploy + live audit + recrawl (2026-08-03)
