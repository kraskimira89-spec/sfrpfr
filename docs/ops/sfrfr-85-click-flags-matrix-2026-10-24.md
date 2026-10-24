# SFRFR-85 — клик soft-ask ≠ доказательство анализа (матрица 2026-10-24)

**Задача:** [SFRFR-85](https://tracker.yandex.ru/SFRFR-85) · parent [SFRFR-82](https://tracker.yandex.ru/SFRFR-82)  
**Исходный main (на момент среза):** `7e18c2dd…` (+ #259 не обязателен)  
**Код:** `brief_analysis.preserve_gaps_after_soft_ask_yes`, `ensure_brief_flags_for_offer`, `diag_choice`  

Живые сообщения / клиентские данные / платежи **не** трогали.

## Критерий задачи

> Клик soft-ask восстанавливает право на оффер, но **не** является доказательством того, что анализ документов выполнен. Paid не откатывается к повторной продаже.

## Событие → изменение состояния → разрешённое утверждение → тест

| Событие | Что меняется в `q_answers` | Разрешено утверждать | Запрещено утверждать | Тест |
|---|---|---|---|---|
| Холодный клик `diag:detail_yes` **без** prior soft-ask/brief | **ничего** (early return) | — | discrepancy / completed / summary_shown | `test_preserve_without_prior_soft_ask_does_not_invent_completed` |
| Soft-ask уже ушёл (`SOFT_ASK_SENT` или `DETAIL_PENDING`) + клик | `SOFT_ASK_SENT=1`, `DISCREPANCY=1`, `OFFER_REVIVE=1`; при отсутствии — поднимает `STATUS_COMPLETED`, `OK`, `CURRENT`, `SUMMARY_SHOWN`; при пустом summary — подставляет revive-текст | «клиент согласился на подробный разбор»; «офер можно снова показать» (`OFFER_REVIVE`) | «клик доказал OCR/findings»; «эксперт подтвердил» | `test_detail_yes_after_soft_ask_*`, heal/preserve suite |
| Brief реально посчитан + soft-ask доставлен | `STATUS_COMPLETED`, discrepancy по compute, `SUMMARY_SHOWN` после delivery | «краткий разбор показан»; evidence из compute | — | `test_run_brief_delivers_soft_ask` |
| Restart / потеря флагов при prior soft-ask | `ensure_brief_flags_for_offer` / preserve | gaps не откатываются в 0 | выдуманный completed без soft-ask | `test_heal_does_not_downgrade_soft_ask_gaps`, `test_restart_preserves_*` |
| Уже paid DIAG + клик | ветка already_paid в `diag_choice` | next step, не новый офер | повторная продажа | `test_max_diag_choice` / paid path (см. suite) |

## Пробелы (безопасный разбор)

| ID | Наблюдение | Класс | Действие |
|---|---|---|---|
| G1 | При prior soft-ask preserve **поднимает** `STATUS_COMPLETED`/`SUMMARY_SHOWN` даже если флаги были потеряны | thin / продуктовый | Документировано: soft-ask шлётся только после реального brief; revive помечает `OFFER_REVIVE`. Отдельный дефект **не** подтверждаем без критерия «completed только от compute». |
| G2 | Нет явного unit: «после revive gate видит OFFER_REVIVE, а evidence_kinds не становятся docs от клика» | thin | Можно добавить тест только; код не ломать |
| G3 | Live MAX: клик → офер без фальш-анализа | live | Отдельный запрос разрешения |

**Дефекта, требующего правки working code в этом срезе, не зафиксировано.**  
Следующий шаг: при необходимости тест G2 отдельным PR без auto-merge; иначе — ждать ревью/85 критериев владельца.

## Связь с SFRFR-84

Критерий #16 матрицы 84 = эта задача. Передача **не** закрывает 84.
