from __future__ import annotations

import json
from pathlib import Path

from sfrfr.integrations.max.channel_daily import next_post_id


def test_next_post_id_skips_sent() -> None:
    assert next_post_id(["a", "b", "c"], ["a"]) == "b"
    assert next_post_id(["a", "b"], ["a", "b"]) is None
    assert next_post_id(["a"], []) == "a"


def test_daily_queue_file_exists() -> None:
    path = Path("scripts/assets/max-channel/daily-queue.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "08-ils" in data["queue"]
    assert data["mode"] == "ops_review"
