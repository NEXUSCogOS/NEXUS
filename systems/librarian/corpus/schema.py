"""SQLite schema definitions for the Librarian corpus store.

RECOVERED from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/storage/schema.py
(commit 514c8f8, "phase 2 - librarian-rag storage layer", 2026-08-09).
Logic unchanged; see LIBRARIAN_DONOR_FORENSIC_REPORT.md and
LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md for the recovery decision (RECOVER
— TESTED, 7/7 storage tests).

MODERNIZE fix applied during recovery: the donor's original docstring
claimed "Embeddings are stored in ChromaDB collections" — no ChromaDB
integration, or any embedding code at all, exists anywhere in the donor
(confirmed by the anti-fabrication audit in
LIBRARIAN_DONOR_FORENSIC_REPORT.md). That sentence is removed here rather
than carried forward as an unsupported claim.

MODERNIZE fix applied: `QueryHistory.model_used` previously defaulted to
the hardcoded literal `'llama2-uncensored:7b'` — a specific model name
that has never actually been invoked by any code in this donor (no
query/search capability exists yet to populate this table at all). A
fixed default naming an unused model is exactly the kind of unsupported,
self-certifying detail the anti-fabrication audit looks for; the default
is now `None` (UNKNOWN), populated honestly only once a real query
capability actually calls a real model.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone
import json


def _utc_now() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Source:
    """Represents a knowledge source (paper, documentation, etc)."""
    source_id: str
    title: str
    source_type: str  # 'paper', 'documentation', 'blog', 'code', etc.
    url: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    summary: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # Flexible JSON field
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    is_active: bool = True

    def to_dict(self):
        return {
            'source_id': self.source_id,
            'title': self.title,
            'source_type': self.source_type,
            'url': self.url,
            'author': self.author,
            'published_date': self.published_date,
            'summary': self.summary,
            'tags': json.dumps(self.tags),
            'metadata': json.dumps(self.metadata),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_active': 1 if self.is_active else 0,
        }


@dataclass
class Document:
    """Represents a chunk/document within a source."""
    document_id: str
    source_id: str
    title: str
    content_hash: str  # SHA256 of content for deduplication
    chunk_index: int  # Position within source (0, 1, 2, ...)
    tokens: int  # Approximate token count
    metadata: dict = field(default_factory=dict)  # Section, subsection, etc.
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    is_active: bool = True

    def to_dict(self):
        return {
            'document_id': self.document_id,
            'source_id': self.source_id,
            'title': self.title,
            'content_hash': self.content_hash,
            'chunk_index': self.chunk_index,
            'tokens': self.tokens,
            'metadata': json.dumps(self.metadata),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_active': 1 if self.is_active else 0,
        }


@dataclass
class QueryHistory:
    """Audit log entry for every query made to the system."""
    query_id: str
    query_text: str
    query_type: str  # 'lexical' today; 'semantic'/'hybrid' remain NOT_COMMISSIONED
    source_filter: Optional[str] = None  # JSON-encoded filter criteria
    num_results: int = 5
    confidence_threshold: float = 0.0
    result_count: int = 0  # How many results were returned
    result_metadata: dict = field(default_factory=dict)  # Scores, timings, etc.
    model_used: Optional[str] = None  # None until a real query capability actually calls a real model
    response_length: int = 0  # Tokens in generated response
    user_feedback: Optional[str] = None  # 'helpful', 'not_helpful', etc.
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self):
        return {
            'query_id': self.query_id,
            'query_text': self.query_text,
            'query_type': self.query_type,
            'source_filter': self.source_filter,
            'num_results': self.num_results,
            'confidence_threshold': self.confidence_threshold,
            'result_count': self.result_count,
            'result_metadata': json.dumps(self.result_metadata),
            'model_used': self.model_used,
            'response_length': self.response_length,
            'user_feedback': self.user_feedback,
            'created_at': self.created_at,
        }


# SQL DDL for schema creation
SCHEMA_SQL = """
-- Sources: metadata about knowledge sources
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT,
    author TEXT,
    published_date TEXT,
    summary TEXT,
    tags TEXT,  -- JSON array
    metadata TEXT,  -- JSON object for flexible attributes
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    UNIQUE(url)
);

CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_created ON sources(created_at);
CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(is_active);


-- Documents: chunks/sections within sources
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,  -- Prevents duplicate content
    chunk_index INTEGER NOT NULL,
    tokens INTEGER NOT NULL,
    metadata TEXT,  -- JSON object (section, subsection, etc.)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY(source_id) REFERENCES sources(source_id),
    UNIQUE(source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_active ON documents(is_active);


-- Query History: complete audit trail of all queries
CREATE TABLE IF NOT EXISTS query_history (
    query_id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_type TEXT NOT NULL,
    source_filter TEXT,  -- JSON-encoded filter
    num_results INTEGER,
    confidence_threshold REAL,
    result_count INTEGER,
    result_metadata TEXT,  -- JSON with scores, timing, etc.
    model_used TEXT,
    response_length INTEGER,
    user_feedback TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_history_type ON query_history(query_type);
CREATE INDEX IF NOT EXISTS idx_query_history_created ON query_history(created_at);
CREATE INDEX IF NOT EXISTS idx_query_history_model ON query_history(model_used);


-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    applied_at TEXT NOT NULL,
    migration_file TEXT
);
"""
