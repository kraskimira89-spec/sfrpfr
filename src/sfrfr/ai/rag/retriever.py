"""RAG-заглушка: поиск по knowledge/ (без ПДн клиента)."""

from __future__ import annotations

from pathlib import Path

from sfrfr.ai.schemas.agents import KnowledgeHit

_DEFAULT_KNOWLEDGE = Path(__file__).resolve().parents[4] / "knowledge"


class KnowledgeRetriever:
    """Пока keyword-поиск по .md; позже — Chroma + embeddings."""

    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self.knowledge_dir = knowledge_dir or _DEFAULT_KNOWLEDGE

    def search(self, query: str, *, limit: int = 3) -> list[KnowledgeHit]:
        if not self.knowledge_dir.exists():
            return []
        q = query.lower()
        hits: list[KnowledgeHit] = []
        for path in sorted(self.knowledge_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if q and q not in text.lower():
                # мягкий матч: любое слово запроса
                words = [w for w in q.split() if len(w) > 2]
                if words and not any(w in text.lower() for w in words):
                    continue
            snippet = text.strip().replace("\n", " ")[:400]
            if not snippet:
                continue
            hits.append(
                KnowledgeHit(
                    source=str(path.relative_to(self.knowledge_dir)),
                    snippet=snippet,
                )
            )
            if len(hits) >= limit:
                break
        return hits
