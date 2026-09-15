#!/usr/bin/env python3
"""Mission section 27 negative control, run as its own fresh process (not
imported directly into the shared pytest process) so this package's
bare-named `schema`/`script` modules never collide with another
institution's own same-named modules (news_intelligence also ships a
`schema.py`) inside one shared Python process -- exactly the isolation
discipline every other F8/F6/F7 subprocess already uses.

Fixture-only, per this mission's own allowance for negative controls: an
evidence pack whose only real finding establishes NOTHING, and a script
that attempts to smuggle in a sensational, unbacked FACT claim. The
fact-check stage must remove it.
"""

import json
import sys
from pathlib import Path

YOUTUBE_ROOT = str(Path(__file__).resolve().parents[4] / "youtube_production")
if YOUTUBE_ROOT not in sys.path:
    sys.path.insert(0, YOUTUBE_ROOT)

from schema import EvidenceItem, EvidencePack, Script, ScriptSegment
from script import fact_check_script


def run():
    pack = EvidencePack(
        evidence_pack_id="fixture-pack",
        production_mission_id="fixture-mission",
        source_event_ref="fixture-event",
        nexus_synthesis_ref="fixture-synthesis",
        specialist_findings_refs=[],
        items=[
            EvidenceItem(
                evidence_id="fixture-mission:support:0",
                source_institution="specialist_synthesis",
                source_ref="fixture-synthesis",
                claim_text="UNKNOWN: no institution reported evidence establishing a material cross-domain effect",
                claim_class="UNVERIFIED",
            ),
        ],
        contradictions=[], stale_evidence=[], prohibited_extrapolations=[],
        created_at="2026-08-28T00:00:00+00:00",
    )
    script = Script(
        script_id="fixture-script",
        production_mission_id="fixture-mission",
        segments=[
            ScriptSegment(segment_id="intro", text="Here's the story.", segment_class="EDITORIAL_TRANSITION"),
            ScriptSegment(
                segment_id="sensational_claim",
                text="This stock is guaranteed to triple in value next month!",
                segment_class="FACT",
                claim_ids=["fabricated-claim-not-in-evidence-pack"],
            ),
        ],
        revision=1,
    )
    claim_ledger = [
        {
            "claim_id": "fabricated-claim-not-in-evidence-pack",
            "script_segment": "sensational_claim",
            "claim_text": "This stock is guaranteed to triple in value next month!",
            "claim_class": "FACT",
            "evidence_refs": [], "provenance_refs": [],
            "verification_status": "REJECTED",
            "uncertainty": "claim_id referenced in script has no matching EvidencePack item",
            "editorial_transform_status": "UNCHANGED_FROM_EVIDENCE",
        },
    ]

    results, revised_script = fact_check_script(script, claim_ledger, pack)

    result = {
        "pid": __import__("os").getpid(),
        "outcomes": [r.outcome for r in results],
        "actions_taken": [r.action_taken for r in results],
        "kept_segment_ids": [s.segment_id for s in revised_script.segments],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
