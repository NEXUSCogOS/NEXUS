# Contributing to NEXUS

## Research and Engineering Contributions

NEXUS welcomes contributions that improve inspectability, reproducibility, evidence quality, experimental validity, software quality or independent review.

Contributions should preserve the distinction between implementation progress and scientific evidence.

## Before Proposing a Change

Review the relevant public documentation:

1. `README.md` — project orientation and current status;
2. `ARCHITECTURE.md` — authority, evidence and subsystem architecture;
3. `EXPERIMENTS.md` — canonical experimental programme;
4. `REPRODUCIBILITY.md` — reproduction requirements;
5. `INDEPENDENT_VERIFICATION.md` — assurance and independence boundary;
6. `SECURITY.md` — security scope and reporting.

## Experiment-State Changes

Do not change canonical experiment status or verdict merely to make documentation, implementation or tests appear complete.

Canonical experiment state is governed by `systems/librarian/experiments/registry.json` and the applicable Experimental Validation workflow.

## Evidence

Where a contribution makes a measurable claim, provide inspectable evidence appropriate to that claim.

Examples include tests, execution results, hashes, provenance records, benchmark outputs or reproducible procedures.

## Negative Results

Negative, null and contradictory results are legitimate contributions when they are methodologically relevant and supported by evidence.

Do not suppress an unfavourable result merely because it weakens an existing hypothesis.

## Security

Do not commit credentials, secrets or unnecessary personal information.

Security findings should follow `SECURITY.md`.

## Independent Verification

Reviewers claiming independence should disclose material involvement in the original implementation, protocol design, endpoint selection or evidence production.

Repository separation alone does not establish independence.

## Documentation

Documentation must distinguish architectural intent, implemented mechanisms and demonstrated properties.

Do not convert `BLOCKED / PENDING` experiments into successful claims through prose.

## Review Standard

A strong contribution should make it easier for another person to determine:

- what changed;
- why it changed;
- what authority permitted it;
- what evidence supports it;
- what remains uncertain;
- how it can be reproduced or challenged.
