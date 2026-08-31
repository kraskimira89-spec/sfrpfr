"""Временный debug-sink для сессии d43d44 (без ПДн)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

_SESSION = "d43d44"
_LOG_PATHS = (
    Path("/opt/sfrfr/debug-d43d44.log"),
    Path("debug-d43d44.log"),
)


class DebugSessionEvent(BaseModel):
    sessionId: str = Field(max_length=32)
    location: str = Field(max_length=200)
    message: str = Field(max_length=300)
    hypothesisId: str = Field(default="", max_length=16)
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: int | None = None
    runId: str = Field(default="pre", max_length=32)


def _write_ndjson(payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    for path in _LOG_PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            return
        except OSError:
            continue


@router.post("/debug-session")
def post_debug_session(event: DebugSessionEvent) -> dict[str, str]:
    if event.sessionId != _SESSION:
        raise HTTPException(status_code=403, detail="bad_session")
    # Не сохраняем потенциальные ПДн
    safe_data = {
        k: v
        for k, v in (event.data or {}).items()
        if k.lower() not in {"email", "phone", "token", "password", "code", "otp"}
    }
    _write_ndjson(
        {
            "sessionId": event.sessionId,
            "location": event.location,
            "message": event.message,
            "hypothesisId": event.hypothesisId,
            "data": safe_data,
            "timestamp": event.timestamp or int(time.time() * 1000),
            "runId": event.runId,
            "source": "client",
        }
    )
    return {"ok": "1"}
