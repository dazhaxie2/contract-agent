"""
上下文窗口构建器
层级回溯 + 优先级排序 + Token管控 + 引用标注
"""

from app.core.config import settings
from app.rag.retriever import RetrievalResult


class ContextBuilder:
    """上下文窗口构建"""

    PRIORITY_MAP = {
        "law": 4,        # 法律条文最高
        "regulation": 3, # 合规规范
        "contract": 2,   # 合同条款
        "case": 1,       # 案例
        "guide": 0,      # 指引
    }

    def build(self, results: list[RetrievalResult], max_tokens: int | None = None) -> dict:
        """
        构建大模型上下文:
        1. 优先级排序 2. Token截断 3. 引用标注 4. 格式化
        """
        max_tokens = max_tokens or settings.rag.context_tokens

        # 按法律效力优先级排序
        sorted_results = sorted(
            results,
            key=lambda r: (
                self.PRIORITY_MAP.get(r.metadata.get("doc_type", "guide"), 0),
                r.rerank_score or r.score,
            ),
            reverse=True,
        )

        context_parts = []
        references = []
        total_tokens = 0

        for i, result in enumerate(sorted_results):
            ref_id = i + 1
            content = result.content
            token_count = len(content)  # 简化

            if total_tokens + token_count > max_tokens:
                # 截断低优先级内容
                remaining = max_tokens - total_tokens
                if remaining > 100:
                    content = content[:remaining]
                    token_count = remaining
                else:
                    break

            # 构建引用标记
            source_info = result.metadata.get("source", "未知来源")
            hierarchy = result.metadata.get("hierarchy_path", "")
            ref_label = f"[参考{ref_id}]"

            context_parts.append(f"{ref_label} {content}")
            references.append({
                "ref_id": ref_id,
                "chunk_id": result.chunk_id,
                "source": source_info,
                "hierarchy": hierarchy,
                "doc_type": result.metadata.get("doc_type", ""),
                "score": result.rerank_score or result.score,
            })

            total_tokens += token_count

        context_text = "\n\n---\n\n".join(context_parts)

        return {
            "context": context_text,
            "references": references,
            "total_tokens": total_tokens,
            "chunk_count": len(context_parts),
        }


context_builder = ContextBuilder()
