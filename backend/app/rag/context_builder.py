"""Context builder with token budgeting and references."""

from __future__ import annotations

from app.core.config import settings
from app.rag.retriever import RetrievalResult


class ContextBuilder:
    PRIORITY_MAP = {
        "law": 4,
        "regulation": 3,
        "enterprise_rule": 3,
        "contract": 2,
        "case": 1,
        "guide": 0,
    }

    def build(self, results: list[RetrievalResult], max_tokens: int | None = None) -> dict:
        max_tokens = max_tokens or settings.rag.context_tokens
        sorted_results = sorted(
            results,
            key=lambda item: (
                self.PRIORITY_MAP.get(item.metadata.get("doc_type", "guide"), 0),
                float(item.rerank_score if item.rerank_score is not None else item.score),
            ),
            reverse=True,
        )

        parts: list[str] = []
        references: list[dict] = []
        total_tokens = 0

        for i, result in enumerate(sorted_results, start=1):
            content = (result.content or "").strip()
            parent_excerpt = str(result.metadata.get("parent_excerpt") or "").strip()
            if parent_excerpt:
                content = f"[PARENT] {parent_excerpt}\n[CHUNK] {content}"
            token_count = len(content) // 4 + 1
            if total_tokens + token_count > max_tokens:
                remaining_chars = max(0, (max_tokens - total_tokens) * 4)
                if remaining_chars < 100:
                    break
                content = content[:remaining_chars] + "..."
                token_count = remaining_chars // 4

            ref_label = f"[REF-{i}]"
            parts.append(f"{ref_label} {content}")
            references.append(
                {
                    "ref_id": i,
                    "chunk_id": result.chunk_id,
                    "doc_id": result.metadata.get("doc_id"),
                    "source": result.metadata.get("source", "unknown"),
                    "doc_title": result.metadata.get("doc_title", ""),
                    "hierarchy": result.metadata.get("hierarchy_path", ""),
                    "doc_type": result.metadata.get("doc_type", ""),
                    "score": float(result.rerank_score if result.rerank_score is not None else result.score),
                }
            )
            total_tokens += token_count

        return {
            "context": "\n\n---\n\n".join(parts),
            "references": references,
            "total_tokens": total_tokens,
            "chunk_count": len(parts),
        }


context_builder = ContextBuilder()
