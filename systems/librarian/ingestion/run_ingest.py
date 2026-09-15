"""CLI entrypoint for Librarian corpus ingestion.

Usage:
    python -m ingestion.run_ingest --dry-run ROOT [ROOT ...]
    python -m ingestion.run_ingest ROOT [ROOT ...]

RECOVERED from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/ingestion/run_ingest.py
(commit d855206). MODERNIZE fix applied during recovery: the donor
hardcoded `DEFAULT_ROOTS` to two machine-specific relative paths (`~/Librarian`
via 4 parent-directory hops, and the donor's own `systems/librarian` scaffold
tree). `~/Librarian` no longer exists on this machine (confirmed in
LIBRARIAN_DONOR_FORENSIC_REPORT.md) and a canonical `systems/librarian`
self-referencing its own package directory makes no sense. Roots are now
REQUIRED arguments -- no silently-stale default is carried forward. The
already-ingested real corpus (93 sources / 297 documents, ingested
2026-08-09) is preserved as-is in `data/` (see CORPUS_STORAGE_ARCHITECTURE.md);
re-running this CLI against a new root only ADDS to or updates that corpus,
it never erases the historical rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from corpus import DatabaseConnectionPool
from ingestion import IngestionPipeline


def main(argv=None):
    ap = argparse.ArgumentParser(description="Librarian corpus ingestion")
    ap.add_argument("roots", nargs="+", help="corpus roots to ingest (required -- no default)")
    ap.add_argument("--dry-run", action="store_true", help="census only, no writes")
    ap.add_argument("--data-dir", default="data", help="output dir for db + content")
    ap.add_argument("--json", action="store_true", help="emit machine-readable summary")
    args = ap.parse_args(argv)

    roots = args.roots
    data_dir = Path(args.data_dir)
    pool = DatabaseConnectionPool(data_dir / "librarian.db")
    pool.initialize()
    pipe = IngestionPipeline(pool, data_dir / "content")

    result = pipe.run(roots, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    c = result.census
    mode = "DRY-RUN CENSUS" if args.dry_run else "INGESTION"
    print(f"\n=== Librarian {mode} ===")
    print(f"run_id: {result.run_id}")
    print(f"roots:  {roots}")
    print("\n-- Corpus census --")
    print(f"  total files:        {c.total_files}")
    print(f"  valid (supported):  {c.valid_files}")
    print(f"  unreadable:         {c.unreadable_files}")
    print(f"  empty:              {c.empty_files}")
    print(f"  unsupported:        {c.unsupported_files}")
    print(f"  exact-dup files:    {c.exact_duplicate_files}")
    print(f"  unique src hashes:  {c.unique_source_hashes}")
    print(f"  total bytes:        {c.total_bytes}")
    print(f"  source types:       {c.source_types}")
    print(f"  unsupported types:  {c.unsupported_types}")
    print("\n-- Estimates --")
    print(f"  estimated documents: {result.estimated_documents}")
    print(f"  estimated chunks:    {result.estimated_chunks}")
    print(f"  duplicate content:   {result.duplicate_content_chunks}")
    if not args.dry_run:
        print("\n-- Applied --")
        print(f"  created:            {result.created}")
        print(f"  updated:            {result.updated}")
        print(f"  skipped unchanged:  {result.skipped_unchanged}")
        print(f"  skipped duplicate:  {result.skipped_duplicate}")
        print(f"  deleted:            {result.deleted}")
        print(f"  errors:             {result.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
