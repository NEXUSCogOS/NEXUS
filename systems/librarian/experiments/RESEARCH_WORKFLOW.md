# NEXUS Experimental Validation and Evidence Workflow

`registry.json` is the sole canonical experiment record. Librarian and Research
Assistant views may contain IDs and links only; they must not copy experiment
fields or results.

## State transition

`PREREGISTERED -> BLOCKED -> READY -> RUNNING -> COMPLETED`

Any provenance failure, unverifiable datum, leakage, protocol mutation, or
stability regression transitions the record to `INVALIDATED` or back to
`BLOCKED`. Nothing may transition to `READY` until every global and
experiment-specific stability gate has an evidence artifact and independent
reviewer approval. This registry was created with every experiment `BLOCKED`;
no experiment was initiated.

## Evidence search for every hypothesis

1. Freeze the hypothesis, predictions, null outcome, thresholds, protocol,
   dataset cutoff and search strategy before observing experimental results.
2. Search primary literature and authoritative datasets using concept synonyms,
   exact mechanisms, competing theories, failure modes and explicit
   disconfirmation terms. Do not search only for confirming language.
3. Record each candidate source in the Librarian provenance store before using
   it. Required fields are source/author/institution, acquisition time,
   canonical identifier, licence, local content hash, transformation history,
   reviewer, verification time and lifecycle status.
4. For each source-hypothesis relationship, record exactly one of
   `CONFIRMS`, `CONTRADICTS`, `QUALIFIES`, `DISPROVES`, `INSUFFICIENT`, or
   `UNVERIFIABLE`; include passage offsets, method/population/context,
   limitations and reviewer confidence. Keyword matches alone are leads, not
   evidence classifications.
5. Resolve duplicate sources by canonical identifier and content hash. Preserve
   every acquisition/transformation event; never overwrite the audit trail.
6. Synthesize confirming and contradictory evidence separately, then compare
   study design, population, measurement, effect size, uncertainty, recency and
   independence. Absence of contradiction is not confirmation.
7. Update only `external_literature_cross_check_status` and
   `contradictory_findings` before execution. Do not rewrite predictions or
   thresholds after results are visible; version any deviation and invalidate
   the original confirmatory interpretation when required.

## Execution and result handling

- The runner must deny execution unless registry/schema validation passes and
  every required gate artifact resolves and verifies.
- Inputs are immutable snapshots. Record code commit, dependency lock, config,
  random seeds, host/runtime, dataset hashes and the complete command/runner
  identity.
- Preserve raw outputs before analysis. Analysis produces new artifacts and
  never modifies raw evidence.
- Compare results with the preregistered prediction and null using the frozen
  decision rule. Report effect sizes and uncertainty, not only pass/fail.
- Data accuracy checks include schema/unit validation, range and consistency
  checks, duplicate/orphan scans, provenance coverage, source reconciliation and
  independent recomputation of primary metrics.
- A result cannot be `SUPPORTED` until independent replication succeeds.
  Failed or partial replication is recorded as contradictory evidence and may
  produce `QUALIFIED`, `INCONCLUSIVE`, `REJECTED`, or `INVALID`.

## Audit rule

Append one event to `audit/registry_events.jsonl` for every registry change,
including actor, timestamp, reason, prior/new registry hash and changed IDs.
Never edit or delete earlier events. Missing provenance or unverifiable data
must fail closed and be quarantined, never silently repaired or promoted.
