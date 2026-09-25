## Техническое задание для Яндекс Cloud AI-ассистента

### Цель
Применить уже записанный `metadata["ssh-keys"]` (оба ключа) к `~sfrfr/.ssh/authorized_keys` на ВМ `sfrfr-supabase-db-01`.

### Факт
После обновления `ssh-keys` (операция `fhmkr127m3d22qu3praa`) SSH с ноутбука **всё ещё** `Permission denied` для ключа `…UaTm` (проверено дважды, без reboot). Guest agent на лету ключ не применил.

### Шаги
1. **ДА — reboot** ВМ `sfrfr-supabase-db-01` (`fhmkkkr7if3ggu6h29uq`). Не delete.
2. Дождаться статуса **RUNNING**, IP `51.250.69.237` на месте.
3. Убедиться, что `metadata["ssh-keys"]` по-прежнему содержит **обе** строки:
   - `sfrfr:…0PZM github`
   - `sfrfr:…UaTm user.kraskimira89@gmail.com`
4. Краткий отчёт: операция reboot, статус RUNNING.

### Если после reboot SSH снова denied (план B — только по отдельному подтверждению)
Не делать сейчас. Сообщить нам; тогда отдельно разрешим `user-data` с `runcmd`, который **append** ключа в `authorized_keys` + `cloud-init clean` + reboot.

### Ограничения
- Не DNS, не UFW/Docker, не Lockbox, не менять SG.
- Не удалять ключи из `ssh-keys`.

### Критерии готовности
- ВМ RUNNING после reboot.
- Мы сами проверим: `ssh sfrfr@51.250.69.237`.

---
Это техническое задание для выполнения Яндекс-ассистентом.
