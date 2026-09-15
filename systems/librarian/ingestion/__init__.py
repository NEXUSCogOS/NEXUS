"""Librarian ingestion pipeline — recovered from the librarian_rag donor
(see LIBRARIAN_DONOR_FORENSIC_REPORT.md)."""

from .pipeline import IngestionPipeline, IngestResult
from .discovery import discover, build_census, DiscoveredFile, CensusReport
from .normalize import normalize_text, chunk_text, Chunk

__all__ = [
    "IngestionPipeline",
    "IngestResult",
    "discover",
    "build_census",
    "DiscoveredFile",
    "CensusReport",
    "normalize_text",
    "chunk_text",
    "Chunk",
]
