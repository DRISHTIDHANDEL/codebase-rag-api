import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import enum

from app.db.base import Base


class RepoStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_url = Column(String, nullable=False, unique=True)
    status = Column(Enum(RepoStatus), default=RepoStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship(
        "CodeChunk", back_populates="repository", cascade="all, delete-orphan"
    )


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False
    )

    # --- Metadata ---
    file_path = Column(String, nullable=False)
    symbol_name = Column(String, nullable=True)     # function/class name
    entity_type = Column(String, nullable=False)    # "function" | "class" | "import" | "text"
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)

    # --- Content ---
    content = Column(Text, nullable=False)           # raw code text

    # --- Search columns ---
    embedding = Column(Vector(1536), nullable=True)  # OpenAI embedding
    content_tsv = Column(TSVECTOR, nullable=True)     # full-text search index

    created_at = Column(DateTime, default=datetime.utcnow)

    repository = relationship("Repository", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "file_path", "start_line", "end_line",
            name="uq_chunk_location",
        ),
    )


class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False
    )
    query_hash = Column(String, nullable=False, index=True)  # hashed query text
    query_text = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repository_id", "query_hash", name="uq_cache_key"),
    )