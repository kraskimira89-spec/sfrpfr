from __future__ import annotations

from collections.abc import Iterator

import pytest

from sfrfr.core.config import get_settings


@pytest.fixture(autouse=True)
def _max_questionnaire_off_by_default(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Сценарии MAX написаны под прежнее приветствие; анкету B1 включают явно.
    monkeypatch.setenv("MAX_QUESTIONNAIRE_ENABLED", "0")
    yield
    get_settings.cache_clear()
