"""Рантайм-буферы в storage/ не должны быть в git: деплой делает git reset --hard."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_FILES = ("storage/max_chat_pending.json", "storage/emergency_leads.jsonl")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("rel", RUNTIME_FILES)
def test_runtime_buffer_not_tracked_and_ignored(rel: str) -> None:
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        pytest.skip("not a git checkout")
    assert _git("ls-files", "--error-unmatch", rel).returncode != 0, f"{rel} tracked"
    assert _git("check-ignore", "-q", rel).returncode == 0, f"{rel} not ignored"
