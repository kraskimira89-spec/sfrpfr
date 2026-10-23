# 2026-10-23: cutover SSL-патч — skip только по правилу своего target

В `ensure_ssl_redirect` условие `https://{target}` + любой `RewriteRule` пропускало второй патч, если в файле уже был чужой RewriteRule и упоминание URL.

Теперь: skip только если есть `RewriteRule ^ https://{target}` (как в bash-grep выше).
