# 2026-08-17 — SSH-доступ к VPS для агента и владельца

- Проверен вход: личный ключ ПК и ключ `sfrfr-deploy` на `root@91.229.11.147`.
- В `~/.ssh/config` добавлен алиас `sfrfr-vps` / `proverkastaza` (не в git).
- Документ: `docs/ops/vps-ssh.md`.
- На VPS убраны дубли одной RSA-строки в `authorized_keys` (бэкап рядом).
