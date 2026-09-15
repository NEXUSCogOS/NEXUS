"""Stage 5-6: deterministic normalization and chunking.

RECOVERED unchanged from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/ingestion/normalize.py
(commit d855206). No logic changes; part of the 22/22 test baseline.

Both functions are pure and deterministic: identical input bytes always yield
identical normalized text and identical chunk boundaries. This is what makes
re-ingestion idempotent and content hashes stable across runs.
"""

from __future__ import annotations

from dataclasses import dataclass

# Target chunk size in characters. Paragraphs accumulate until adding the next
# would exceed this; oversized single paragraphs become their own chunk.
CHUNK_TARGET_CHARS = 1200
CHUNK_MAX_CHARS = 2000


def normalize_text(text: str) -> str:
    """Deterministic normalization.

    - CRLF/CR -> LF
    - strip trailing whitespace on each line
    - collapse 3+ consecutive blank lines to exactly 2
    - strip leading/trailing whitespace of the whole document
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]

    collapsed: list[str] = []
    blank_run = 0
    for ln in lines:
        if ln == "":
            blank_run += 1
            if blank_run <= 2:
                collapsed.append(ln)
        else:
            blank_run = 0
            collapsed.append(ln)

    return "\n".join(collapsed).strip()


@dataclass
class Chunk:
    index: int
    text: str


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines into paragraph units, preserving order."""
    paras: list[str] = []
    buf: list[str] = []
    for ln in text.split("\n"):
        if ln.strip() == "":
            if buf:
                paras.append("\n".join(buf))
                buf = []
        else:
            buf.append(ln)
    if buf:
        paras.append("\n".join(buf))
    return paras


def chunk_text(normalized: str) -> list[Chunk]:
    """Deterministic paragraph-accumulation chunking.

    Paragraphs are packed in order until the target size; a paragraph larger
    than CHUNK_MAX_CHARS is hard-split on character boundaries so no chunk is
    unbounded. Ordering is strictly preserved (chunk 0, 1, 2, ...).
    """
    if not normalized.strip():
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

    for para in _split_paragraphs(normalized):
        if len(para) > CHUNK_MAX_CHARS:
            flush()
            for i in range(0, len(para), CHUNK_MAX_CHARS):
                chunks.append(para[i : i + CHUNK_MAX_CHARS])
            continue

        addition = len(para) + (2 if current else 0)
        if current_len + addition > CHUNK_TARGET_CHARS and current:
            flush()
        current.append(para)
        current_len += addition

    flush()
    return [Chunk(index=i, text=c) for i, c in enumerate(chunks)]
