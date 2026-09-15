# Post-Review Process

A reviewer decision does not directly mutate canonical experiment state.

## APPROVE

If an independent reviewer returns APPROVE:

1. verify reviewer identity and role;
2. inspect independence disclosure;
3. verify decision scope is global-10;
4. verify reviewed release/commit identity;
5. preserve the original reviewer artifact;
6. hash the reviewer artifact;
7. create the formal global-10 evidence record only through the governed gate-record workflow;
8. re-run canonical readiness evaluation;
9. expect 14/14 only if every gate validates;
10. expect `READY_ELIGIBLE` while the registry remains BLOCKED;
11. perform the separately governed registry transition;
12. re-evaluate readiness;
13. only `READY` may authorize experiment execution.

## REJECT

Preserve the rejection and keep EXP-002 blocked.

## REQUEST_MORE_EVIDENCE

Preserve the request and resolve only the requested deficiencies. Do not convert the request into PASS.

## CONFLICT

Register and preserve the conflict. Do not proceed until the applicable authority process resolves it.

## Invariant

Independent review evidence, gate validation, registry transition and experiment execution are separate state transitions.
