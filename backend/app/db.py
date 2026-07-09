from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text
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
    llm_provider = Column(String, nullable=True)
    embedding_provider = Column(String, nullable=True)
    context_node_ids = Column(JSON, default=list)
    citations = Column(JSON, default=list)
    answer_snippet = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(String, nullable=False)


# ---------------------------------------------------------------------------
# Workspace + provider policy
# ---------------------------------------------------------------------------

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False, unique=True)
    allow_cloud_providers = Column(Boolean, default=False)
    default_llm_provider = Column(String, default="ollama")
    default_embedding_provider = Column(String, default="local")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class ProviderConfig(Base):
    __tablename__ = "provider_configs"
    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    provider_type = Column(String, nullable=False)
    provider_name = Column(String, nullable=False)
    model_name = Column(String, nullable=True)
    config_json = Column(JSON, default=dict)
    api_key_ref = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


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
    extraction_engine = Column(String, default="regex")
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
    extraction_engine = Column(String, default="regex")
    embedding = Column(JSON, nullable=True)  # cosine fallback when Neo4j is down
    embedding_provider = Column(String, nullable=True)  # Phase 2: provenance
    embedding_dims = Column(Integer, nullable=True)
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
    embedding_provider = Column(String, nullable=True)  # Phase 2: provenance
    embedding_dims = Column(Integer, nullable=True)
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
    "ALTER TABLE query_logs ADD COLUMN llm_provider TEXT",
    "ALTER TABLE query_logs ADD COLUMN embedding_provider TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN embedding_provider TEXT",
    "ALTER TABLE knowledge_items ADD COLUMN embedding_dims INTEGER",
    "ALTER TABLE knowledge_items ADD COLUMN extraction_engine TEXT",
    "ALTER TABLE artifact_summaries ADD COLUMN embedding_provider TEXT",
    "ALTER TABLE artifact_summaries ADD COLUMN embedding_dims INTEGER",
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

        # Backfill workspace records for existing users.
        try:
            await conn.execute(
                __import__('sqlalchemy').text(
                    "INSERT OR IGNORE INTO workspaces (id, name, allow_cloud_providers, default_llm_provider, default_embedding_provider, created_at) "
                    "SELECT DISTINCT workspace_id, workspace_id, 0, 'ollama', 'local', datetime('now') FROM users"
                )
            )
        except Exception:
            pass
