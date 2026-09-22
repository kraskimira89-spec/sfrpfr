"""Создать issue FUNNEL: недельный чеклист реанимации (без ПДн)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "secrets" / "yandex-tracker.env"


def _load_env() -> None:
    if not ENV.is_file():
        raise SystemExit(f"Нет {ENV}")
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    _load_env()
    sys.path.insert(0, str(ROOT / "src"))
    from sfrfr.integrations.yandex_tracker import create_issue

    desc = """## Реанимация дел — недельный ритм

Канон: `docs/ops/playbook-case-reactivation.md`

### Автотика
- Timer: `sfrfr-case-reactivation.timer` (Пн–Пт 10:15 МСК)
- CLI: `sfrfr case-reactivation-due-tick`
- Env на VPS: `CASE_REACTIVATION_AUTO_SEND=1`

### Чеклист на неделю (копировать в комментарий)

```text
## Реанимация — неделя YYYY-MM-DD
- [ ] Timer active; лог sent/skipped/orphan
- [ ] Канбан: payment/docs/in_touch + просроченный next_action_at
- [ ] Корзина D: оплата без движения staff
- [ ] Корзина S: new без первого ответа > SLA
- [ ] 5 ответивших → next_action обновлён
- [ ] После №2 → archive / можно вернуться
- [ ] Нет касаний в F / не беспокоить
Вывод: …
Next: …
```

Без ПДн; `case_ref` = последние 4 символа id.
"""
    result = create_issue(
        summary="Недельный чеклист реанимации CRM + orphan MAX",
        description=desc,
        tags=["funnel-reactivation", "funnel-lead", "funnel-qualify"],
        priority="normal",
        queue="FUNNEL",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
