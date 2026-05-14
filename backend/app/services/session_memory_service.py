"""Session, conversation history, and memory management."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Iterable

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import ConversationMessage, ConversationSession
from app.models.memory import MemoryFact, MemorySummary


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rough_token_count(text: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _summary_text_from_messages(messages: Iterable[ConversationMessage], max_len: int = 1600) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.role.upper()
        content = (msg.content or "").strip().replace("\n", " ")
        if len(content) > 240:
            content = content[:240] + "..."
        lines.append(f"{role}: {content}")
    summary = "\n".join(lines)
    return summary[:max_len]


def _extract_candidate_facts(text: str) -> list[tuple[str, str, list[str]]]:
    candidates: list[tuple[str, str, list[str]]] = []
    if not text:
        return candidates

    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()[:128]
        value = value.strip()[:512]
        if key and value:
            candidates.append((key.lower(), value, ["colon_pair"]))

    for match in re.finditer(r"([A-Za-z0-9_\-\u4e00-\u9fa5]{2,32})\s+is\s+([^.,;\n]{2,128})", text, flags=re.IGNORECASE):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        candidates.append((key, value, ["is_statement"]))

    for match in re.finditer(r"([\u4e00-\u9fa5A-Za-z0-9_\-]{2,32})是([\u4e00-\u9fa5A-Za-z0-9_\-、，, ]{2,128})", text):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        candidates.append((key, value, ["cn_is_statement"]))

    dedup: dict[tuple[str, str], tuple[str, str, list[str]]] = {}
    for item in candidates:
        dedup[(item[0], item[1])] = item
    return list(dedup.values())[:20]


async def _llm_extract_facts(text: str) -> list[tuple[str, str, list[str]]]:
    if not text or len(text) < 20:
        return []
    try:
        from app.services.llm_service import llm_service

        messages = [
            {
                "role": "system",
                "content": (
                    "Extract structured facts from this text. Output one fact per line as: key | value\n"
                    "Keys should be lowercase English or Chinese nouns. Values should be concise.\n"
                    "Only extract clear, factual statements. Output max 10 facts. No explanations."
                ),
            },
            {"role": "user", "content": text[:2000]},
        ]
        result = await llm_service.light_generate(messages)
        content = result.get("content", "")
        facts = []
        for line in content.strip().splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            parts = line.split("|", 1)
            key = parts[0].strip()[:128].lower()
            value = parts[1].strip()[:512]
            if key and value and len(key) >= 2:
                facts.append((key, value, ["llm_extracted"]))
        return facts[:15]
    except Exception:
        return []


class SessionMemoryService:
    async def get_or_create_user_profile(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        tenant_id: str,
    ):
        from app.models.memory import UserProfile

        row = await db.scalar(
            select(UserProfile).where(
                UserProfile.tenant_id == tenant_id,
                UserProfile.user_id == user_id,
            )
        )
        if row:
            return row
        now = _utcnow()
        row = UserProfile(
            id=uuid.uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            industry="",
            company_type="",
            common_contract_types=[],
            focus_areas=[],
            compliance_rules=[],
            preferences={},
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return row

    async def update_user_profile(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        tenant_id: str,
        updates: dict,
    ):
        profile = await self.get_or_create_user_profile(db, user_id, tenant_id)
        for field_name in ("industry", "company_type"):
            if field_name in updates and updates[field_name]:
                setattr(profile, field_name, updates[field_name])
        for field_name in ("common_contract_types", "focus_areas", "compliance_rules"):
            if field_name in updates and isinstance(updates[field_name], list):
                setattr(profile, field_name, updates[field_name])
        if "preferences" in updates and isinstance(updates["preferences"], dict):
            merged = {**(profile.preferences or {}), **updates["preferences"]}
            profile.preferences = merged
        profile.updated_at = _utcnow()
        await db.flush()
        return profile

    async def extract_profile_from_text(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        tenant_id: str,
        text: str,
    ) -> None:
        if not text or len(text) < 30:
            return
        try:
            from app.services.llm_service import llm_service

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Extract user profile information from this text. Output JSON only:\n"
                        '{"industry": "", "company_type": "", "contract_types": [], "focus_areas": []}\n'
                        "Only fill in fields that are clearly mentioned. Leave empty strings / empty arrays for unknowns."
                    ),
                },
                {"role": "user", "content": text[:1500]},
            ]
            result = await llm_service.light_generate(messages)
            import json

            content = result.get("content", "{}")
            import re as _re

            match = _re.search(r"\{[^}]+\}", content)
            if not match:
                return
            parsed = json.loads(match.group())
            updates = {}
            if parsed.get("industry"):
                updates["industry"] = parsed["industry"]
            if parsed.get("company_type"):
                updates["company_type"] = parsed["company_type"]
            if parsed.get("contract_types"):
                updates["common_contract_types"] = parsed["contract_types"]
            if parsed.get("focus_areas"):
                updates["focus_areas"] = parsed["focus_areas"]
            if updates:
                await self.update_user_profile(db, user_id, tenant_id, updates)
        except Exception as exc:
            logger.debug(f"profile extraction failed user={user_id} tenant={tenant_id}: {exc}")

    async def get_profile_context(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        tenant_id: str,
    ) -> dict:
        try:
            profile = await self.get_or_create_user_profile(db, user_id, tenant_id)
            parts = []
            if profile.industry:
                parts.append(f"行业: {profile.industry}")
            if profile.company_type:
                parts.append(f"企业类型: {profile.company_type}")
            if profile.common_contract_types:
                parts.append(f"常用合同类型: {', '.join(profile.common_contract_types)}")
            if profile.focus_areas:
                parts.append(f"关注领域: {', '.join(profile.focus_areas)}")
            if profile.compliance_rules:
                parts.append(f"合规规则: {', '.join(str(r) for r in profile.compliance_rules[:5])}")
            return {
                "profile_text": "\n".join(parts) if parts else "",
                "industry": profile.industry,
                "company_type": profile.company_type,
                "focus_areas": profile.focus_areas,
            }
        except Exception:
            return {"profile_text": "", "industry": "", "company_type": "", "focus_areas": []}

    async def ensure_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> ConversationSession:
        row = await db.scalar(
            select(ConversationSession).where(
                ConversationSession.id == session_id,
                ConversationSession.tenant_id == tenant_id,
            )
        )
        if row:
            return row

        now = _utcnow()
        row = ConversationSession(
            id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            title=(title or "New Session")[:256],
            status="active",
            metadata_extra={},
            last_message_at=None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return row

    async def get_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
    ) -> ConversationSession | None:
        return await db.scalar(
            select(ConversationSession).where(
                ConversationSession.id == session_id,
                ConversationSession.tenant_id == tenant_id,
            )
        )

    async def list_sessions(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConversationSession], int]:
        query = select(ConversationSession).where(ConversationSession.tenant_id == tenant_id)
        if user_id:
            query = query.where(ConversationSession.user_id == user_id)

        total_stmt = select(func.count()).select_from(query.subquery())
        total = int((await db.scalar(total_stmt)) or 0)

        rows = (
            await db.scalars(
                query.order_by(ConversationSession.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return list(rows), total

    async def append_message(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
        role: str,
        content: str,
        user_id: uuid.UUID | None = None,
        trace_id: str | None = None,
        metadata: dict | None = None,
    ) -> ConversationMessage:
        now = _utcnow()
        max_idx = await db.scalar(
            select(func.max(ConversationMessage.message_index)).where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.tenant_id == tenant_id,
            )
        )
        next_index = int(max_idx or 0) + 1
        row = ConversationMessage(
            id=uuid.uuid4(),
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            content=content,
            token_count=_rough_token_count(content),
            message_index=next_index,
            trace_id=trace_id,
            metadata_extra=metadata or {},
            created_at=now,
        )
        db.add(row)

        session = await self.ensure_session(
            db=db,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        session.last_message_at = now
        session.updated_at = now
        await db.flush()
        return row

    async def list_messages(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ConversationMessage], int]:
        query = select(ConversationMessage).where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.tenant_id == tenant_id,
        )
        total_stmt = select(func.count()).select_from(query.subquery())
        total = int((await db.scalar(total_stmt)) or 0)
        rows = (
            await db.scalars(
                query.order_by(ConversationMessage.message_index.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return list(rows), total

    async def get_runtime_context(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
        short_window: int = 12,
    ) -> dict:
        latest = (
            await db.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.tenant_id == tenant_id,
                )
                .order_by(ConversationMessage.message_index.desc())
                .limit(short_window)
            )
        ).all()
        latest = list(reversed(list(latest)))

        summary = await db.scalar(
            select(MemorySummary)
            .where(MemorySummary.session_id == session_id, MemorySummary.tenant_id == tenant_id)
            .order_by(MemorySummary.updated_at.desc())
            .limit(1)
        )
        facts = (
            await db.scalars(
                select(MemoryFact)
                .where(MemoryFact.session_id == session_id, MemoryFact.tenant_id == tenant_id)
                .order_by(MemoryFact.updated_at.desc())
                .limit(20)
            )
        ).all()

        return {
            "history_messages": latest,
            "history_text": _summary_text_from_messages(latest, max_len=2000),
            "summary": summary.content if summary else "",
            "facts": [
                {
                    "key": fact.fact_key,
                    "value": fact.fact_value,
                    "confidence": float(fact.confidence or 0.0),
                    "tags": fact.tags or [],
                }
                for fact in facts
            ],
        }

    async def upsert_facts_from_message(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
        source_message_id: uuid.UUID,
        text: str,
    ) -> int:
        candidates = _extract_candidate_facts(text)
        llm_facts = await _llm_extract_facts(text)
        for fact in llm_facts:
            key_val = (fact[0], fact[1])
            if key_val not in {(c[0], c[1]) for c in candidates}:
                candidates.append(fact)
        if not candidates:
            return 0

        updated = 0
        for key, value, tags in candidates:
            row = await db.scalar(
                select(MemoryFact).where(
                    MemoryFact.session_id == session_id,
                    MemoryFact.tenant_id == tenant_id,
                    MemoryFact.fact_key == key,
                )
            )
            now = _utcnow()
            if row:
                row.fact_value = value
                row.tags = sorted(set((row.tags or []) + tags))
                row.confidence = max(float(row.confidence or 0.0), 0.65)
                row.source_message_id = source_message_id
                row.updated_at = now
            else:
                row = MemoryFact(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    tenant_id=tenant_id,
                    fact_key=key,
                    fact_value=value,
                    confidence=0.65,
                    source_message_id=source_message_id,
                    tags=tags,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            updated += 1
        await db.flush()
        return updated

    async def refresh_rolling_summary(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
        trigger_messages: int = 16,
        summary_window: int = 24,
    ) -> MemorySummary | None:
        total = int(
            (await db.scalar(
                select(func.count()).where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.tenant_id == tenant_id,
                )
            ))
            or 0
        )
        if total < trigger_messages:
            return None

        rows = (
            await db.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.tenant_id == tenant_id,
                )
                .order_by(ConversationMessage.message_index.desc())
                .limit(summary_window)
            )
        ).all()
        rows = list(reversed(list(rows)))
        if not rows:
            return None

        summary_text = _summary_text_from_messages(rows, max_len=2400)
        now = _utcnow()

        latest = await db.scalar(
            select(MemorySummary)
            .where(
                MemorySummary.session_id == session_id,
                MemorySummary.tenant_id == tenant_id,
                MemorySummary.summary_type == "rolling",
            )
            .order_by(MemorySummary.updated_at.desc())
            .limit(1)
        )
        start_idx = rows[0].message_index
        end_idx = rows[-1].message_index

        if latest:
            latest.content = summary_text
            latest.token_count = _rough_token_count(summary_text)
            latest.window_start_index = start_idx
            latest.window_end_index = end_idx
            latest.updated_at = now
            latest.metadata_extra = {"message_count": len(rows)}
            await db.flush()
            return latest

        row = MemorySummary(
            id=uuid.uuid4(),
            session_id=session_id,
            tenant_id=tenant_id,
            summary_type="rolling",
            content=summary_text,
            token_count=_rough_token_count(summary_text),
            window_start_index=start_idx,
            window_end_index=end_idx,
            metadata_extra={"message_count": len(rows)},
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return row

    async def rebuild_session_memory(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: str,
    ) -> dict:
        await db.execute(
            MemoryFact.__table__.delete().where(
                MemoryFact.session_id == session_id,
                MemoryFact.tenant_id == tenant_id,
            )
        )
        await db.execute(
            MemorySummary.__table__.delete().where(
                MemorySummary.session_id == session_id,
                MemorySummary.tenant_id == tenant_id,
            )
        )

        messages = (
            await db.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.tenant_id == tenant_id,
                )
                .order_by(ConversationMessage.message_index.asc())
            )
        ).all()

        fact_count = 0
        for msg in messages:
            if msg.role in {"user", "system"}:
                fact_count += await self.upsert_facts_from_message(
                    db=db,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    source_message_id=msg.id,
                    text=msg.content,
                )
        summary = await self.refresh_rolling_summary(db, session_id, tenant_id, trigger_messages=1)
        return {
            "messages": len(messages),
            "facts": fact_count,
            "summary_updated": bool(summary),
        }


session_memory_service = SessionMemoryService()
