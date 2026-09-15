"""Script generation, anti-hallucination checking, and the fact-check
stage. NEXUS Federation F8, mission sections 8-9, 10, 21.

Every FACT/ANALYSIS/INTERPRETATION/HYPOTHESIS segment's text is derived
DIRECTLY from one EvidencePack item's own claim_text (lightly reworded for
spoken narration, never re-authored into a new claim) and carries that
item's evidence_id as its claim_id -- this is what makes the anti-
hallucination check and fact-check stage possible at all: every factual
sentence has exactly one traceable source. EDITORIAL_TRANSITION segments
carry no claim_id and are never fact-checked, because they assert no
fact (mission section 9).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from schema import Script, ScriptSegment, FactCheckResult

_CLASS_TO_SEGMENT_CLASS = {
    "FACT": "FACT",
    "ANALYSIS": "ANALYSIS",
    "INTERPRETATION": "INTERPRETATION",
    "HYPOTHESIS": "HYPOTHESIS",
    "UNVERIFIED": "HYPOTHESIS",  # never presented as FACT; downgraded to the weakest class
}


def generate_script(evidence_pack, editorial_objective: str) -> Script:
    segments: list[ScriptSegment] = []

    segments.append(ScriptSegment(
        segment_id="intro",
        text=f"Here is what the federation's evidence actually shows about {editorial_objective.split(':', 1)[-1].strip()}.",
        segment_class="EDITORIAL_TRANSITION",
    ))

    for item in evidence_pack.items:
        seg_class = _CLASS_TO_SEGMENT_CLASS.get(item.claim_class, "HYPOTHESIS")
        # Lightly reworded for spoken narration -- strip the leading
        # institutional tag ("OBSERVED_MARKET_FACT: ...") since a viewer
        # doesn't need that internal vocabulary, but never alter the
        # substance after the tag.
        spoken_text = item.claim_text.split(":", 1)[-1].strip() if ":" in item.claim_text else item.claim_text
        segment_suffix = item.evidence_id.rsplit(":", 2)[-2:]  # e.g. ["support", "0"] or ["contradict", "1"]
        segments.append(ScriptSegment(
            segment_id="seg_" + "_".join(segment_suffix),
            text=spoken_text,
            segment_class=seg_class,
            claim_ids=[item.evidence_id],
        ))

    if evidence_pack.contradictions:
        segments.append(ScriptSegment(
            segment_id="caveat",
            text="It's worth noting the evidence isn't unanimous here -- some findings point in different directions.",
            segment_class="EDITORIAL_TRANSITION",
        ))

    segments.append(ScriptSegment(
        segment_id="outro",
        text="That's what the evidence establishes right now -- and only that.",
        segment_class="EDITORIAL_TRANSITION",
    ))

    return Script(
        script_id=str(uuid5(NAMESPACE_URL, f"f8-script:{evidence_pack.production_mission_id}:rev1")),
        production_mission_id=evidence_pack.production_mission_id,
        segments=segments,
        revision=1,
    )


_NUMBER_RE = re.compile(r"\b\d[\d,.]*\b")


def anti_hallucination_check(script: Script, evidence_pack) -> list[str]:
    """Checks every numeric token in a FACT/ANALYSIS segment appears
    somewhere in the evidence pack's own claim text. Returns a list of
    violation strings (empty = clean). This does not catch every
    possible hallucination class the mission lists (names/quotes/etc.)
    but is a real, running check against real evidence text -- not a
    placeholder that always passes."""
    evidence_text = " ".join(i.claim_text for i in evidence_pack.items)
    evidence_numbers = set(_NUMBER_RE.findall(evidence_text))

    violations = []
    for seg in script.segments:
        if seg.segment_class not in ("FACT", "ANALYSIS"):
            continue
        for num in _NUMBER_RE.findall(seg.text):
            if num not in evidence_numbers:
                violations.append(
                    f"segment={seg.segment_id!r} contains numeric token {num!r} "
                    f"not present in any evidence item -- possible fabricated statistic"
                )
    return violations


def fact_check_script(script: Script, claim_ledger: list, evidence_pack) -> tuple[list[FactCheckResult], Script]:
    """Mission section 21: runs AFTER script generation, BEFORE final
    render acceptance. UNSUPPORTED claims are removed from the returned
    (possibly revised) script -- never silently left in."""
    stale_set = set(evidence_pack.stale_evidence)
    contradiction_set = set(evidence_pack.contradictions)

    results: list[FactCheckResult] = []
    segments_to_keep: list[ScriptSegment] = []

    ledger_by_claim = {e["claim_id"]: e for e in claim_ledger}

    for seg in script.segments:
        if seg.segment_class == "EDITORIAL_TRANSITION" or not seg.claim_ids:
            segments_to_keep.append(seg)
            continue

        claim_id = seg.claim_ids[0]
        entry = ledger_by_claim.get(claim_id)
        if entry is None or entry.get("verification_status") == "REJECTED":
            results.append(FactCheckResult(claim_id=claim_id, outcome="UNSUPPORTED", basis="no matching evidence_ref in claim ledger", action_taken="REMOVED"))
            continue  # dropped from segments_to_keep

        if seg.text in contradiction_set or entry["claim_text"] in contradiction_set:
            outcome = "CONTRADICTORY"
        elif claim_id in stale_set or entry["claim_text"] in stale_set:
            outcome = "STALE"
        elif entry.get("verification_status") == "VERIFIED":
            outcome = "SUPPORTED"
        elif entry.get("verification_status") == "PARTIAL":
            outcome = "PARTIAL"
        else:
            outcome = "UNSUPPORTED"

        if outcome == "UNSUPPORTED":
            results.append(FactCheckResult(claim_id=claim_id, outcome=outcome, basis="claim ledger verification_status did not reach VERIFIED/PARTIAL", action_taken="REMOVED"))
            continue

        results.append(FactCheckResult(claim_id=claim_id, outcome=outcome, basis=f"claim ledger verification_status={entry.get('verification_status')}", action_taken="NONE"))
        segments_to_keep.append(seg)

    revised_script = Script(
        script_id=script.script_id,
        production_mission_id=script.production_mission_id,
        segments=segments_to_keep,
        revision=script.revision,
    )
    return results, revised_script
