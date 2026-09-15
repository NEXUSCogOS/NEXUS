"""Stage 1-3: source discovery, type validation, provenance capture.

RECOVERED unchanged from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/ingestion/discovery.py
(commit d855206). No logic changes; part of the 22/22 test baseline.

Note: `provenance.py` is kept inside `ingestion/` (matching the donor's
own original layout) rather than promoted to a separate top-level
`provenance/` package as the mission's target tree names it — a separate
top-level `provenance` package would collide with NEXUS Federation's own
`provenance` package (ProvenanceRecord graph, F2), which must be
importable on the SAME PYTHONPATH as this module once Librarian's
institutional contract adapter runs. See LIBRARIAN_CANONICAL_ARCHITECTURE.md.

Read-only. Walks the configured corpus roots, classifies every file, reads and
hashes the supported ones, and records why each unsupported/unreadable/empty
file was excluded. Nothing here writes to the stores — the census runs entirely
on the output of this stage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .provenance import Provenance, sha256_bytes

SUPPORTED_EXTENSIONS = {".md", ".txt"}

# Directories that are tooling/state, never knowledge content.
EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv", "venv"}


@dataclass
class DiscoveredFile:
    root: str
    rel_path: str
    abs_path: str
    ext: str
    status: str            # supported|unsupported|unreadable|empty
    byte_size: int = 0
    reason: str = ""
    provenance: Optional[Provenance] = None
    raw_text: Optional[str] = None


@dataclass
class CensusReport:
    total_files: int = 0
    valid_files: int = 0
    unreadable_files: int = 0
    empty_files: int = 0
    unsupported_files: int = 0
    exact_duplicate_files: int = 0        # same bytes, different path
    total_bytes: int = 0
    source_types: dict = field(default_factory=dict)      # ext -> count
    unsupported_types: dict = field(default_factory=dict)  # ext -> count
    unique_source_hashes: int = 0

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "valid_files": self.valid_files,
            "unreadable_files": self.unreadable_files,
            "empty_files": self.empty_files,
            "unsupported_files": self.unsupported_files,
            "exact_duplicate_files": self.exact_duplicate_files,
            "total_bytes": self.total_bytes,
            "source_types": dict(sorted(self.source_types.items())),
            "unsupported_types": dict(sorted(self.unsupported_types.items())),
            "unique_source_hashes": self.unique_source_hashes,
        }


def _iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        for name in filenames:
            if name == ".DS_Store":
                continue
            yield Path(dirpath) / name


def discover(roots: list[str | Path]) -> list[DiscoveredFile]:
    """Walk roots and classify every file. Read-only."""
    out: list[DiscoveredFile] = []
    for root in roots:
        root_path = Path(root).resolve()
        if not root_path.exists():
            continue
        for path in _iter_files(root_path):
            rel = str(path.relative_to(root_path))
            ext = path.suffix.lower()
            df = DiscoveredFile(
                root=str(root_path),
                rel_path=rel,
                abs_path=str(path),
                ext=ext or "(none)",
                status="",
            )
            if ext not in SUPPORTED_EXTENSIONS:
                df.status = "unsupported"
                df.reason = f"extension {df.ext} not in supported set"
                out.append(df)
                continue
            try:
                data = path.read_bytes()
            except (OSError, PermissionError) as exc:
                df.status = "unreadable"
                df.reason = f"read error: {exc.__class__.__name__}"
                out.append(df)
                continue

            df.byte_size = len(data)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                df.status = "unreadable"
                df.reason = "utf-8 decode error"
                out.append(df)
                continue

            if not text.strip():
                df.status = "empty"
                df.reason = "no non-whitespace content"
                out.append(df)
                continue

            mtime = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            df.status = "supported"
            df.raw_text = text
            df.provenance = Provenance(
                root=str(root_path),
                rel_path=rel,
                abs_path=str(path),
                source_hash=sha256_bytes(data),
                byte_size=len(data),
                mtime=mtime,
            )
            out.append(df)
    return out


def build_census(files: list[DiscoveredFile]) -> CensusReport:
    """Aggregate discovery output into a census. Pure function, no I/O."""
    report = CensusReport()
    seen_hashes: set[str] = set()
    for df in files:
        report.total_files += 1
        if df.status == "supported":
            report.valid_files += 1
            report.total_bytes += df.byte_size
            report.source_types[df.ext] = report.source_types.get(df.ext, 0) + 1
            h = df.provenance.source_hash  # type: ignore[union-attr]
            if h in seen_hashes:
                report.exact_duplicate_files += 1
            else:
                seen_hashes.add(h)
        elif df.status == "unreadable":
            report.unreadable_files += 1
        elif df.status == "empty":
            report.empty_files += 1
        elif df.status == "unsupported":
            report.unsupported_files += 1
            report.unsupported_types[df.ext] = (
                report.unsupported_types.get(df.ext, 0) + 1
            )
    report.unique_source_hashes = len(seen_hashes)
    return report
