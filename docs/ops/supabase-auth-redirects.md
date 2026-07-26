# Supabase Auth: redirect URLs для кабинета

Для восстановления пароля клиент вызывает
`resetPasswordForEmail(..., { redirectTo: 'https://cabinet.proverkastaza.ru/?mode=recover' })`.

Проект: `frualvycousvvyjivybu`  
Прямая ссылка: https://supabase.com/dashboard/project/frualvycousvvyjivybu/auth/url-configuration

В Dashboard → **Authentication → URL Configuration** должны быть:

- **Site URL:** `https://cabinet.proverkastaza.ru`
- **Additional Redirect URLs** (минимум):
  - `https://cabinet.proverkastaza.ru/**`
  - `https://cabinet.proverkastaza.ru/?mode=recover`
  - (временно, пока живёт старый домен) `https://cabinet.taxi-doroga-dobra.ru/**`

Без allow-list письмо recovery откроет ошибку redirect / не завершит смену пароля.

Сводка cutover: [cutover-manual-checklist.md](./cutover-manual-checklist.md).
