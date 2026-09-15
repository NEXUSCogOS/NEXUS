"""Ingests the real, curated academic source manifest into the academic
corpus store.

NEW module, NEXUS Librarian F4. Every record in `real_source_manifest.json`
was fetched live from arXiv's own export API (export.arxiv.org/api/query)
during this mission -- title, authors, arXiv id, publication date, and
full abstract text are verbatim, not paraphrased or invented. This script
performs NO web access itself; it only classifies and persists what was
already retrieved.

Classification policy (conservative, disclosed): every source here is
classified ACADEMIC_PREPRINT. Three records carry a DOI in the manifest
(pointing at a Springer book chapter and two other venues) -- their
peer-reviewed venue was NOT independently verified this mission (no
follow-up fetch confirmed the DOI resolves to a real peer-reviewed
publication), so this script does NOT upgrade them to
PEER_REVIEWED_CONFERENCE/JOURNAL. Under-claiming source quality is the
correct default per the mission's anti-fabrication requirement --
verifying and upgrading these three is listed as future work in
LIBRARIAN_LIMITATIONS.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from academic.identity import compute_source_id
from academic.provenance import AcademicProvenance, RetractionStatus, VerificationStatus
from academic.store import AcademicStore
from academic.taxonomy import SourceType

MANIFEST_PATH = Path(__file__).resolve().parent / "real_source_manifest.json"
INGESTION_METHOD = "arxiv_export_api_live_fetch_2026-08-27"


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def build_provenance(record: dict) -> AcademicProvenance:
    external_ids = {"arxiv": record["id"]}
    doi = record.get("doi", "UNKNOWN")
    source_id = compute_source_id(
        external_identifiers=external_ids,
        canonical_url=f"https://arxiv.org/abs/{record['id']}",
        fallback_content=record["summary"],
    )
    return AcademicProvenance(
        source_id=source_id,
        title=record["title"],
        authors=record["authors"],
        publication_date=record["published"],
        journal_or_venue="UNKNOWN",  # not independently verified -- see module docstring
        publisher="arXiv",
        doi=doi,
        external_identifiers=external_ids,
        canonical_url=f"https://arxiv.org/abs/{record['id']}",
        source_type=SourceType.ACADEMIC_PREPRINT,
        peer_review_status="UNVERIFIED",
        retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
        content_hash="UNKNOWN",  # set at persist time from the actual retrievable text
        license="UNKNOWN",
        language="en",
        version="UNKNOWN",
        retraction_status=RetractionStatus.ACTIVE,
        correction_status="NONE",
        ingestion_method=INGESTION_METHOD,
        verification_status=VerificationStatus.PARTIAL,  # existence+metadata confirmed live; full-text fidelity not independently re-checked
    )


def ingest_all(store: AcademicStore) -> dict:
    import hashlib

    manifest = load_manifest()
    created = 0
    skipped = 0
    for record in manifest:
        prov = build_provenance(record)
        content_hash = hashlib.sha256(record["summary"].strip().encode("utf-8")).hexdigest()
        row = prov.model_dump(mode="json")
        row["content_hash"] = content_hash
        row["retrievable_text"] = record["summary"]
        row["retraction_status"] = prov.retraction_status.value
        row["verification_status"] = prov.verification_status.value
        row["source_type"] = prov.source_type.value
        inserted = store.upsert_source(row)
        if inserted:
            created += 1
            store.record_event(row["source_id"], event_type="INGESTED", detail=f"arxiv:{record['id']}, {INGESTION_METHOD}")
        else:
            skipped += 1
    return {"created": created, "skipped_existing": skipped, "total_in_manifest": len(manifest)}


if __name__ == "__main__":
    import sys

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data"
    store = AcademicStore(data_dir / "academic_corpus.db")
    result = ingest_all(store)
    print(json.dumps(result, indent=2))
