# SSH на VPS «Проверка стажа»

Хост: **91.229.11.147** (`proverkastaza.ru`). Пользователь: `root`. Порт: `22`.

Пароли и приватные ключи в этот файл **не** пишем. Ключи только на диске ПК и в GitHub Secrets `VPS_*`.

## Быстрый вход с ПК владельца

После записи в `~/.ssh/config`:

```powershell
ssh sfrfr-vps
```

Алиас `proverkastaza` — то же самое.

Конфиг (локально, не в git):

```text
Host sfrfr-vps proverkastaza
  HostName 91.229.11.147
  User root
  IdentityFile ~/.ssh/id_ed25519
  IdentityFile ~/.ssh/sfrfr-deploy/id_ed25519_sfrfr_deploy
  IdentitiesOnly yes
```

Без алиаса:

```powershell
ssh -i $HOME\.ssh\id_ed25519 root@91.229.11.147
# запасной ключ деплоя:
ssh -i $HOME\.ssh\sfrfr-deploy\id_ed25519_sfrfr_deploy root@91.229.11.147
```

## Какие ключи должны быть в `authorized_keys`

На сервере у `root` должны быть **публичные** ключи:

- личный ПК (`id_ed25519.pub`, комментарий вроде `user.kraskimira89@gmail.com`);
- ключ GitHub Actions / деплоя (`sfrfr-deploy/id_ed25519_sfrfr_deploy.pub`).

Добавить новый ключ (подставьте содержимое `.pub`):

```bash
umask 077
mkdir -p ~/.ssh
# echo 'ssh-ed25519 AAAA... comment' >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Не класть приватный ключ на VPS и не коммитить его в репозиторий.

## Что смотреть на сервере

| Путь | Назначение |
|------|------------|
| `/opt/sfrfr` | код API / скрипты деплоя |
| `/opt/sfrfr/.env` | секреты приложения |
| `/var/www/taxi-doroga-dobra` | WordPress-витрина |
| `/root/.sfrfr-secrets/` | локальные секреты (WP и т.п.) |

Автодеплой: `push` в `main` → Actions `deploy-vps.yml`. Ручной `vps_deploy.sh` не запускать, пока в очереди уже есть `deploy-vps`.

См. также: [deploy-vps.md](../deploy-vps.md), [vps-secrets-checklist.md](../vps-secrets-checklist.md).
