# ES-PUBLIC-GITHUB-INTEGRATION-001

## Objective
Install a governed publication boundary between private canonical NEXUS/Engineering Studio evidence and curated public GitHub repositories.

## Invariants
1. Canonical evidence remains authoritative and immutable under this subsystem.
2. No wholesale NEXUS export.
3. No public claim may exceed its canonical validation state.
4. Negative evidence relevant to a claim is preserved.
5. Publication candidates are isolated copies.
6. Secret/PII/private-path/IP review is mandatory.
7. Git history must be separately reviewed before publishing history.
8. Human approval is mandatory before external publication.
9. Failed mandatory gates block release.
10. Career/publicity goals may motivate new experiments but never determine results.

## Flow
CANONICAL ARTIFACT
→ ALLOW-LIST
→ CLAIM/EVIDENCE RESOLUTION
→ DISCLOSURE CHECK
→ ISOLATED COPY
→ SANITISATION
→ SECRET/PII/PATH SCAN
→ TESTS
→ REPRODUCIBILITY CHECK
→ RELEASE MANIFEST
→ HUMAN REVIEW
→ PUBLICATION

No reverse mutation path is permitted.

## Planned public repositories
1. `agentic-engineering-benchmark` — benchmark and baseline methodology; publish first.
2. `engineering-studio` — sanitised research implementation; never wholesale private export.
3. `ai-evidence-provenance` — claim/evidence/provenance framework.
4. `cumulative-agent-memory` — comparative memory experiments.

## Required release gates
G01 source explicitly allow-listed
G02 evidence references resolve
G03 claim wording calibrated
G04 disclosure permits publication
G05 secret scan passes
G06 PII/private-data review passes
G07 machine-specific path review passes
G08 tests pass
G09 reproduction instructions exist
G10 result provenance present
G11 limitations documented
G12 explicit human approval

G12 is never auto-approved.

## Claim states
UNVERIFIED
PARTIALLY_SUPPORTED
SUPPORTED
VERIFIED
REPRODUCED
INDEPENDENTLY_REPRODUCED
CONTRADICTED
SUPERSEDED
RETRACTED
