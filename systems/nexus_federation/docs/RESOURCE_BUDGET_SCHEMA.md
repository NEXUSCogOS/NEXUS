# RESOURCE BUDGET SCHEMA
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`budget/schema.py: ResourceBudget` — every dimension (`cpu_seconds,
memory_bytes, elapsed_seconds, local_storage_bytes,
external_storage_bytes, api_cost_usd, model_tokens`) is a REQUIRED,
non-negative, finite number, plus a required `basis: str` naming where the
bound came from (mirroring `Confidence.basis` in DAT.AI's own contract —
a bound with no stated origin is exactly the kind of unsupported claim
this estate refuses to accept elsewhere).

`UNBOUNDED_NOT_ALLOWED` is the literal rejection-reason string a
`pydantic.ValidationError` carries when any dimension is `None` — there is
no `Optional`/`None` spelling of "unlimited." This is structural: code
cannot construct a valid `ResourceBudget` by omitting a bound, the same
way DAT.AI's contract structurally blocks self-promotion to `OPERATIONAL`.
Zero IS a legal, meaningful bound (e.g. "no external storage permitted at
all"), distinct from an omitted/unbounded one.

`DEFAULT_ANALYSIS_ONLY_BUDGET` is the one concrete budget this federation
currently issues — conservative and explicitly justified (`basis` names
exactly why: the only delegation category issued this phase requests
analysis of already-supplied evidence, with zero external storage, API
cost, or model tokens).

`delegation/schema.py: DelegationProposal.resource_budget` is now a
REQUIRED `ResourceBudget` object (an F1 -> F2 change: it was previously an
`Optional[str]` free-text field) — every delegation this federation issues
now carries an explicit, evidenced, fully-bounded resource cap.

### Proven (`tests/unit/test_resource_budget.py`)

- `None` on any dimension raises, citing `UNBOUNDED_NOT_ALLOWED`.
- Negative values raise.
- Missing/empty `basis` raises.
- Extra fields are forbidden (`extra="forbid"`).
- Zero is accepted as a valid, distinct-from-unbounded value.

## TARGET

- Per-recipient-institution or per-capability budget policies (today:
  one single default budget for the one delegation category that exists).
- Actual ENFORCEMENT of the budget against real measured consumption
  (today: the budget is stated on the proposal; nothing yet compares a
  recipient's actual resource use against it, because no recipient is
  connected to measure).

## LIMITATIONS

- `ResourceBudget` states a CAP, not a guarantee of availability — nothing
  in this federation currently reserves or pre-allocates the resources a
  budget names.
- Real resource ACCOUNTING (what was actually consumed) remains a
  separate, F1-era module (`observability/resource_accounting.py`) not yet
  cross-checked against the budget a delegation carried — that
  enforcement loop is future work, not claimed here.
