# 2026-08-22 — MAX ежедневный ритм + 08-ils в ops

## Сделано

- Отправлен черновик `08-ils` в личку ops (кнопка «Опубликовать»).
- Ритм playbook: **ежедневно** (было через день).
- CLI `sfrfr max-channel-daily-tick` + очередь `daily-queue.json`.
- Systemd: `sfrfr-max-channel-daily.timer` — 10:00 МСК, полуавто (ops review, не `--direct`).
- Ops: `docs/ops/max-channel-daily-cron.md`.

## Дальше владельцу

1. В MAX ops: **Опубликовать** для `08-ils`.
2. С 23.08 timer шлёт `09-sverka` и далее по одному в день.
