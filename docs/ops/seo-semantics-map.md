# Карта семантики SEO (ТЗ-18, этап 4)

**Дата:** 2026-08-13  
**Связано:** [seo-url-decision-map.md](seo-url-decision-map.md), [ТЗ-18](../specs/18-seo-strategy-and-implementation.md), [research калькулятор](../marketing-sales/research-seo-pension-queries-2026-08.md), [research 7 проблемных кластеров](../marketing-sales/research-seo-problem-clusters-wordstat-2026-08.md)

Формат строки: кластер → URL → интент → CTA → статус → обновлено.

## Коммерция и доверие

| Кластер | URL | Интент | CTA | Статус | Обновлено |
|---|---|---|---|---|---|
| Услуга проверки стажа | `/proverka-stazha/` | купить помощь / понять услугу; **отстройка от калькулятора пенсии** | заявка / MAX | live+keys | 2026-08-13 |
| Тарифы | `/tarify/` | цена | заявка | live | 2026-08 |
| Как работаем | `/kak-rabotaem/` | процесс и границы | MAX | live | 2026-08 |
| Контакты | `/kontakty/` | доверие / реквизиты | связаться | live | 2026-08 |
| Эксперт | `/expert/lopakova-nataliya/` | кто оказывает | услуга | live | 2026-08 |
| Главная | `/` | бренд + вход | MAX / заявка | live | 2026-08 |

## Информационное ядро (блог)

| Кластер | URL (slug) | Интент | CTA | Статус | Обновлено |
|---|---|---|---|---|---|
| Заказ ИЛС | `/blog/kak-zakazat-vypisku-ils/` | получить выписку | сверка / услуга | live | 2026-08 |
| Чтение ИЛС / стаж | `/blog/kak-proverit-stazh-v-vypiske-ils/` | понять выписку, **оценка стажа без фейкового калькулятора** | сверка / MAX | live+keys | 2026-08-13 |
| Сверка трудовая↔ИЛС | `/blog/kak-sverit-trudovuyu-knizhku-i-ils/` | найти расхождения | документы / услуга | live+keys | 2026-08-13 |
| Неучтённый период | `/blog/chto-delat-esli-period-raboty-ne-uchten/` | исправить пробел | архив / услуга | live | 2026-08 |
| Архив | `/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/` | подтвердить период | комплект | live | 2026-08 |
| Документы | `/blog/kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr/` | собрать комплект | подача / услуга | live | 2026-08 |
| Подача | `/blog/kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc/` | подать сам | услуга (подготовка) | live | 2026-08 |
| Отказ СФР | `/blog/otkaz-sfr-chto-proverit-v-dokumentah/` | разобрать отказ | диагностика | live | 2026-08 |
| Север | `/blog/severnyy-stazh-i-rayonnyy-koefficient/` | север / коэффициент | сверка | live | 2026-08 |
| FAQ | `/blog/chastye-voprosy-o-proverke-stazha/` | общие вопросы | MAX | live+keys | 2026-08-13 |
| Услуга vs калькулятор СФР | `/proverka-stazha/` + блок на FAQ/ИЛС | «пенсионный калькулятор / расчёт пенсии» | официальный калькулятор СФР + наша сверка | keys | 2026-08-13 |

## 7 проблемных кластеров (Wordstat PDF, mapped 2026-08-13)

| Кластер | URL live | Candidate PDF | Интент | CTA | Статус | Обновлено |
|---|---|---|---|---|---|---|
| Не учли / пропал стаж в ИЛС | `/blog/chto-delat-esli-period-raboty-ne-uchten/` | `/ne-uchli-stazh/` | проблемный | разобрать / услуга | mapped; gap commercial | 2026-08-13 |
| Стаж до 2002 | `/stazh-do-2002/` | `/stazh-do-2002/` | проблемный | чек-лист | **live** trust | 2026-08-14 |
| Архивная справка | `/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/` | `/arhivnaya-spravka-stazh/` | транзакционный | чек-лист | mapped | 2026-08-13 |
| Северный стаж / перерасчёт | `/proverka-severnogo-stazha/` + blog север | `/severnyj-stazh/` | высокая ценность | разобрать | mapped | 2026-08-13 |
| Отказ СФР | `/blog/otkaz-sfr-chto-proverit-v-dokumentah/` | `/otkaz-sfr/` | горячий | разобрать | mapped; gap commercial | 2026-08-13 |
| Выписка СЗИ-ИЛС | заказ + чтение ИЛС (blog) | `/proverka-ils/` | инфо / диагностика | сверить ИЛС | mapped | 2026-08-13 |
| Перед назначением пенсии | `/proverka-stazha-pered-pensiey/` | — | диагностика | разобрать | mapped | 2026-08-13 |

Таблица запросов Title/H1/CTA: [research-seo-problem-clusters-wordstat-2026-08.md](../marketing-sales/research-seo-problem-clusters-wordstat-2026-08.md). Частоты: [CSV](../marketing-sales/reports/wordstat-7-clusters-template.csv), добор 3–7 — [2026-08-14](../marketing-sales/reports/wordstat-3-7-tbd-2026-08-14.md).

## Решение по интенту «калькулятор»

| Решение | Деталь |
|---|---|
| Не создавать | Отдельный URL «калькулятор пенсии Онлайн» с суммой выплат от сервиса |
| Делать | Ключи и пояснения на существующих URL: ИЛС, сверка, услуга, FAQ |
| Официальный прогноз суммы | Ссылка на калькулятор/сведения СФР / Госуслуги; мы не подменяем |
| Наш продукт | Сверка документов и план обращения; решение о пенсии — только СФР |
| Канон копирайта | [`no-calculator-no-recalculation.md`](../../scripts/assets/copy/no-calculator-no-recalculation.md): нет калькулятора стажа / не ведём перерасчёт |
| CSV seed | кластер `8_calc` в [wordstat-7-clusters-template.csv](../marketing-sales/reports/wordstat-7-clusters-template.csv) |
| Частоты 2026-08-14 | [wordstat-8-calc-2026-08-14.md](../marketing-sales/reports/wordstat-8-calc-2026-08-14.md): стаж 89 718, расчет пенсии 75 770, пенсионный калькулятор 19 314; перерасчёт-калькулятор 130 |

## Обновление карты

Раз в SEO-спринте ([seo-sprint.md](seo-sprint.md)): сверить с Вебмастером/Wordstat, дописать кластеры, не плодить URL без уникального интента.
