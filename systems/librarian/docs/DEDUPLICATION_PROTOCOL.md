# DEDUPLICATION PROTOCOL
**NEXUS Federation F3 — 2026-08-27**

Recovered unchanged from the donor. Two independent, complementary
mechanisms:

## 1. Source-level (exact file duplicate)

Two files with identical bytes (`sha256` of raw content), regardless of
path or filename, are recognized as the same source. Only the first-seen
path becomes a `sources` row; every subsequent identical file is logged
`skipped_duplicate`, never creating a second source row. Proven: 16
exact-duplicate files correctly excluded in the real corpus
(`LIBRARIAN_CORPUS_AUDIT.md`), and by
`test_exact_duplicate_file_skipped`.

## 2. Chunk-level (identical content across different sources)

After normalization and chunking, each chunk's `sha256` of its
normalized text is the dedup key. Two DIFFERENT sources containing an
identical paragraph (e.g. shared boilerplate) store that paragraph ONCE
in `documents`, with each source's `chunk_map` independently pointing at
the shared row in the correct position. Proven: 74 duplicate-content
chunks in the real corpus correctly collapsed, and
`test_reconstruction_survives_shared_chunks` proves each source still
reconstructs its own full, correct text.

## Real bug this exact design fixed (disclosed, not hidden)

The donor's own commit message (`d855206`) states: "Rollback test caught
a real UNIQUE-collision bug (canonical chunk identity now decoupled to
`_canonical` owner + global sequence)." The chunk-ownership design
(`documents.source_id = "_canonical"`, true origin tracked in
`documents.metadata`) exists specifically to avoid a `UNIQUE(source_id,
chunk_index)` collision when re-chunking a source that shares content
with another. This mechanism is preserved exactly as recovered.
