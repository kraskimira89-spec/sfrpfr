import socket
from pathlib import Path
from urllib.parse import urlparse

dsn = ""
for line in Path("/opt/sfrfr/.env").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
u = urlparse(dsn.replace("postgresql+psycopg://", "postgresql://"))
host = u.hostname
print("host", host)
for p in (5432, 5433, 6543):
    try:
        s = socket.create_connection((host, p), timeout=8)
        print("open", p, s.getpeername())
        s.close()
    except Exception as e:
        print("fail", p, type(e).__name__, e)
