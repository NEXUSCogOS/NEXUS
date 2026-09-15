# NEXUS-EVA Verification Lifecycle

DRAFT
  ↓
PACKAGE_FROZEN
  ↓
DISPATCHED
  ↓
RECEIVED
  ↓
INTEGRITY_VERIFIED
  ↓
INDEPENDENCE_VERIFIED
  ↓
ADJUDICATED
  ↓
SEALED

## DRAFT
Package remains mutable.

## PACKAGE_FROZEN
Claims, protocol and package contents receive immutable version/hash identity.

## DISPATCHED
Exact frozen package is transmitted to a registered external verifier.

## RECEIVED
Returned evidence is preserved in original form.

Receipt does not imply validation.

## INTEGRITY_VERIFIED
Required cryptographic/provenance checks pass.

This verifies artifact integrity, not scientific truth.

## INDEPENDENCE_VERIFIED
Reviewer independence and conflict information is evaluated.

Permitted classifications:

INDEPENDENT
DECLARED_CONFLICT
NOT_INDEPENDENT
UNKNOWN

## ADJUDICATED
External findings are mapped to the exact claims addressed.

Original verdict cannot be altered.

## SEALED
Original evidence, metadata, adjudication and integrity records become a
provenance-bound evidence record.

SEALED does not mean PASS.

A sealed verdict may be:

PASS
PARTIAL
FAIL
INCONCLUSIVE
