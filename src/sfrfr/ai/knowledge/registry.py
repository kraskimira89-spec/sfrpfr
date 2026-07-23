"""Реестр обезличенных кейсов в knowledge/cases/*.json."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from sfrfr.ai.schemas.knowledge_case import KnowledgeCase, KnowledgeQuality

_DEFAULT_CASES_DIR = Path(__file__).resolve().parents[4] / "knowledge" / "cases"
_CASE_ID_RE = re.compile(r"^CASE-(\d{4})-(\d{3})$")


class KnowledgeCaseRegistry:
    """Файловый реестр кейсов (MVP без БД)."""

    def __init__(self, cases_dir: Path | None = None) -> None:
        self.cases_dir = cases_dir or _DEFAULT_CASES_DIR
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, case_id: str) -> Path:
        return self.cases_dir / f"{case_id}.json"

    def list_cases(
        self,
        *,
        quality: KnowledgeQuality | None = None,
        rag_ready_only: bool = False,
    ) -> list[KnowledgeCase]:
        items: list[KnowledgeCase] = []
        for path in sorted(self.cases_dir.glob("CASE-*.json")):
            case = KnowledgeCase.model_validate_json(path.read_text(encoding="utf-8"))
            if quality is not None and case.quality != quality:
                continue
            if rag_ready_only and not case.is_rag_ready():
                continue
            items.append(case)
        return items

    def get(self, case_id: str) -> KnowledgeCase:
        path = self._path_for(case_id)
        if not path.exists():
            raise KeyError(case_id)
        return KnowledgeCase.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, case: KnowledgeCase) -> Path:
        path = self._path_for(case.case_id)
        path.write_text(
            case.model_dump_json(indent=2, exclude_none=False) + "\n",
            encoding="utf-8",
        )
        return path

    def next_case_id(self, *, year: int | None = None) -> str:
        y = year or date.today().year
        max_n = 0
        for path in self.cases_dir.glob(f"CASE-{y}-*.json"):
            m = _CASE_ID_RE.match(path.stem)
            if m and int(m.group(1)) == y:
                max_n = max(max_n, int(m.group(2)))
        return f"CASE-{y}-{max_n + 1:03d}"

    def find_by_ops_case_id(self, ops_case_id: str) -> KnowledgeCase | None:
        for case in self.list_cases():
            if case.ops_case_id == ops_case_id:
                return case
        return None

    def set_quality(
        self,
        case_id: str,
        quality: KnowledgeQuality,
        *,
        verified_at: date | None = None,
    ) -> KnowledgeCase:
        case = self.get(case_id)
        case.quality = quality
        if quality in (KnowledgeQuality.VERIFIED, KnowledgeQuality.TEMPLATE):
            case.verified_at = verified_at or date.today()
            if quality == KnowledgeQuality.TEMPLATE:
                case.can_be_template = True
        self.save(case)
        return case


def load_case_json(path: Path) -> KnowledgeCase:
    data = json.loads(path.read_text(encoding="utf-8"))
    return KnowledgeCase.model_validate(data)
