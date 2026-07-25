# Supabase Auth: redirect URLs для кабинета

Для восстановления пароля клиент вызывает
`resetPasswordForEmail(..., { redirectTo: 'https://cabinet.taxi-doroga-dobra.ru/?mode=recover' })`.

В Dashboard проекта → **Authentication → URL Configuration** должны быть:

- **Site URL:** `https://cabinet.taxi-doroga-dobra.ru`
- **Additional Redirect URLs** (минимум):
  - `https://cabinet.taxi-doroga-dobra.ru/**`
  - `https://cabinet.taxi-doroga-dobra.ru/?mode=recover`

Без allow-list письмо recovery откроет ошибку redirect / не завершит смену пароля.
