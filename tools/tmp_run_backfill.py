from sfrfr.integrations.yandex_workspace.backfill_local_uploads import (
    backfill_local_uploads_to_disk,
)
import json

print(json.dumps(backfill_local_uploads_to_disk(), ensure_ascii=False))
