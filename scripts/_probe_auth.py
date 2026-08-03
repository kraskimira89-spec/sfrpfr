from pathlib import Path
import re
import time
import psycopg

env = {}
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://").replace(
    ":5432/", ":6543/"
)
dsn = re.sub(r"sslmode=[^&]*", "sslmode=require", dsn)
c = psycopg.connect(dsn, connect_timeout=20)
cur = c.cursor()
queries = [
    "select id, email from auth.users",
    "select id, email, encrypted_password from auth.users limit 1",
    "select id, email, raw_app_meta_data from auth.users limit 1",
    "select id from auth.users",
    "select * from auth.users limit 1",
]
for q in queries:
    t = time.time()
    print("Q", q, flush=True)
    cur.execute(q)
    n = len(cur.fetchall())
    print(" ->", n, round(time.time() - t, 2), flush=True)
c.close()
print("done", flush=True)
