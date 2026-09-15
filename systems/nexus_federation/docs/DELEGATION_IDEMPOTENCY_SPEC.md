# DELEGATION IDEMPOTENCY SPEC
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`delegation/idempotency.py: compute_idempotency_key(institution, cycle_id,
capability_name, category)` is a pure function: sha256 of
`f"{institution}|{cycle_id}|{capability_name}|{category}"`. It deliberately
excludes anything that varies for no semantic reason (`proposal_id` is a
random UUID; `created_at` is wall-clock time) — those must never be part
of an idempotency key, or every call would look "new."

`persistence/db.py: delegation_log.idempotency_key` carries a `UNIQUE`
SQL constraint. `FederationStore.append_delegation()` does `INSERT OR
IGNORE` keyed on it and returns whether a row was ACTUALLY inserted
(`cursor.rowcount == 1`) — the database itself is the enforcement
mechanism, not application-level convention.

`kernel.py: FederationKernel._process_relevance()` runs on BOTH the normal
accept path and the `DUPLICATE` replay path (a deliberate F2 change from
F1, where the duplicate path skipped relevance entirely) — this is what
makes "before delegation persistence" crash-recoverable: a report already
marked accepted, whose delegation never got created before a crash, still
gets a chance to produce it on a later duplicate replay, guarded by the
same idempotency key so it is never produced twice.

### Proven (`tests/unit/test_delegation_idempotency.py`)

| Requirement | Test |
|---|---|
| First processing -> 1 delegation | `test_first_processing_yields_one_delegation` |
| Duplicate report -> still 1 | `test_duplicate_report_still_one_delegation` |
| Restart + duplicate -> still 1 | `test_restart_plus_duplicate_still_one_delegation` |
| New, materially different finding -> new delegation allowed | `test_new_materially_different_finding_allows_new_delegation` |
| Crash before delegation persistence -> recovers to exactly 1 | `test_delegation_before_persistence_crash_recovers_to_exactly_one` |

Also covered end-to-end via the real subprocess restart test
(`tests/restart/test_subprocess_restart.py`): Process B re-ingests the
IDENTICAL payload Process A ingested, across a genuine OS process
boundary, and `total_delegations_in_store` remains exactly 1.

## TARGET

- Extend the idempotency key to cover a genuinely new relevance CATEGORY
  firing on the same cycle+capability (currently: yes, already covered —
  `category` is part of the key, so a second, different category on the
  same cycle+capability correctly produces a second, distinct delegation;
  this is intentional, not a gap).
- A durable `delegation_attempt_log` distinguishing "attempted and
  suppressed" from "attempted and succeeded" more explicitly than today's
  `KernelResult.delegations_suppressed_as_duplicate` transient count plus
  the `delegation_idempotency_suppression` observability event.

## LIMITATIONS

- The idempotency key does not include anything about the CONTENT of the
  delegation (objective text, evidence_refs) — two calls with the same
  (institution, cycle_id, capability_name, category) but different
  materiality/evidence would still collide on the same key and the second
  would be silently suppressed. This is intentional for this phase (the
  routing table only ever produces one shape of delegation per category
  today), but is a real constraint documented for F3: if a capability
  could trigger the same category twice in one cycle with materially
  different content, the key would need to widen.
