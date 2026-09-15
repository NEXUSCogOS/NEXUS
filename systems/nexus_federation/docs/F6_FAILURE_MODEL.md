# F6 FAILURE MODEL
**NEXUS Federation F6 — 2026-08-28**

Full test evidence in F6_FAILURE_TEST_REPORT.md; this document states
the model, not the run log.

## Specialist unavailable (mission section 21)

`synthesize()` accepts `librarian_report: Optional[dict]` and
`sentinel_report: Optional[dict]` — either may be `None`. When one is:

- The available institution's report is retained and fully ingested
  through the normal generic kernel path.
- `missing_institutions` explicitly lists the absent institution(s).
- `partial = True`.
- `executive_conclusion_class` is forced to `INSUFFICIENT_EVIDENCE`
  regardless of what the available institution reported — a synthesis
  is never drawn from half the intended evidence and presented as
  complete.
- `executive_conclusion` text explicitly says the conclusion is
  "withheld pending retry," not silently omitted.

This is a partial-degradation model, not a whole-federation failure: the
available institution's contribution is not discarded, and retrying
Process D later (once the missing institution's report exists) produces
a full, non-partial synthesis without re-running the available
institution's work.

## Contradictory results

See CROSS_INSTITUTION_CONTRADICTION_PROTOCOL.md. Not a "failure" in the
crash sense — a legitimate epistemic outcome that must be represented
(`CONTRADICTORY_EVIDENCE`), never suppressed.

## Duplicate / replay

See CROSS_DOMAIN_PROVENANCE_STANDARD.md's determinism note and
F6_REPRODUCIBILITY_PROTOCOL.md. A replayed trigger or a restarted
Process D must not create semantic duplicates; receipt-level logs
(`report_log`, `observability_event_log`) MAY grow on replay — that is
intentional audit-trail behavior, not a bug.

## What is explicitly NOT handled by this model

- A crash mid-Process-B or mid-Process-C (before that process persists
  its own report) is not distinguished from "that institution was never
  delegated to" — Process D simply sees no report_id for it and treats
  it as the missing-institution case. This is safe (no fabrication) but
  coarser than distinguishing "never started" from "started and died."
- No automatic retry scheduling exists — "permit retry" (mission section
  21) means the mechanism is safe to invoke again, not that anything
  invokes it automatically.
