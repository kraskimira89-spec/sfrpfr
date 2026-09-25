## Техническое задание для Яндекс Cloud AI-ассистента

### Цель
Реально добавить SSH-ключ `…UaTm` в `~sfrfr/.ssh/authorized_keys` на **уже запущенной** ВМ `sfrfr-supabase-db-01`. Предыдущий шаг (user-data + reboot) **не сработал**: с ноутбука `ssh` предлагает ключ `…UaTm`, сервер отвечает `Permission denied (publickey)`.

### Доказательство
- Локальный pubkey: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm`
- IP клиента в SG: `185.77.216.28` (22 открыт)
- SSH debug: `Offering public key …UaTm` → `Authentications that can continue: publickey` → denied
- Вывод: cloud-init **не** перезаписал `authorized_keys` при reboot (модуль users обычно once-per-instance)

### Контекст
- ВМ id: `fhmkkkr7if3ggu6h29uq`, IP `51.250.69.237`, user `sfrfr`
- Каталог: `b1grtprgfugidt9u073i`
- Сохранить ключ GitHub: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAh5DSXS+s8Y7ylwU3vMEOzzafTMGx9MTYN9e7hz0PZM`

### Шаги (обязательно вариант с `ssh-keys`)
Владелец **явно разрешает** изменить `metadata["ssh-keys"]` (исключение из вашей иммутабельности для этой задачи).

1. Установить metadata `ssh-keys` так, чтобы были **оба** ключа (многострочно), формат YC:
```text
sfrfr:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAh5DSXS+s8Y7ylwU3vMEOzzafTMGx9MTYN9e7hz0PZM github
sfrfr:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm user.kraskimira89@gmail.com
```
2. Не удалять первый ключ. Не затирать другими метаданными.
3. Если guest agent применяет ключи без reboot — reboot **не** делать.
4. Если по доке YC нужен reboot после смены `ssh-keys` — сделать reboot и дождаться RUNNING.
5. Если политика всё же запрещает `ssh-keys`: вернуть **точные** шаги UI консоли (Compute → ВМ → изменить → SSH-ключи) с тем же содержимым, без выполнения.

### Ограничения
- Не DNS, не UFW/Docker с вашей стороны, не Lockbox, не delete ВМ.
- Не открывать 5432/5433/8000 в SG.

### Критерии готовности
- Подтверждение, что `ssh-keys` содержит обе строки `sfrfr:…`.
- Статус ВМ RUNNING.
- Мы проверим SSH с ноутбука сами.

---
Это техническое задание для выполнения Яндекс-ассистентом.
