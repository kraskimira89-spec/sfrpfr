# Supabase Auth: redirect URLs для кабинета

Для восстановления пароля клиент вызывает
`resetPasswordForEmail(..., { redirectTo: 'https://cabinet.proverkastaza.ru/?mode=recover' })`.

В Dashboard проекта → **Authentication → URL Configuration** должны быть:

- **Site URL:** `https://cabinet.proverkastaza.ru`
- **Additional Redirect URLs** (минимум):
  - `https://cabinet.proverkastaza.ru/**`
  - `https://cabinet.proverkastaza.ru/?mode=recover`
  - (временно, пока живёт старый домен) `https://cabinet.taxi-doroga-dobra.ru/**`

Без allow-list письмо recovery откроет ошибку redirect / не завершит смену пароля.
