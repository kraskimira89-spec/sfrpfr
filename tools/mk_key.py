"""Создать static key writer-SA и разложить без вывода секрета (удалить после задачи)."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from yc_api import call  # noqa: E402

SA = "ajefvsvo7ojojp8rp6sr"
LOCAL = Path(__file__).resolve().parent.parent / "secrets" / "yc-db01-backup-writer.env"
if LOCAL.exists():
    sys.exit("local env already exists, abort")

code, data = call(
    "POST",
    "https://iam.api.cloud.yandex.net/iam/aws-compatibility/v1/accessKeys",
    {"serviceAccountId": SA, "description": "db-01 pg_dump -> sfrfr-supabase-db01-backup"},
)
if code != 200:
    sys.exit(f"create failed: {code} {data.get('message')}")
key_id = data["accessKey"]["id"]
content = (
    "# sfrfr-db01-backup-writer static key (storage.uploader на бакет)\n"
    f"S3_ACCESS_KEY_ID={data['accessKey']['keyId']}\n"
    f"S3_SECRET_ACCESS_KEY={data['secret']}\n"
    "S3_BUCKET=sfrfr-supabase-db01-backup\n"
    "S3_ENDPOINT=https://storage.yandexcloud.net\n"
    "S3_REGION=ru-central1\n"
)
LOCAL.write_text(content, encoding="utf-8", newline="\n")
r = subprocess.run(
    [
        "ssh",
        "-o",
        "BatchMode=yes",
        "sfrfr@51.250.69.237",
        "sudo sh -c 'umask 077; cat > /etc/sfrfr-backup.env; "
        "chown root:root /etc/sfrfr-backup.env; chmod 600 /etc/sfrfr-backup.env'; "
        "sudo stat -c '%U:%G %a %s' /etc/sfrfr-backup.env",
    ],
    input=content.encode(),
    capture_output=True,
    timeout=60,
)
print("access_key_resource_id:", key_id)
print("vm:", r.returncode, r.stdout.decode().strip(), r.stderr.decode().strip()[:300])
