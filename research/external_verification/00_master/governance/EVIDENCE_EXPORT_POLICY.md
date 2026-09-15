# EVA Evidence Export Policy

## Purpose

Define what NEXUS-EVA may expose to Experimental Validation.

## Export Eligibility

An evidence reference may be exported only when:

1. lifecycle_state = SEALED;
2. original evidence exists;
3. original evidence SHA-256 is recorded;
4. package SHA-256 is recorded;
5. verifier identity is recorded;
6. independence status is recorded;
7. conflict status is recorded;
8. exact claim IDs are recorded;
9. system version is recorded;
10. external verdict is preserved.

## Export Does Not Mean Acceptance

Export means:

"This evidence record is eligible to be considered."

It does not mean:

"This evidence satisfies an Experimental Validation gate."

## Prohibited Export Transformations

EVA may not transform:

FAIL → PASS
PARTIAL → PASS
INCONCLUSIVE → PASS
NOT_INDEPENDENT → INDEPENDENT
UNKNOWN → INDEPENDENT

## Original Evidence

Original externally supplied artifacts remain authoritative for what the
reviewer actually stated.

Machine-readable representations are derivative metadata.
