from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator

from sqlalchemy import JSON, Column, ForeignKey, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/knowledge.db")

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    workspace_id = Column(String, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String, default="manual")
    source_type = Column(String, default="manual")  # manual | file | url | transcript | email | slack
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
    review_status = Column(String, default="pending")  # pending | accepted | rejected
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
    score = Column(String, nullable=False)  # stored as string to avoid Float dialect issues


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
