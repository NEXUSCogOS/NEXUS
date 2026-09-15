"""Staged ingestion pipeline orchestrator.

RECOVERED from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/ingestion/pipeline.py
(commit d855206, "phase 3 - evidence-gated Librarian corpus ingestion").
Logic unchanged (including the `_canonical`-owner chunk-identity fix the
donor's own commit message describes fixing a real UNIQUE-collision bug);
only import paths updated for the canonical `corpus`/`provenance` module
layout. Part of the 22/22 test baseline, re-verified this mission.

Stages: discovery -> validation -> provenance -> dedup -> normalize -> chunk ->
enrich -> SQL persist -> JSON persist -> audit log. Supports --dry-run (census
only, no writes) and is idempotent: re-running over an unchanged corpus creates
no new sources, documents, or chunks.

Dedup model:
  - source-level: identical file bytes (source_hash) under a different path are
    recorded as skipped_duplicate; no second source row is created.
  - chunk-level: identical chunk text (content_hash) is stored once in the
    documents table and the content store; every source still maps its own
    ordered chunk_index -> content_hash via chunk_map for reconstruction.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from corpus import (
    Source,
    Document,
    DatabaseConnectionPool,
    SourceStore,
    DocumentStore,
    JsonContentStore,
)
from .provenance import (
    INGESTION_SCHEMA_SQL,
    PARSER_VERSION,
    CHUNKER_VERSION,
    utc_now,
    sha256_text,
)
from .discovery import discover, build_census, DiscoveredFile, CensusReport
from .normalize import normalize_text, chunk_text

CONTENT_BUCKET = "_corpus_chunks"  # single content-hash-keyed dedup bucket


def _source_id(abs_path: str) -> str:
    return "src_" + hashlib.sha256(abs_path.encode()).hexdigest()[:16]


def _document_id(content_hash: str) -> str:
    return "doc_" + content_hash[:24]


def _run_id(seed: str) -> str:
    return "run_" + hashlib.sha256(seed.encode()).hexdigest()[:12]


@dataclass
class IngestResult:
    run_id: str
    dry_run: bool
    census: CensusReport
    created: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    skipped_duplicate: int = 0
    deleted: int = 0
    errors: int = 0
    estimated_documents: int = 0     # dry-run: total chunks that would exist
    estimated_chunks: int = 0
    duplicate_content_chunks: int = 0  # chunks whose content_hash already seen
    actions: list = field(default_factory=list)  # (rel_path, action, reason)

    def to_dict(self) -> dict:
        d = {
            "run_id": self.run_id,
            "dry_run": self.dry_run,
            "created": self.created,
            "updated": self.updated,
            "skipped_unchanged": self.skipped_unchanged,
            "skipped_duplicate": self.skipped_duplicate,
            "deleted": self.deleted,
            "errors": self.errors,
            "estimated_documents": self.estimated_documents,
            "estimated_chunks": self.estimated_chunks,
            "duplicate_content_chunks": self.duplicate_content_chunks,
        }
        d.update(self.census.to_dict())
        return d


class IngestionPipeline:
    def __init__(self, pool: DatabaseConnectionPool, content_root: str | Path):
        self.pool = pool
        self.sources = SourceStore(pool)
        self.documents = DocumentStore(pool)
        self.content = JsonContentStore(content_root)
        self._ensure_schema()

    def _ensure_schema(self):
        with self.pool.get_connection() as conn:
            conn.executescript(INGESTION_SCHEMA_SQL)

    # ---- audit -------------------------------------------------------------
    def _log(self, conn, run_id, df: Optional[DiscoveredFile], source_id,
             action, reason, source_hash, documents, dry_run):
        rel = df.rel_path if df else None
        log_id = "log_" + hashlib.sha256(
            f"{run_id}:{source_id}:{action}:{rel}".encode()
        ).hexdigest()[:20]
        conn.execute(
            """INSERT OR REPLACE INTO ingestion_log (
                log_id, run_id, source_id, rel_path, action, reason,
                source_hash, parser_version, chunker_version, documents,
                dry_run, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (log_id, run_id, source_id, rel, action, reason, source_hash,
             PARSER_VERSION, CHUNKER_VERSION, documents,
             1 if dry_run else 0, utc_now()),
        )

    # ---- main entry --------------------------------------------------------
    def run(self, roots: list[str | Path], dry_run: bool = False) -> IngestResult:
        files = discover(roots)
        census = build_census(files)
        run_id = _run_id("|".join(str(Path(r).resolve()) for r in roots) +
                          ("|dry" if dry_run else "|real"))
        result = IngestResult(run_id=run_id, dry_run=dry_run, census=census)

        supported = [f for f in files if f.status == "supported"]

        # Track source-level and chunk-level dedup across this run.
        seen_source_hash: dict[str, str] = {}   # source_hash -> first rel_path
        seen_content_hash: set[str] = set()

        for df in supported:
            prov = df.provenance
            assert prov is not None
            sh = prov.source_hash

            # --- source-level exact-duplicate detection ---
            if sh in seen_source_hash:
                result.skipped_duplicate += 1
                result.actions.append(
                    (df.rel_path, "skipped_duplicate",
                     f"same bytes as {seen_source_hash[sh]}"))
                if not dry_run:
                    with self.pool.get_connection() as conn:
                        self._log(conn, run_id, df, _source_id(prov.abs_path),
                                  "skipped_duplicate",
                                  f"dup of {seen_source_hash[sh]}", sh, 0, dry_run)
                continue
            seen_source_hash[sh] = df.rel_path

            normalized = normalize_text(df.raw_text or "")
            chunks = chunk_text(normalized)
            result.estimated_chunks += len(chunks)
            result.estimated_documents += len(chunks)
            for ch in chunks:
                h = sha256_text(ch.text)
                if h in seen_content_hash:
                    result.duplicate_content_chunks += 1
                else:
                    seen_content_hash.add(h)

            if dry_run:
                result.actions.append((df.rel_path, "would_ingest",
                                       f"{len(chunks)} chunks"))
                continue

            try:
                self._ingest_one(run_id, df, chunks, result)
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                result.errors += 1
                result.actions.append((df.rel_path, "error", repr(exc)))
                with self.pool.get_connection() as conn:
                    self._log(conn, run_id, df, _source_id(prov.abs_path),
                              "error", repr(exc), sh, 0, dry_run)

        if not dry_run:
            self._handle_deletions(run_id, roots, result)

        return result

    # ---- per-source transactional ingest -----------------------------------
    def _ingest_one(self, run_id, df: DiscoveredFile, chunks,
                    result: IngestResult):
        prov = df.provenance
        assert prov is not None
        sid = _source_id(prov.abs_path)
        existing = self.sources.get(sid)

        # Unchanged: same bytes AND same processing versions -> skip.
        if existing is not None:
            meta = existing.metadata
            if (meta.get("source_hash") == prov.source_hash
                    and meta.get("parser_version") == PARSER_VERSION
                    and meta.get("chunker_version") == CHUNKER_VERSION):
                result.skipped_unchanged += 1
                result.actions.append((df.rel_path, "skipped_unchanged", ""))
                with self.pool.get_connection() as conn:
                    self._log(conn, run_id, df, sid, "skipped_unchanged", "",
                              prov.source_hash, 0, False)
                return

        action = "updated" if existing is not None else "created"

        # One transaction spanning SQL metadata + chunk_map + audit. JSON
        # content is written first (content-addressed, dedup-safe, idempotent);
        # if the SQL transaction rolls back, orphan content is harmless and
        # overwritten on retry.
        for ch in chunks:
            h = sha256_text(ch.text)
            self.content.put(CONTENT_BUCKET, h, ch.text)

        with self.pool.get_connection() as conn:
            if existing is not None:
                # Re-chunk: drop this source's mapping, GC canonical chunks that
                # no longer belong to any source, then refresh the source row.
                conn.execute("DELETE FROM chunk_map WHERE source_id = ?", (sid,))
                conn.execute(
                    "DELETE FROM documents WHERE content_hash NOT IN "
                    "(SELECT content_hash FROM chunk_map)"
                )
                conn.execute(
                    "UPDATE sources SET metadata = ?, updated_at = ?, "
                    "is_active = 1 WHERE source_id = ?",
                    (_dump_meta(prov, existing), utc_now(), sid),
                )
            else:
                src = Source(
                    source_id=sid,
                    title=_title_from(df.rel_path),
                    source_type=_type_from(prov.root),
                    url=prov.abs_path,
                    summary=None,
                    tags=_tags_from(df.rel_path),
                    metadata=prov.to_metadata(),
                )
                conn.execute(
                    """INSERT INTO sources (source_id,title,source_type,url,
                        author,published_date,summary,tags,metadata,
                        created_at,updated_at,is_active)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    tuple(src.to_dict().values()),
                )

            for ch in chunks:
                h = sha256_text(ch.text)
                did = _document_id(h)
                # Canonical unique chunk row: keyed by content_hash (global
                # dedup). Owner is the synthetic "_canonical" bucket with a
                # monotonic sequence index, decoupling chunk identity from any
                # real source so re-chunking a source never collides on
                # UNIQUE(source_id, chunk_index). True origin is in metadata.
                row = conn.execute(
                    "SELECT document_id FROM documents WHERE content_hash = ?",
                    (h,),
                ).fetchone()
                if row is None:
                    seq = conn.execute(
                        "SELECT COUNT(*) c FROM documents"
                    ).fetchone()["c"]
                    doc = Document(
                        document_id=did,
                        source_id="_canonical",
                        title=f"{_title_from(df.rel_path)} #{ch.index}",
                        content_hash=h,
                        chunk_index=seq,
                        tokens=max(1, len(ch.text) // 4),
                        metadata={"origin_source": sid, "origin_index": ch.index},
                    )
                    conn.execute(
                        """INSERT INTO documents (document_id,source_id,title,
                            content_hash,chunk_index,tokens,metadata,
                            created_at,updated_at,is_active)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        tuple(doc.to_dict().values()),
                    )
                    canonical_did = did
                else:
                    canonical_did = row["document_id"]

                conn.execute(
                    """INSERT OR REPLACE INTO chunk_map (source_id,chunk_index,
                        content_hash,document_id,tokens,parser_version,
                        chunker_version,created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (sid, ch.index, h, canonical_did,
                     max(1, len(ch.text) // 4), PARSER_VERSION,
                     CHUNKER_VERSION, utc_now()),
                )

            self._log(conn, run_id, df, sid, action, "", prov.source_hash,
                      len(chunks), False)

        if action == "created":
            result.created += 1
        else:
            result.updated += 1
        result.actions.append((df.rel_path, action, f"{len(chunks)} chunks"))

    # ---- deleted-source handling -------------------------------------------
    def _handle_deletions(self, run_id, roots, result):
        # Any active source whose url is under a scanned root but no longer
        # exists on disk is soft-deleted (and its chunk_map cleared).
        root_prefixes = [str(Path(r).resolve()) for r in roots]
        for src in self.sources.list_active():
            url = src.url or ""
            if not any(url.startswith(pfx) for pfx in root_prefixes):
                continue
            if not Path(url).exists():
                self.sources.delete(src.source_id)
                with self.pool.get_connection() as conn:
                    conn.execute("DELETE FROM chunk_map WHERE source_id = ?",
                                 (src.source_id,))
                    self._log(conn, run_id, None, src.source_id, "deleted",
                              "file no longer present", None, 0, False)
                result.deleted += 1
                result.actions.append((url, "deleted", "file removed"))

    # ---- reconstruction (used by tests and retrieval/lexical_search.py) ----
    def reconstruct(self, source_id: str) -> Optional[str]:
        with self.pool.get_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_index, content_hash FROM chunk_map "
                "WHERE source_id = ? ORDER BY chunk_index ASC",
                (source_id,),
            ).fetchall()
        if not rows:
            return None
        parts = []
        for row in rows:
            text = self.content.get(CONTENT_BUCKET, row["content_hash"])
            if text is None:
                return None
            parts.append(text)
        return "\n\n".join(parts)


def _dump_meta(prov, existing) -> str:
    import json
    meta = dict(existing.metadata)
    meta.update(prov.to_metadata())
    return json.dumps(meta)


def _title_from(rel_path: str) -> str:
    return Path(rel_path).stem.replace("-", " ").replace("_", " ").strip()


def _type_from(root: str) -> str:
    name = Path(root).name.lower()
    return f"librarian:{name}"


def _tags_from(rel_path: str) -> list[str]:
    parts = Path(rel_path).parts[:-1]
    return [p for p in parts if p not in (".", "")]
