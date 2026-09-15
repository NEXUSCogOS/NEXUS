"""Metadata generation. NEXUS Federation F8, mission section 20: title,
description, chapter suggestions, tags, source notes, disclosure notes --
no false authority claims, no fabricated citations.
"""

from __future__ import annotations

from schema import VideoMetadata


def generate_metadata(*, script, evidence_pack, executive_conclusion_class: str) -> VideoMetadata:
    fact_segments = [s for s in script.segments if s.segment_class in ("FACT", "ANALYSIS")]
    title_source = fact_segments[0].text if fact_segments else script.segments[0].text if script.segments else "Production update"
    title = title_source[:90].rstrip() + ("..." if len(title_source) > 90 else "")

    description_lines = [
        "This video summarizes a real, evidence-derived analysis produced by "
        "the NEXUS federation's automated research pipeline.",
        "",
        f"Overall evidentiary conclusion class: {executive_conclusion_class}.",
        "",
        "Sources and disclosure:",
        f"- Evidence pack: {evidence_pack.evidence_pack_id}",
        f"- {len(evidence_pack.items)} underlying evidence item(s), each independently traceable.",
    ]
    if evidence_pack.contradictions:
        description_lines.append("- Some underlying findings were contradictory; both sides are disclosed in the video.")
    if evidence_pack.stale_evidence:
        description_lines.append("- Some evidence was flagged as stale relative to the analysis date.")
    description_lines += [
        "",
        "Disclosure: script, narration, and visuals for this video were generated "
        "by an automated production pipeline from the evidence above. No footage "
        "in this video is documentary/stock footage; all visuals are generated.",
    ]

    chapters = [f"00:00 {s.segment_id.replace('_', ' ').title()}" for s in script.segments]

    tags = ["automated analysis", "evidence-based", executive_conclusion_class.lower().replace("_", " ")]

    source_notes = [f"evidence_id={i.evidence_id} class={i.claim_class}" for i in evidence_pack.items]

    disclosure_notes = [
        "Script generated from a structured evidence pack, not free-form generation.",
        "Voice: local macOS text-to-speech (no cloud TTS, no voice cloning).",
        "Visuals: generated stills (Pillow), not stock or documentary footage.",
        "This video has NOT been published; production status is internal only.",
    ]

    return VideoMetadata(
        title=title,
        description="\n".join(description_lines),
        chapters=chapters,
        tags=tags,
        source_notes=source_notes,
        disclosure_notes=disclosure_notes,
    )
