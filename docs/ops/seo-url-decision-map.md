# Карта решений по URL блога (ТЗ-18)

Дата: 2026-07-29  
Источник аудита: материалы `scripts/assets/blog/` + live `seo_production_audit.py`.

Легенда: **оставить** | **усилить** | **объединить → hub** | **noindex** | **301**.

## Индексируемые pillar / инструкции

| URL (slug) | Решение | Комментарий |
|---|---|---|
| `/` | оставить | Главная услуга |
| `/blog/` | оставить | Архив |
| `kak-proverit-stazh-v-vypiske-ils` | усилить | Pillar ИЛС |
| `kak-sverit-trudovuyu-knizhku-i-ils` | усилить | Pillar сверка |
| `chto-delat-esli-period-raboty-ne-uchten` | усилить | Pillar неучтённый период |
| `arhivnaya-spravka-dlya-sfr-zachem-i-kuda` | усилить | Документы / архив |
| `kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr` | усилить | Документы |
| `kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc` | усилить | Подача |
| `otkaz-sfr-chto-proverit-v-dokumentah` | усилить | Отказ |
| `chek-list-pered-zapisju-v-mfc` | оставить | Узкий чек-лист |
| `kak-pomoch-rodstvenniku-proverit-stazh` | усилить | Родственники |
| `tipichnye-situacii-proverki-stazha` | оставить | Хаб ситуаций |
| `chem-otlichaetsya-diagnostika-ot-soprovozhdeniya` | оставить | Услуга |
| `pochemu-reshenie-prinimaet-tolko-sfr` | оставить | Границы |
| `chto-vy-poluchite-posle-proverki-stazha` | оставить | Результат |
| `kak-rabotat-v-max-i-lichnom-kabinete` | оставить | Канал |
| `chastye-voprosy-o-proverke-stazha` | усилить | FAQ |
| `pensiya-po-invalidnosti-i-stazh-na-chto-smotret` | оставить | Отдельный интент |
| `severnyy-stazh-i-rayonnyy-koefficient` | усилить (новый hub) | Консолидация северных кейсов |
| `edv-i-pensiya-chto-proveryat-otdelno` | усилить (новый hub) | Консолидация ЕДВ |
| `lgotnyy-i-pedagogicheskiy-stazh` | усилить (новый hub) | Консолидация льготного/пед. |
| `rashozhdeniya-fio-i-zapisi-trudovoy` | усилить (новый hub) | ФИО / ошибки трудовой |

## Ситуации и аналитика → noindex (+ исключение из sitemap)

Все `primer-*` и `analitika-*` в рубриках `situacii` / `analitika`: **noindex,follow**.  
Контент сохранён как справочный; поисковый спрос закрывают hub-страницы.

| Бывшие кейсы | Объединить в |
|---|---|
| S01, S23, A05 | `lgotnyy-i-pedagogicheskiy-stazh` (+ северный hub) |
| S02, S04, S21, S25, A01 | `severnyy-stazh-i-rayonnyy-koefficient` |
| S03, S15, S19 | `kak-proverit-stazh-v-vypiske-ils`, `kak-sverit-trudovuyu-knizhku-i-ils` |
| S08 | `chto-delat-esli-period-raboty-ne-uchten` |
| S09 | `arhivnaya-spravka-dlya-sfr-zachem-i-kuda` |
| S10, S14, S18, A02, A04 | `edv-i-pensiya-chto-proveryat-otdelno` |
| S13, A03 | `otkaz-sfr-chto-proverit-v-dokumentah` |
| S17, S22 | `rashozhdeniya-fio-i-zapisi-trudovoy` |
| S24 | `pochemu-reshenie-prinimaet-tolko-sfr` / отказ |

301 с `primer-*` на hub **не включаем массово** до появления устойчивого спроса в Вебмастере (риск потери полезных deep-link). При появлении трафика — точечные 301 по этой таблице.

## Технические URL

| URL | Решение |
|---|---|
| `/glavnaya/` | **301** → `/` |
| `/app/` | **noindex,nofollow,noarchive** |
| кабинет / admin / api | вне публичного sitemap |
| рубрики `situacii`, `analitika` | noindex + вне sitemap |

## Статус внедрения

- [x] Карта зафиксирована
- [x] Hub HTML + seed
- [x] noindex thin + sitemap exclude (MU)
- [x] repair descriptions
- [ ] Deploy + live audit (в конце задачи)
