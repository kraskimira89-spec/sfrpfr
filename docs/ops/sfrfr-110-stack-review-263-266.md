# Этап 2 — ревью стека #263 / #266 (точные head)

Дата ревью: 2026-10-24.
**Auto-merge OFF. Merge не выполнен и этим отчётом не разрешается.**

| PR | Title | head SHA | base |
|---|---|---|---|
| #261 | library | `71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01` | OPEN |
| #263 | E05/F04 wire | `4363f9f8d1dbfe6b9c347671634fb1e459754a5c` | #261 |
| #265 | date write audit | `263d629bd06bd3f1456858b7e72ca358d5bd63a2` | OPEN (зависимость от #263; **не** вложена в #266) |
| #266 | max_llm_reply postfilter | `82e3916f82aaa69df27be39b1675d292f4972b92` | #263 |

Локальная docs-ветка `docs/sfrfr-110-close-dod-matrix` = head #266 `82e3916f…`.

---

## #266 — чеклист ТЗ §5

| # | Требование | Вердикт | Доказательство / пробел |
|---|---|---|---|
| 1 | Смешанные цитаты, отрицания, самостоятельные утверждения | **OK (срез)** | `_mask_quoted_spans` + `_is_locally_negated` (локально перед маркером); целый ответ заменяется при любом untrusted claim |
| 2 | Ack привязан к операции, делу, версии | **OK для LIMIT** | `_claim_trusted(LIMIT_APPLIED)` → `load_for_case` + `belongs_to` + `limit_outcome()==success`; DATE/REFUND/CLAIM/ASSIGNEE — всегда False |
| 3 | Нельзя разрешить дату/возврат через ack ограничения | **OK** | разные `ClaimKind`; limit ack не трогает DATE_FIXED / REFUND_DONE |
| 4 | Fallback + снятие несовместимых кнопок | **OK** | `ACTION_CLAIM_SAFE_FALLBACK` + `_strip_keyboards` |
| 5 | Нет обхода через пустой policy-ответ | **OK на пути** | фильтр после coerce/LLM в `reply_to_free_text` (см. контракт фильтра); пустой policy → LLM → filter |
| 6 | Нет post-check правки текста, возвращающей запрет | **OK** | при block текст целиком safe; нет частичного rewrite |
| 7 | Явная граница лексического покрытия | **OK / ограничение** | docstring + `docs/ops/sfrfr-110-max-llm-action-claim-filter.md`: перечисленные маркеры ≠ универсальная достоверность |

**Остаток #266 (не блокер merge-решения владельца, блокер close SFRFR-110):** другие outbound; синонимы вне regex; prod Null → filter чаще режет, чем разрешает.

---

## #263 — чеклист ТЗ §5

| Требование | Вердикт | Комментарий |
|---|---|---|
| Различимость «не мой сценарий» / «недостаточно фактов» / «ответ подготовлен» / «доставка не подтверждена» | **Частично OK** | `try_policy_reply_for_case` → None (не сценарий) vs coerce empty → LLM; policy text vs outbox enqueue outcome разделены в `deliver_policy_reply_via_outbox` / tests. Клиентский UX «доставка не подтверждена» ещё не универсален |
| Нет двойной отправки из caller | **OK (срез)** | E05 path только outbox `action=max_e05_f04_policy`; caller не дублирует `_reply` при принятом policy |
| Нет caller-retry поверх принятого outbox | **OK (срез)** | повторный смысл — зона worker/guards; см. `max-e05-f04-delivery-risks.md` |
| Fallback при неопределённом enqueue | **Частично** | классификация UNKNOWN в guards; слепой второй механизм на этом пути не включён; полный recovery route — этап 6 |

**Ограничения среза (не prod-доказательство):**

- `NullTrustedErrorContextAdapter` → нет перехвата (безопасно, но не coverage).
- `InMemory` + fake enqueue/bot ≠ транзакция БД / реальный transport.
- E05/F04 с тестовым источником **не** закрывает DoD.

---

## CI / локальные тесты (реестр)

Перепроверить перед любым merge. Не сравнивать «25 vs 28» без команды+SHA.

```text
Код среза (#266 head): 82e3916f82aaa69df27be39b1675d292f4972b92
Docs-ветка на момент прогона: 5f7d8fc6… (поверх #266; без смены кода фильтра/wire)
Команда:
  .\.venv\Scripts\python.exe -m pytest ^
    tests/unit/test_max_e05_f04_wire_path.py ^
    tests/unit/test_max_sfrfr110_e05_f04_slice.py ^
    tests/unit/test_max_llm_action_claim_filter.py -q --basetemp=.tmp_pytest_sfrfr110
Результат: 49 passed (2026-10-24, локально)
```

GitHub Checks на #263/#266 — смотреть UI на указанных head; локальный зелёный ≠ CI head.
Не сравнивать 49 с другими наборами без той же команды+SHA.

---

## Итог этапа 2

| Вопрос | Ответ |
|---|---|
| Готовы ли #263/#266 к **отдельному** merge по разрешению владельца? | Технически ревью среза: **да, с явными ограничениями DoD**; решение merge — только владелец |
| Закрывает ли стек SFRFR-110? | **Нет** |
| Следующий реализационный PR | Точечная операция исправления даты (см. `sfrfr-110-next-date-op-pr-plan.md`) |
| Merge / deploy / live / миграции этим отчётом | **Не разрешены** |

Рекомендация: **не закрывать** SFRFR-110; продолжать этап 3 после разрешения на реализацию (без merge стека без отдельного OK).
