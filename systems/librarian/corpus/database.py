"""SQLite database operations for the Librarian corpus store.

RECOVERED from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/storage/database.py
(commit 514c8f8). Logic unchanged (7/7 storage tests, re-verified this
mission) except one documentation-honesty fix, described below.

MODERNIZE fix applied during recovery: the donor class is named
`DatabaseConnectionPool` and its docstring said "Thread-safe SQLite
connection pool" — but `get_connection()` opens a brand-new
`sqlite3.connect()` and closes it on every call; nothing is actually
pooled or reused across calls. Thread-safety is real (every thread gets
its own fresh connection, so there is no shared-connection race), but
"pool" overstates the mechanism. The docstrings below say so plainly
rather than silently keep the overclaim. The class NAME is kept
(`DatabaseConnectionPool`) for import compatibility with the recovered
`corpus/schema.py` callers and `ingestion/pipeline.py`.
"""

import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
import threading

from .schema import SCHEMA_SQL, Source, Document, QueryHistory


class DatabaseConnectionPool:
    """Thread-safe SQLite connection FACTORY (not a true pool despite the
    name, kept for compatibility with recovered callers) with automatic
    schema initialization. Each `get_connection()` call opens a fresh,
    short-lived connection and closes it on exit -- thread-safety follows
    from that (no connection is ever shared across threads), not from
    actual connection reuse."""

    def __init__(self, db_path: str | Path, max_connections: int = 5):
        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self._connections = []
        self._lock = threading.Lock()
        self._initialized = False

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self):
        """Create tables and schema if they don't exist."""
        if self._initialized:
            return

        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        self._initialized = True

    @contextmanager
    def get_connection(self):
        """Get a database connection with auto-commit."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close_all(self):
        """Close all pooled connections."""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()


class SourceStore:
    """CRUD operations for Source entities."""

    def __init__(self, pool: DatabaseConnectionPool):
        self.pool = pool

    def create(self, source: Source) -> bool:
        """Insert a new source. Returns True if successful."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute("""
                    INSERT INTO sources (
                        source_id, title, source_type, url, author,
                        published_date, summary, tags, metadata,
                        created_at, updated_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(source.to_dict().values()))
                return True
        except sqlite3.IntegrityError:
            return False

    def get(self, source_id: str) -> Optional[Source]:
        """Retrieve a source by ID."""
        with self.pool.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE source_id = ?",
                (source_id,)
            ).fetchone()

        if row:
            return self._row_to_source(row)
        return None

    def list_active(self, source_type: Optional[str] = None) -> List[Source]:
        """List all active sources, optionally filtered by type."""
        with self.pool.get_connection() as conn:
            if source_type:
                rows = conn.execute(
                    "SELECT * FROM sources WHERE is_active = 1 AND source_type = ? "
                    "ORDER BY created_at DESC",
                    (source_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sources WHERE is_active = 1 ORDER BY created_at DESC"
                ).fetchall()

        return [self._row_to_source(row) for row in rows]

    def update(self, source: Source) -> bool:
        """Update an existing source."""
        source.updated_at = datetime.now(timezone.utc).isoformat()
        with self.pool.get_connection() as conn:
            result = conn.execute("""
                UPDATE sources SET
                    title = ?, source_type = ?, url = ?, author = ?,
                    published_date = ?, summary = ?, tags = ?, metadata = ?,
                    updated_at = ?, is_active = ?
                WHERE source_id = ?
            """, (
                source.title, source.source_type, source.url, source.author,
                source.published_date, source.summary,
                json.dumps(source.tags), json.dumps(source.metadata),
                source.updated_at, 1 if source.is_active else 0,
                source.source_id
            ))
            return result.rowcount > 0

    def delete(self, source_id: str) -> bool:
        """Soft-delete a source (mark as inactive)."""
        with self.pool.get_connection() as conn:
            result = conn.execute(
                "UPDATE sources SET is_active = 0, updated_at = ? WHERE source_id = ?",
                (datetime.now(timezone.utc).isoformat(), source_id)
            )
            return result.rowcount > 0

    def count_active(self) -> int:
        """Count active sources."""
        with self.pool.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) as count FROM sources WHERE is_active = 1"
            ).fetchone()
        return result['count']

    @staticmethod
    def _row_to_source(row) -> Source:
        return Source(
            source_id=row['source_id'],
            title=row['title'],
            source_type=row['source_type'],
            url=row['url'],
            author=row['author'],
            published_date=row['published_date'],
            summary=row['summary'],
            tags=json.loads(row['tags'] or '[]'),
            metadata=json.loads(row['metadata'] or '{}'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            is_active=bool(row['is_active'])
        )


class DocumentStore:
    """CRUD operations for Document entities."""

    def __init__(self, pool: DatabaseConnectionPool):
        self.pool = pool

    def create(self, document: Document) -> bool:
        """Insert a new document."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute("""
                    INSERT INTO documents (
                        document_id, source_id, title, content_hash,
                        chunk_index, tokens, metadata,
                        created_at, updated_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(document.to_dict().values()))
                return True
        except sqlite3.IntegrityError:
            return False

    def get(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        with self.pool.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,)
            ).fetchone()

        if row:
            return self._row_to_document(row)
        return None

    def list_by_source(self, source_id: str) -> List[Document]:
        """List all active documents in a source."""
        with self.pool.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE source_id = ? AND is_active = 1 "
                "ORDER BY chunk_index ASC",
                (source_id,)
            ).fetchall()

        return [self._row_to_document(row) for row in rows]

    def get_by_hash(self, content_hash: str) -> Optional[Document]:
        """Find document by content hash (for deduplication)."""
        with self.pool.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ? LIMIT 1",
                (content_hash,)
            ).fetchone()

        if row:
            return self._row_to_document(row)
        return None

    def update(self, document: Document) -> bool:
        """Update an existing document."""
        document.updated_at = datetime.now(timezone.utc).isoformat()
        with self.pool.get_connection() as conn:
            result = conn.execute("""
                UPDATE documents SET
                    title = ?, content_hash = ?, chunk_index = ?,
                    tokens = ?, metadata = ?, updated_at = ?, is_active = ?
                WHERE document_id = ?
            """, (
                document.title, document.content_hash, document.chunk_index,
                document.tokens, json.dumps(document.metadata),
                document.updated_at, 1 if document.is_active else 0,
                document.document_id
            ))
            return result.rowcount > 0

    def delete(self, document_id: str) -> bool:
        """Soft-delete a document."""
        with self.pool.get_connection() as conn:
            result = conn.execute(
                "UPDATE documents SET is_active = 0, updated_at = ? WHERE document_id = ?",
                (datetime.now(timezone.utc).isoformat(), document_id)
            )
            return result.rowcount > 0

    def count_by_source(self, source_id: str) -> int:
        """Count active documents in a source."""
        with self.pool.get_connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) as count FROM documents WHERE source_id = ? AND is_active = 1",
                (source_id,)
            ).fetchone()
        return result['count']

    @staticmethod
    def _row_to_document(row) -> Document:
        return Document(
            document_id=row['document_id'],
            source_id=row['source_id'],
            title=row['title'],
            content_hash=row['content_hash'],
            chunk_index=row['chunk_index'],
            tokens=row['tokens'],
            metadata=json.loads(row['metadata'] or '{}'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            is_active=bool(row['is_active'])
        )


class QueryHistoryStore:
    """Audit log for all queries made to the system."""

    def __init__(self, pool: DatabaseConnectionPool):
        self.pool = pool

    def log_query(self, query: QueryHistory) -> bool:
        """Log a query to the audit trail."""
        try:
            with self.pool.get_connection() as conn:
                conn.execute("""
                    INSERT INTO query_history (
                        query_id, query_text, query_type, source_filter,
                        num_results, confidence_threshold, result_count,
                        result_metadata, model_used, response_length,
                        user_feedback, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(query.to_dict().values()))
                return True
        except sqlite3.IntegrityError:
            return False

    def get_query(self, query_id: str) -> Optional[QueryHistory]:
        """Retrieve a logged query."""
        with self.pool.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM query_history WHERE query_id = ?",
                (query_id,)
            ).fetchone()

        if row:
            return self._row_to_query(row)
        return None

    def list_recent(self, limit: int = 100, query_type: Optional[str] = None) -> List[QueryHistory]:
        """List recent queries, optionally filtered by type."""
        with self.pool.get_connection() as conn:
            if query_type:
                rows = conn.execute(
                    "SELECT * FROM query_history WHERE query_type = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (query_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM query_history ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()

        return [self._row_to_query(row) for row in rows]

    def set_feedback(self, query_id: str, feedback: str) -> bool:
        """Update user feedback on a query."""
        with self.pool.get_connection() as conn:
            result = conn.execute(
                "UPDATE query_history SET user_feedback = ? WHERE query_id = ?",
                (feedback, query_id)
            )
            return result.rowcount > 0

    @staticmethod
    def _row_to_query(row) -> QueryHistory:
        return QueryHistory(
            query_id=row['query_id'],
            query_text=row['query_text'],
            query_type=row['query_type'],
            source_filter=row['source_filter'],
            num_results=row['num_results'],
            confidence_threshold=row['confidence_threshold'],
            result_count=row['result_count'],
            result_metadata=json.loads(row['result_metadata'] or '{}'),
            model_used=row['model_used'],
            response_length=row['response_length'],
            user_feedback=row['user_feedback'],
            created_at=row['created_at']
        )
