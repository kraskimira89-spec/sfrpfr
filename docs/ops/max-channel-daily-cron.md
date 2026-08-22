# Ежедневные черновики канала MAX (полуавто)

**Дата:** 2026-08-22  
**Режим:** cron/systemd шлёт **один** пост в личку ops → человек жмёт **Опубликовать**.  
**Не** `--direct` в клиентский канал.

## Очередь

- Список id: [`scripts/assets/max-channel/daily-queue.json`](../../scripts/assets/max-channel/daily-queue.json)
- Тексты: [`scripts/assets/max-channel/starter-posts.json`](../../scripts/assets/max-channel/starter-posts.json)
- State (VPS + локально, не в git): `storage/max_channel_daily_state.json`

## Команды

```powershell
.\.venv\Scripts\Activate.ps1
sfrfr max-channel-daily-tick --dry-run
sfrfr max-channel-daily-tick
sfrfr max-channel-daily-tick --mark-sent 08-ils
```

## Systemd на VPS

```bash
sudo cp /opt/sfrfr/docs/systemd/sfrfr-max-channel-daily.service /etc/systemd/system/
sudo cp /opt/sfrfr/docs/systemd/sfrfr-max-channel-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sfrfr-max-channel-daily.timer
systemctl list-timers | grep max-channel
sudo systemctl start sfrfr-max-channel-daily.service   # разовый тест
journalctl -u sfrfr-max-channel-daily.service -n 50 --no-pager
```

Расписание: **ежедневно 10:00 Europe/Moscow**.

## Env (уже нужны для review)

| Переменная | Роль |
|---|---|
| `MAX_OPS_BOT_TOKEN` | Ops-бот |
| `STAFF_LOGIN_APPROVER_MAX_USER_IDS` | Кому слать черновик |
| `MAX_BOT_TOKEN` | Клиентский бот (кнопка «Опубликовать») |
| `MAX_CHANNEL_CHAT_ID` | Клиентский канал |
| `MAX_CHAT_URL` | CTA chat |

State на VPS должен жить в `/opt/sfrfr/storage/` (права `sfrfr`). После деплоя один раз:

```bash
sudo -u sfrfr mkdir -p /opt/sfrfr/storage
# если 08-ils уже отправлен вручную:
sudo -u sfrfr bash -lc 'cd /opt/sfrfr && .venv/bin/python -m sfrfr max-channel-daily-tick --mark-sent 08-ils'
```

## Playbook

Ритм и календарь: [`playbook-max-channel-month-2026-08.md`](../marketing-sales/playbook-max-channel-month-2026-08.md).
