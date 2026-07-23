"""RAG: нормы + только verified/template кейсы (без ПДн)."""

from __future__ import annotations

from pathlib import Path

from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry
from sfrfr.ai.schemas.agents import KnowledgeHit

_DEFAULT_KNOWLEDGE = Path(__file__).resolve().parents[4] / "knowledge"


class KnowledgeRetriever:
    """Keyword-поиск по knowledge/*.md и registry кейсов; позже — embeddings."""

    def __init__(
        self,
        knowledge_dir: Path | None = None,
        registry: KnowledgeCaseRegistry | None = None,
    ) -> None:
        self.knowledge_dir = knowledge_dir or _DEFAULT_KNOWLEDGE
        self.registry = registry or KnowledgeCaseRegistry(
            cases_dir=self.knowledge_dir / "cases"
        )

    def search(self, query: str, *, limit: int = 3) -> list[KnowledgeHit]:
        q = (query or "").lower().strip()
        words = [w for w in q.split() if len(w) > 2]
        scored: list[KnowledgeHit] = []

        if self.knowledge_dir.exists():
            for path in sorted(self.knowledge_dir.glob("*.md")):
                hit = self._score_text(
                    source=str(path.relative_to(self.knowledge_dir)),
                    text=path.read_text(encoding="utf-8", errors="ignore"),
                    words=words,
                    q=q,
                )
                if hit:
                    scored.append(hit)

        for case in self.registry.list_cases(rag_ready_only=True):
            hit = self._score_text(
                source=f"cases/{case.case_id}",
                text=case.rag_text(),
                words=words,
                q=q,
            )
            if hit:
                scored.append(hit)

        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:limit]

    @staticmethod
    def _score_text(
        *,
        source: str,
        text: str,
        words: list[str],
        q: str,
    ) -> KnowledgeHit | None:
        body = text.strip()
        if not body:
            return None
        low = body.lower()
        if q and q in low:
            score = 1.0
        elif words:
            hits = sum(1 for w in words if w in low)
            if hits == 0:
                return None
            score = hits / len(words)
        else:
            score = 0.1
        snippet = body.replace("\n", " ")[:400]
        return KnowledgeHit(source=source, snippet=snippet, score=score)
