"""Дедуп webhook MAX: повторные доставки callback не обрабатываем дважды."""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from pathlib import Path

from sfrfr.core.config import get_settings

_lock = threading.RLock()
_seen: OrderedDict[str, float] = OrderedDict()
_SEEN_TTL_SEC = 30 * 60
_SEEN_MAX = 4000


def _path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "max_webhook_callbacks.json"


def _prune(now: float) -> None:
    while _seen and (now - next(iter(_seen.values())) > _SEEN_TTL_SEC or len(_seen) > _SEEN_MAX):
        _seen.popitem(last=False)


def _load() -> None:
    path = _path()
    if not path.exists():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        rows = raw.get("rows") or {}
        now = time.time()
        loaded: OrderedDict[str, float] = OrderedDict()
        if isinstance(rows, dict):
            for key, ts in sorted(rows.items(), key=lambda kv: float(kv[1] or 0)):
                try:
                    t = float(ts)
                except (TypeError, ValueError):
                    continue
                if now - t <= _SEEN_TTL_SEC:
                    loaded[str(key)] = t
        global _seen
        _seen = loaded
        _prune(now)
    except Exception:
        pass


def _save() -> None:
    path = _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"rows": dict(_seen)}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def claim_callback_id(callback_id: str | None) -> bool:
    """True = первый раз (можно обрабатывать). False = уже видели этот callback_id."""
    cid = str(callback_id or "").strip()
    if not cid:
        return True
    with _lock:
        if not _seen:
            _load()
        now = time.time()
        _prune(now)
        if cid in _seen:
            return False
        _seen[cid] = now
        _seen.move_to_end(cid)
        _save()
        return True


def reset_callback_dedupe_for_tests() -> None:
    with _lock:
        _seen.clear()
        path = _path()
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
