# Чеклист: GitHub secrets + bootstrap VPS

## Что нужно от вас

Пришлите (в чат или выполните скрипт сами):

| Параметр | Пример |
|----------|--------|
| IP / hostname VPS | `91.229.11.147` |
| SSH-пользователь | `root` или `ubuntu` |
| Порт SSH | `22` (если не стандартный — укажите) |

Пароль в чат **не** присылайте. Достаточно IP + user; ключ создадим локально.

## Вариант А — одной командой на вашем ПК

```powershell
cd c:\Users\user\Documents\Cursor\SFRFR
.\scripts\setup_github_vps_secrets.ps1 -VpsHost YOUR_IP -VpsUser root
```

Скрипт:

1. Создаст ключ `~/.ssh/sfrfr-deploy/id_ed25519_sfrfr_deploy`
2. Запишет в GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_PORT`, `VPS_SSH_KEY`
3. Напечатает **публичный** ключ и команды для VPS

## Вариант B — вручную в GitHub UI

1. Откройте: https://github.com/kraskimira89-spec/sfrpfr/settings/secrets/actions  
2. New repository secret:

| Name | Value |
|------|-------|
| `VPS_HOST` | IP сервера |
| `VPS_USER` | SSH-логин |
| `VPS_PORT` | `22` |
| `VPS_SSH_KEY` | весь текст **приватного** ключа `-----BEGIN ... PRIVATE KEY-----` |

Ключ можно создать так:

```powershell
mkdir $HOME\.ssh\sfrfr-deploy -Force
ssh-keygen -t ed25519 -f $HOME\.ssh\sfrfr-deploy\id_ed25519_sfrfr_deploy -N '""' -C "github-actions-sfrfr"
```

## На VPS — один раз (bootstrap)

Подключитесь:

```powershell
ssh -i $HOME\.ssh\sfrfr-deploy\id_ed25519_sfrfr_deploy USER@HOST
```

На сервере:

```bash
# публичный ключ Actions уже должен быть в authorized_keys (скрипт подскажет)

sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip

cd /tmp
git clone https://github.com/kraskimira89-spec/sfrpfr.git sfrpfr-tmp
cd sfrpfr-tmp

sudo REPO_URL=https://github.com/kraskimira89-spec/sfrpfr.git \
  APP_DIR=/opt/sfrfr \
  APP_USER=sfrfr \
  bash scripts/vps_bootstrap.sh

# sudo для деплоя (подставьте своего SSH-пользователя вместо root)
echo 'root ALL=(root) NOPASSWD: /bin/bash /opt/sfrfr/scripts/vps_deploy.sh, /bin/systemctl restart sfrfr-api, /bin/systemctl is-active sfrfr-api' \
  | sudo tee /etc/sudoers.d/sfrfr-deploy
sudo chmod 440 /etc/sudoers.d/sfrfr-deploy

sudo nano /opt/sfrfr/.env   # заполнить ключи
sudo systemctl restart sfrfr-api
sudo systemctl status sfrfr-api
```

Репозиторий публичный — `git clone` по HTTPS без токена обычно работает. Если сделаете private — нужен deploy key или PAT.

## Проверка

```powershell
gh secret list -R kraskimira89-spec/sfrpfr
gh workflow run deploy-vps.yml -R kraskimira89-spec/sfrpfr
gh run list -R kraskimira89-spec/sfrpfr -L 3
```

## Если нет доступа к VPS сейчас

1. Секреты всё равно можно завести скриптом (когда будет IP).  
2. Bootstrap — только когда есть SSH на машину.  
3. До bootstrap workflow `deploy` будет падать с сообщением «каталог не инициализирован» — это ожидаемо.
