"""Evaluation service: LLM-as-judge scoring and test set management."""

from __future__ import annotations

import json
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentExecution
from app.services.llm_service import llm_service


class EvaluationService:
    async def score_execution(
        self,
        db: AsyncSession,
        execution_id: uuid.UUID,
        tenant_id: str,
    ) -> dict[str, Any]:
        execution = await db.scalar(
            select(AgentExecution).where(
                AgentExecution.id == execution_id,
                AgentExecution.tenant_id == tenant_id,
            )
        )
        if not execution:
            return {"error": "execution not found"}

        query = execution.user_query or ""
        result_text = execution.result or ""
        metadata = execution.result_metadata or {}
        references = metadata.get("references", [])
        ref_text = json.dumps(references[:8], ensure_ascii=False)[:3000]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a legal AI output quality judge. Score on 4 dimensions (0.0-1.0):\n"
                    "1) relevance: How well does the output address the user query?\n"
                    "2) factuality: Is every claim grounded in the provided references?\n"
                    "3) completeness: Does it cover all important aspects?\n"
                    "4) clarity: Is the output well-structured and easy to understand?\n"
                    "Output ONLY valid JSON: {\"relevance\": <f>, \"factuality\": <f>, \"completeness\": <f>, \"clarity\": <f>}"
                ),
            },
            {
                "role": "user",
                "content": f"Query: {query[:500]}\n\nOutput: {result_text[:3000]}\n\nReferences: {ref_text}",
            },
        ]

        try:
            judge_result = await llm_service.light_generate(messages)
            content = judge_result.get("content", "{}")
            import re
            match = re.search(r"\{[^}]+\}", content)
            if match:
                scores = json.loads(match.group())
                relevance = scores.get("relevance")
                factuality = scores.get("factuality")

                execution.relevance_score = relevance
                execution.factuality_score = factuality
                new_meta = dict(metadata)
                new_meta["evaluation"] = scores
                execution.result_metadata = new_meta
                await db.flush()
                return {"execution_id": str(execution_id), **scores}
        except Exception as exc:
            logger.error(f"Evaluation scoring failed: {exc}")
            return {"error": str(exc)}

        return {"error": "no valid score JSON in judge output"}

    async def batch_score(
        self,
        db: AsyncSession,
        tenant_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        rows = (
            await db.scalars(
                select(AgentExecution)
                .where(
                    AgentExecution.tenant_id == tenant_id,
                    AgentExecution.status == "completed",
                    AgentExecution.relevance_score.is_(None),
                )
                .order_by(AgentExecution.created_at.desc())
                .limit(limit)
            )
        ).all()

        scored = 0
        errors = 0
        for row in rows:
            result = await self.score_execution(db, row.id, tenant_id)
            if "error" not in result:
                scored += 1
            else:
                errors += 1

        return {"scored": scored, "errors": errors, "total": len(rows)}

    async def get_metrics(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> dict[str, Any]:
        stats = await db.execute(
            select(
                func.count(AgentExecution.id).label("total"),
                func.avg(AgentExecution.relevance_score).label("avg_relevance"),
                func.avg(AgentExecution.factuality_score).label("avg_factuality"),
            ).where(
                AgentExecution.tenant_id == tenant_id,
                AgentExecution.relevance_score.isnot(None),
            )
        )
        row = stats.one()
        return {
            "total_scored": row.total or 0,
            "avg_relevance": round(float(row.avg_relevance or 0), 3),
            "avg_factuality": round(float(row.avg_factuality or 0), 3),
        }


evaluation_service = EvaluationService()
