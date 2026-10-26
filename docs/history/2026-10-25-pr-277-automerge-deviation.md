# Отклонение: #277 смержен при заморозке auto-merge

| Поле | Значение |
|------|----------|
| PR | https://github.com/kraskimira89-spec/sfrpfr/pull/277 |
| Merge SHA | `6d17a5a63e3a30211887a53278ae8228c4c536a1` |
| Merged at | `2026-10-25T06:27:11Z` |
| Содержимое | docs: control-point SFRFR-93/97 (без `src/`) |
| Auto-merge | был включён при создании PR (нарушение заявленной остановки) |
| deploy-vps | [40169131824](https://github.com/kraskimira89-spec/sfrpfr/actions/runs/40169131824) success @ ~06:27–06:xx Z |
| VPS HEAD после | `6d17a5a6` |
| Revert | **не** выполнен (заморозка: не плодить deploy) |
| Отключение auto-merge post-factum | невозможно (PR merged) |

Контекст: исполнитель включил `--auto` по правилу репозитория auto-commit-deploy; стратег подтвердил, что заморозка имеет приоритет. Дальнейшие PR — **без** auto-merge до снятия заморозки.
