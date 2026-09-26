## Техническое задание для Яндекс Cloud AI-ассистента

### Цель
Гарантированно прописать ключ `…UaTm` в `/home/sfrfr/.ssh/authorized_keys` на ВМ `sfrfr-supabase-db-01`.  
Проверка после reboot `fhmcvq4q7009kp8oj07r`: SSH с ноутбука снова **Permission denied** — утверждение «cloud-init применил ключи в authorized_keys» **не подтверждено**.

### Контекст
- ВМ: `fhmkkkr7if3ggu6h29uq` / `51.250.69.237` / user `sfrfr`
- `metadata["ssh-keys"]` уже содержит оба ключа — **не удалять**
- Локальный pubkey OK, TCP/22 в SG открыт (`146.158.1.12/32` — домашний IP администратора, `91.229.11.147/32` — jump App-VPS) — проблема только в `authorized_keys` на диске
- DNS / Lockbox / старый каталог — не трогать

### Шаги (план B)
1. Прочитать текущий `metadata["user-data"]` (полный YAML).
2. **Дополнить** (не заменить целиком слепо) секцией, которая на **каждой** загрузке гарантирует ключи. Использовать **`bootcmd`** (выполняется каждый boot), не одноразовый `runcmd`:

```yaml
bootcmd:
  - |
    install -d -m 700 -o sfrfr -g sfrfr /home/sfrfr/.ssh
    touch /home/sfrfr/.ssh/authorized_keys
    chown sfrfr:sfrfr /home/sfrfr/.ssh/authorized_keys
    chmod 600 /home/sfrfr/.ssh/authorized_keys
    grep -q 'AAAAIAh5DSXS+s8Y7ylwU3vMEOzzafTMGx9MTYN9e7hz0PZM' /home/sfrfr/.ssh/authorized_keys \
      || echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAh5DSXS+s8Y7ylwU3vMEOzzafTMGx9MTYN9e7hz0PZM github' >> /home/sfrfr/.ssh/authorized_keys
    grep -q 'AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm' /home/sfrfr/.ssh/authorized_keys \
      || echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm user.kraskimira89@gmail.com' >> /home/sfrfr/.ssh/authorized_keys
    chown sfrfr:sfrfr /home/sfrfr/.ssh/authorized_keys
    chmod 600 /home/sfrfr/.ssh/authorized_keys
```

3. Сохранить прежние части user-data (users, packages, ufw runcmd и т.д.), только **добавить/смержить** `bootcmd`.
4. Выполнить **reboot** ВМ, дождаться RUNNING.
5. Вернуть: фрагмент user-data с `bootcmd`, id операции reboot, статус RUNNING.

### Ограничения
- Не wipe всего user-data.
- Не менять DNS, SG, диски; не delete ВМ.
- Не открывать Postgres наружу.
- Не читать Lockbox.

### Критерии готовности
- В user-data есть bootcmd с обоими ключами.
- ВМ RUNNING после reboot.
- Мы проверим SSH сами; если OK — дальше UFW 80/443.

---
Это техническое задание для выполнения Яндекс-ассистентом.
