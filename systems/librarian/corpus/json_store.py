"""Content storage for the Librarian corpus.

RECOVERED from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/storage/json_store.py
(commit 514c8f8); part of the 7/7 storage test baseline.

Document text lives on disk as JSON files sharded by source_id, keeping the
SQLite database small and queryable while full text stays cheap to stream.

DEFECT FIX applied during F3 (found via the corrupted-evidence failure
test, tests/failure/test_failure_modes.py test_10): `_load()` previously
let `json.JSONDecodeError` propagate uncaught out of a single corrupted
shard file, crashing retrieval for the ENTIRE corpus rather than degrading
gracefully for just that one source. `_load()` now treats an unparseable
shard as empty (equivalent to "no content available for this source"),
matching the same fail-closed-but-isolated philosophy the ingestion
pipeline already applies to unreadable/malformed source files.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional


def content_hash(text: str) -> str:
    """SHA256 of normalized content, used as the deduplication key."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class JsonContentStore:
    """Filesystem-backed store mapping document_id -> text."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, source_id: str) -> Path:
        return self.root / f"{source_id}.json"

    def _load(self, source_id: str) -> dict:
        path = self._path(source_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            # A single corrupted shard degrades to "no content for this
            # source" -- it must never crash retrieval across the whole
            # corpus. See the module docstring's F3 DEFECT FIX note.
            return {}

    def _save(self, source_id: str, payload: dict) -> None:
        tmp = self._path(source_id).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path(source_id))

    def put(self, source_id: str, document_id: str, text: str) -> str:
        payload = self._load(source_id)
        payload[document_id] = text
        self._save(source_id, payload)
        return content_hash(text)

    def get(self, source_id: str, document_id: str) -> Optional[str]:
        return self._load(source_id).get(document_id)

    def get_all(self, source_id: str) -> dict[str, str]:
        return self._load(source_id)

    def delete(self, source_id: str, document_id: str) -> bool:
        payload = self._load(source_id)
        if document_id not in payload:
            return False
        del payload[document_id]
        self._save(source_id, payload)
        return True

    def delete_source(self, source_id: str) -> bool:
        path = self._path(source_id)
        if not path.exists():
            return False
        path.unlink()
        return True
