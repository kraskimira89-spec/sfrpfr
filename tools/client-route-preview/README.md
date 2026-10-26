# Устаревший HTML-preview

Не использовать для приёмки PR #284.

Канон: React-preview реального `CaseWorkMap` + `CaseRoutePanel` + чат справа:

```text
cd apps/cabinet
npx next dev -p 3011
# http://localhost:3011/dev/route-preview?s=upload
```

Приёмка: весь экран — этапы слева, чат справа (`cabinet-case-layout` ≥960px).
В production страница отвечает 404, пока не задан `ALLOW_ROUTE_PREVIEW=1`.
