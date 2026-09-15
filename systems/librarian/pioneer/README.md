# PIONEER Research System

PIONEER is the canonical scientific operating layer for Librarian and Research Assistant. It exists to generate falsifiable, evidence-grounded, reproducible new knowledge—not to accumulate documents or repeat unsupported system claims.

## One pipeline

1. Register a question and falsifiable hypothesis.
2. Freeze predictions, protocol, data requirements, thresholds, and contamination controls.
3. Retrieve evidence with provenance and an explicit search for contradiction and null results.
4. Execute only after stability, ethics, data, and replication gates pass.
5. Preserve raw observations; separate transformations and analysis.
6. Report effect sizes, uncertainty, failure cases, limitations, and alternative explanations.
7. Require independent replication before a claim becomes established.
8. Produce a project paper, white paper, or replication package only from completed evidence records.

## Canonical surfaces

- Experiment registry: `../experiments/registry.json`
- Research Assistant reference: `../research_assistant/PIONEER_LINK.json`
- Literature corpus: `../data/academic_corpus.db`
- Retrieval corpus: `../data/librarian.db`
- Dataset registry: `PIONEER_DATASET_REGISTER.json`
- Publication registry: `PIONEER_PUBLICATION_REGISTER.json`
- Learning journal: `journal/events.jsonl`
- Engineering feedback queue: `engineering_feedback/pending.jsonl`
- System audit: `PIONEER_AUDIT.json`
- Resource optimization and measurement: `PIONEER_RESOURCE_OPTIMIZATION.json`
- Content-address integrity inventory: `PIONEER_CONTENT_INVENTORY.json`
- Storage and retention policy: `PIONEER_STORAGE_POLICY.json`
- Compact journal index: `journal/index.json`
- Last independently observed test result: `PIONEER_TEST_STATUS.json`
- Engineering Studio takeover protocol: `ENGINEERING_STUDIO_TAKEOVER.md`
- Engineering Studio comparison anchor: `ENGINEERING_STUDIO_BASELINE.json`

## Learning loop

Thoughts and reasoning are recorded as observations, never automatically treated as facts. Decisions, successes, failures, academic comparisons, lessons, and optimization proposals are appended to a SHA-256 hash chain. Only evidence-linked, reviewable events may be promoted to Engineering Studio. Promotion creates a pending recommendation; it never executes a system change automatically.

All volume and iCloud research trees are reference or archive surfaces unless explicitly promoted through a hashed canonical registry event.

## Resource discipline

Ingestion is incremental and skips unchanged source/parser/chunker combinations. Chunk text is globally deduplicated by a normalized SHA-256 address. Academic retrieval has an FTS5 candidate index but retains the deterministic lexical scorer as its result contract. At the present 22-source scale, measured FTS timing is slower than scanning, so no speedup is claimed; the index exists for scale readiness and must continue to pass equivalence checks. Database optimization is additive, integrity-checked, physically idempotent, and never automatically vacuums or deletes evidence.
