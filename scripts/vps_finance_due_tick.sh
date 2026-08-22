#!/usr/bin/env bash
# Разовая проверка сроков оплаты на VPS (без отправки клиенту).
set -euo pipefail
cd /opt/sfrfr
.venv/bin/python -m sfrfr finance-due-tick
