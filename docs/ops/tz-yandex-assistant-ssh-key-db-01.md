## Техническое задание для Яндекс Cloud AI-ассистента

### Цель
Добавить второй SSH pubkey пользователю `sfrfr` на ВМ `sfrfr-supabase-db-01` и применить его через **reboot** (metadata + cloud-init). ВМ ещё **не** в DNS cutover (`supabase.proverkastaza.ru` указывает на `51.250.13.240`) — короткий reboot допустим.

### Контекст
- ВМ: `sfrfr-supabase-db-01` / `fhmkkkr7if3ggu6h29uq` / IP `51.250.69.237`
- Каталог: `b1grtprgfugidt9u073i`
- Пользователь: `sfrfr`
- Текущий ключ (сохранить): `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAh5DSXS+s8Y7ylwU3vMEOzzafTMGx9MTYN9e7hz0PZM`
- Добавить: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm user.kraskimira89@gmail.com`
- Понимаем: без reboot cloud-init не обновит `authorized_keys` при смене user-data
- `metadata["ssh-keys"]` не трогать, если у вас это иммутабельно — достаточно user-data + reboot

### Шаги
1. **Да** — обновить `user-data`: у `sfrfr` в `ssh_authorized_keys` оба ключа (`…0PZM` и `…UaTm`).
2. **Да** — выполнить **reboot** ВМ `sfrfr-supabase-db-01` (не delete, не stop насовсем — именно перезагрузка).
3. Дождаться статуса RUNNING после reboot.
4. Вернуть: подтверждение обоих ключей в user-data; время reboot; статус ВМ.

### После reboot (не делать ассистенту — сделаем с ноутбука)
Мы сами: `ssh sfrfr@51.250.69.237` → `ufw allow 80,443` → проверка Docker.

### Ограничения
- Не delete ВМ, не менять диски, не менять SG (80/443/22 уже ок).
- Не менять DNS, не трогать `b1g0mhpm9tr4lrurk1bu` / Lockbox.
- Не удалять ключ `…0PZM`.
- Не открывать Postgres в интернет.

### Критерии готовности
- user-data содержит оба pubkey.
- ВМ снова RUNNING после reboot.
- Краткий отчёт в ответе.

---
Это техническое задание для выполнения Яндекс-ассистентом.
