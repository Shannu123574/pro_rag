from datetime import datetime, timezone

from sqlalchemy import (
    create_engine,
    text,
    Column,
    Integer,
    String,
    Text,
    JSON,
    DateTime,
)
from sqlalchemy.orm import (
    sessionmaker,
    DeclarativeBase,
)
from pgvector.sqlalchemy import Vector

from app.config import settings


# ---------------------------------------------------------
# DATABASE ENGINE
# ---------------------------------------------------------

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# ---------------------------------------------------------
# DATABASE SESSION
# ---------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------
# BASE MODEL
# ---------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------
# DOCUMENT CHUNK MODEL
# ---------------------------------------------------------

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(
        Integer,
        primary_key=True,
    )

    document_id = Column(
        String(128),
        index=True,
        nullable=False,
    )

    source = Column(
        String(512),
        nullable=False,
    )

    page = Column(
        Integer,
        nullable=True,
    )

    chunk_index = Column(
        Integer,
        nullable=False,
    )

    content = Column(
        Text,
        nullable=False,
    )

    metadata_json = Column(
        JSON,
        default=dict,
    )

    embedding = Column(
        Vector(384),
        nullable=False,
    )


# ---------------------------------------------------------
# QUERY AUDIT LOG MODEL
# ---------------------------------------------------------

class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(
        Integer,
        primary_key=True,
    )

    question = Column(
        Text,
        nullable=False,
    )

    answer = Column(
        Text,
        nullable=False,
    )

    confidence = Column(
        String(32),
        nullable=False,
    )

    grounded = Column(
        Integer,
        nullable=False,
        default=0,
    )

    abstained = Column(
        Integer,
        nullable=False,
        default=0,
    )

    retrieved_chunks = Column(
        Integer,
        nullable=False,
        default=0,
    )

    cited_sources = Column(
        Integer,
        nullable=False,
        default=0,
    )

    retrieval_ms = Column(
        Integer,
        nullable=False,
        default=0,
    )

    generation_ms = Column(
        Integer,
        nullable=False,
        default=0,
    )

    total_ms = Column(
        Integer,
        nullable=False,
        default=0,
    )

    citations_json = Column(
        JSON,
        default=list,
    )

    evidence_json = Column(
        JSON,
        default=list,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------

def init_db():
    import time
    from sqlalchemy.exc import OperationalError

    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            # Ensure pgvector is available.
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE EXTENSION IF NOT EXISTS vector"
                    )
                )
            break
        except OperationalError as exc:
            if attempt == max_retries:
                raise
            print(f"[DB] Waiting for database to be ready (attempt {attempt}/{max_retries})...")
            time.sleep(2)

    # Create any missing tables.
    Base.metadata.create_all(engine)

    # Add evidence_json to an existing query_logs table
    # without deleting existing query history.
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE query_logs
                ADD COLUMN IF NOT EXISTS evidence_json JSON
                """
            )
        )
        # Ensure HNSW index exists
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
                ON chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        )