from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/knowledge.db")

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Auth — always in SQLite regardless of STORAGE_BACKEND
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    workspace_id = Column(String, nullable=False)


# ---------------------------------------------------------------------------
# Observability — query logs always in SQLite for durability
# ---------------------------------------------------------------------------

class QueryLog(Base):
    """Persists every GraphRAG query for observability and future fine-tuning."""
    __tablename__ = "query_logs"
    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=False)
    sub_queries = Column(JSON, default=list)
    hyde_doc = Column(Text, nullable=True)
    route = Column(String, nullable=True)
    retrieval_mode = Column(String, nullable=True)
    context_node_ids = Column(JSON, default=list)
    citations = Column(JSON, default=list)
    answer_snippet = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(String, nullable=False)


# ---------------------------------------------------------------------------
# SQLite fallback tables — used only when STORAGE_BACKEND=sqlite
# ---------------------------------------------------------------------------

class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String, default="manual")
    source_type = Column(String, default="manual")
    author = Column(String, default="unknown")
    tags = Column(JSON, default=list)
    created_at = Column(String, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)
    author = Column(String, default="unknown")
    date = Column(String, nullable=False)
    tags = Column(JSON, default=list)
    details = Column(JSON, default=dict)
    embedding = Column(JSON, nullable=True)  # cosine fallback when Neo4j is down
    review_status = Column(String, default="pending")
    review_note = Column(Text, default="")


class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, nullable=False, index=True)
    from_id = Column(String, nullable=False)
    to_id = Column(String, nullable=False)
    type = Column(String, nullable=False)


class Playbook(Base):
    __tablename__ = "playbooks"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    steps = Column(JSON, default=list)
    category = Column(String, default="general")


class CrossLink(Base):
    __tablename__ = "cross_links"
    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, nullable=False, index=True)
    item_id_a = Column(String, ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False)
    item_id_b = Column(String, ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False)
    score = Column(String, nullable=False)


class ArtifactSummary(Base):
    """LLM summary of an artifact used as summary index in GraphRAG."""
    __tablename__ = "artifact_summaries"
    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, nullable=False, index=True)
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    created_at = Column(String, nullable=False)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


# Columns added after initial schema — safe to run on every startup
_MIGRATIONS = [
    "ALTER TABLE knowledge_items ADD COLUMN embedding JSON",
    "ALTER TABLE artifact_summaries ADD COLUMN embedding JSON",
    "ALTER TABLE artifacts ADD COLUMN source_type TEXT DEFAULT 'manual'",
    "ALTER TABLE query_logs ADD COLUMN sub_queries JSON",
    "ALTER TABLE query_logs ADD COLUMN hyde_doc TEXT",
    "ALTER TABLE query_logs ADD COLUMN route TEXT",
    "ALTER TABLE query_logs ADD COLUMN retrieval_mode TEXT",
    "ALTER TABLE query_logs ADD COLUMN context_node_ids JSON",
    "ALTER TABLE query_logs ADD COLUMN latency_ms INTEGER",
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply additive column migrations — ignore errors for columns that already exist
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(__import__('sqlalchemy').text(stmt))
            except Exception:
                pass
