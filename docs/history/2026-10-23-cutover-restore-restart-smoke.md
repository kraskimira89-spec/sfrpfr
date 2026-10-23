# 2026-10-23: cutover — вернуть SSL-патч, restart, miniapp, smoke

После #208 в `vps_cutover_proverkastaza.sh` пропали:

1. python-патч SSL Rewrite (sed с `\\n` писал литерал `\n`);
2. `systemctl restart` / `vps_deploy --post-update` после правок `.env`;
3. вызов `deploy_max_miniapp.sh`;
4. curl smoke по новым URL.

Восстановлено с параметром `OLD_ROOT` (без жёсткого старого apex в репо).
