from pathlib import Path
import re
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
cur.execute(
    """
    select column_name, data_type
    from information_schema.columns
    where table_schema='auth' and table_name='users'
    order by ordinal_position
    """
)
for r in cur.fetchall():
    print(r)
print("--- try limited cols ---", flush=True)
cur.execute(
    "select id, email, encrypted_password, email_confirmed_at, created_at, updated_at, "
    "raw_app_meta_data, raw_user_meta_data, is_super_admin, role "
    "from auth.users"
)
rows = cur.fetchall()
print("got", len(rows), flush=True)
c.close()
