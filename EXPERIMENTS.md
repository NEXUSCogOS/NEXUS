# NEXUS Canonical Experiments

## Purpose

This document provides a human-readable view of the canonical NEXUS experimental programme.

It is **not** an independent experiment registry.

The authoritative experiment state remains:

`systems/librarian/experiments/registry.json`

Experimental readiness requirements remain defined by:

`systems/engineering_studio/experimental_validation/config/experiment_requirements.json`

If this document conflicts with either canonical source, the canonical machine-readable source governs.

At this release point, all six canonical experiments remain **BLOCKED / PENDING**.

The central NEXUS scientific hypothesis is **not yet experimentally validated**, and independent replication is not claimed.

---

## Experimental State Model

The canonical research workflow defines:

```text
PREREGISTERED
    ↓
BLOCKED
    ↓
READY
    ↓
RUNNING
    ↓
COMPLETED
```

Transition to `READY` requires satisfaction of all applicable global and experiment-specific readiness gates, including the required review authority.

A completed internal experiment is not automatically a supported scientific claim.

Under the canonical workflow, a result cannot become `SUPPORTED` until independent replication succeeds.

Failed or partial replication remains part of the evidence record.

---

## Current Experiment Matrix

| Experiment | Result status | Final verdict | Required gates |
|---|---|---|---:|
| `NEXUS-EXP-001` | **BLOCKED** | **PENDING** | 14 |
| `NEXUS-EXP-002` | **BLOCKED** | **PENDING** | 14 |
| `NEXUS-EXP-003` | **BLOCKED** | **PENDING** | 14 |
| `NEXUS-EXP-004` | **BLOCKED** | **PENDING** | 14 |
| `NEXUS-EXP-005` | **BLOCKED** | **PENDING** | 15 |
| `NEXUS-EXP-006` | **BLOCKED** | **PENDING** | 14 |

---

## Canonical Experiment Records

### NEXUS-EXP-001

**Canonical result status:** `BLOCKED`

**Canonical final verdict:** `PENDING`

#### Controls

- unsupported negative-control missions
- known-answer positive-control missions
- malformed-source provenance control

#### Replication Plan

Independent operator repeats from the frozen bundle in a clean environment and compares content hashes plus scored endpoints.

#### Additional Canonical Metadata

**acceptance_rejection_thresholds:**

- **accept:** all reports valid; source resolution=100%; fabrication=0; unsupported outcome accuracy=100%
- **reject:** any fabricated/unresolvable citation or silent unsupported-to-supported conversion
- **otherwise:** INCONCLUSIVE and investigate transport-only failures

- **claim_under_test:** A bounded NEXUS research mission reaches Librarian, retrieves real corpus evidence, synthesises it, and returns a schema-valid InstitutionalReport with traceable citations and limitations.
**contamination_leakage_checks:**

- held-out questions absent from prompts, fixtures and retrieval labels
- corpus snapshot created before result scoring
- no production database writes
- negative controls searched for accidental keyword overlap

- **contradictory_findings:** - 2026-08-28 evidence states the full federation E2E test was deferred despite component-level success.
**dataset_source_requirements:**

- versioned mission fixture set
- immutable snapshot of the registered academic corpus
- separate held-out unsupported questions

**dependent_variables:**

- report contract validity
- source resolution rate
- fabrication count
- correct unsupported-outcome rate
- end-to-end completion rate

**evidence_artifacts:**

- mission fixtures
- corpus manifest
- InstitutionalReport outputs
- schema-validation report
- source-resolution report
- run log and environment manifest

**execution_prerequisites_stability_gates:**

- federation E2E path commissioned
- research domain READY
- no fallback placeholder mode
- corpus and event log restore tested

- **external_literature_cross_check_status:** PENDING
- **falsifiable_hypothesis:** For a frozen set of supported and unsupported research missions, every accepted mission produces exactly one valid report whose claims resolve only to registered sources, while unsupported missions produce an explicit evidence-gap outcome and no fabricated support.
**independent_variables:**

- mission support condition: supported vs unsupported
- federation invocation path

- **null_alternative_outcome:** At least one mission fails federation transport, emits an invalid report, cites an unregistered source, fabricates support, or silently converts an unsupported question into a supported claim.
**pre_registered_protocol:**

- freeze mission fixtures and corpus snapshot
- start only after all global gates and experiment gates pass
- invoke the public federation contract once per fixture
- validate report schema and resolve every evidence/provenance reference
- score outcomes with the frozen analysis script
- retain stdout, stderr, reports and hashes

- **predicted_result:** 100% contract-valid reports; 100% cited-source resolution; zero fabricated citations; unsupported controls labelled as gaps or insufficient evidence.
**provenance_requirements:**

- source manifest identifier
- content SHA-256
- acquisition timestamp
- licence
- transformation/event chain
- code commit and environment lock

- **statistical_reproducibility_criteria:** Run at least 30 missions across at least 10 supported and 10 unsupported questions; repeat the full set on three clean runs; Wilson 95% lower bound for critical correctness proportions must be >=0.95.
- **subsystem_layer:** NEXUS federation -> Librarian end-to-end research pipeline

#### Readiness Gates

**Required gate count:** 14

- `global-01` — canonical code, configuration, dataset and database authority recorded
- `global-02` — required services healthy for the preregistered observation window
- `global-03` — clean-environment build or environment lock reproduced
- `global-04` — research data physically or logically isolated from production writers
- `global-05` — backup integrity verified and at least one restore rehearsal passed
- `global-06` — monitoring detects a deliberately injected non-destructive failure
- `global-07` — dataset snapshots are immutable, hashed, licensed and provenance-complete
- `global-08` — secrets and live financial operations are excluded from experiment scope
- `global-09` — protocol, analysis code, thresholds and stopping rules are frozen
- `global-10` — independent reviewer signs the readiness record
- `NEXUS-EXP-001-01` — federation E2E path commissioned
- `NEXUS-EXP-001-02` — research domain READY
- `NEXUS-EXP-001-03` — no fallback placeholder mode
- `NEXUS-EXP-001-04` — corpus and event log restore tested

#### Current Interpretation

`NEXUS-EXP-001` remains **BLOCKED / PENDING** according to the canonical experiment registry.

Implementation, test coverage, gate machinery or architectural completeness must not be substituted for a different canonical experiment state.

---

### NEXUS-EXP-002

**Canonical result status:** `BLOCKED`

**Canonical final verdict:** `PENDING`

#### Controls

- gold valid records
- one-defect-at-a-time negative fixtures
- tampered-content hash controls
- unresolvable identifier controls

#### Replication Plan

Second implementation or independent reviewer regenerates fixtures from the defect specification and repeats against a clean store.

#### Additional Canonical Metadata

**acceptance_rejection_thresholds:**

- **accept:** sensitivity=1.00; specificity=1.00; invalid retrievability=0; complete audit events=100%
- **reject:** any false acceptance or invalid record retrievable as evidence
- **otherwise:** INCONCLUSIVE only for infrastructure failure before fixture evaluation

- **claim_under_test:** Librarian fails closed when a source, citation, transformation, or dataset lacks verifiable provenance.
**contamination_leakage_checks:**

- isolated temporary database
- unique fixture identifiers
- verify no fixture IDs exist in production corpus before or after
- hash all fixtures

**dataset_source_requirements:**

- synthetic non-sensitive fixtures
- frozen copies of representative valid source metadata
- no live corpus mutation during dry validation

**dependent_variables:**

- accept/reject decision
- quarantine reason accuracy
- retrievability after rejection
- audit-event completeness

**evidence_artifacts:**

- defect matrix
- fixture hashes
- validator output
- quarantine records
- retrieval-negative proof
- audit event export

**execution_prerequisites_stability_gates:**

- provenance schema frozen
- quarantine path writable and auditable
- restore rehearsal passed
- test store demonstrably isolated

- **external_literature_cross_check_status:** PENDING
- **falsifiable_hypothesis:** Complete records are accepted, while every fixture missing a required provenance element or containing a hash/identifier mismatch is rejected or quarantined without becoming citable evidence.
**independent_variables:**

- provenance defect type
- ingestion channel
- source format

- **null_alternative_outcome:** Any provenance-deficient record is accepted, indexed, retrieved as evidence, or silently repaired without an auditable event.
**pre_registered_protocol:**

- freeze defect matrix
- run validation in an isolated temporary store
- attempt ingestion
- attempt retrieval only after decision
- compare actual against expected decision
- verify append-only audit events

- **predicted_result:** 100% valid fixtures accepted; 100% incomplete, mismatched, or unverifiable fixtures rejected/quarantined; zero invalid records retrievable as evidence.
**provenance_requirements:**

- fixture generator version
- expected decision per fixture
- SHA-256 before and after ingestion
- validator version
- reviewer identity

- **statistical_reproducibility_criteria:** At least 5 fixtures per required provenance field and ingestion channel; three deterministic repetitions; identical decision vector and audit-event semantics across runs.
- **subsystem_layer:** Librarian academic corpus provenance and citation control

#### Readiness Gates

**Required gate count:** 14

- `global-01` — canonical code, configuration, dataset and database authority recorded
- `global-02` — required services healthy for the preregistered observation window
- `global-03` — clean-environment build or environment lock reproduced
- `global-04` — research data physically or logically isolated from production writers
- `global-05` — backup integrity verified and at least one restore rehearsal passed
- `global-06` — monitoring detects a deliberately injected non-destructive failure
- `global-07` — dataset snapshots are immutable, hashed, licensed and provenance-complete
- `global-08` — secrets and live financial operations are excluded from experiment scope
- `global-09` — protocol, analysis code, thresholds and stopping rules are frozen
- `global-10` — independent reviewer signs the readiness record
- `NEXUS-EXP-002-01` — provenance schema frozen
- `NEXUS-EXP-002-02` — quarantine path writable and auditable
- `NEXUS-EXP-002-03` — restore rehearsal passed
- `NEXUS-EXP-002-04` — test store demonstrably isolated

#### Current Interpretation

`NEXUS-EXP-002` remains **BLOCKED / PENDING** according to the canonical experiment registry.

Implementation, test coverage, gate machinery or architectural completeness must not be substituted for a different canonical experiment state.

---

### NEXUS-EXP-003

**Canonical result status:** `BLOCKED`

**Canonical final verdict:** `PENDING`

#### Controls

- frozen current lexical baseline
- random-ranking negative control
- exact-title positive control

#### Replication Plan

A second reviewer reruns the sealed benchmark; a later replication uses a newly sampled question set and corpus snapshot.

#### Additional Canonical Metadata

**acceptance_rejection_thresholds:**

- **accept:** 95% CI lower bound Recall@5>=0.90 and point Precision@5>=0.60 and MRR>=0.80
- **reject:** Recall@5<0.90 or confirmed leakage
- **otherwise:** QUALIFIED or INCONCLUSIVE by preregistered decision table

- **claim_under_test:** The academic retrieval layer achieves reliable relevance performance beyond the existing small lexical benchmark and generalises to held-out questions.
**contamination_leakage_checks:**

- question text hash search across source and test fixtures
- label access audit
- duplicate/near-duplicate question detection
- corpus cutoff date
- no tuning on held-out errors

- **contradictory_findings:** - The existing five-question benchmark reports 100% Recall@5 but only 40-80% Precision@5 and is too small to establish generalisation.
**dataset_source_requirements:**

- at least 100 held-out questions across represented domains
- dual independent relevance labels
- adjudicated disagreements
- immutable corpus snapshot

**dependent_variables:**

- Recall@5
- Precision@5
- MRR
- zero-result rate
- latency

**evidence_artifacts:**

- benchmark manifest
- annotation and adjudication logs
- ranked retrieval outputs
- metric report with CIs
- leakage audit

**execution_prerequisites_stability_gates:**

- benchmark labels complete
- corpus snapshot immutable
- retrieval configuration frozen
- independent adjudicator assigned

- **external_literature_cross_check_status:** PENDING
- **falsifiable_hypothesis:** On an independently labelled, preregistered held-out benchmark, Recall@5 remains >=0.90 and Precision@5 >=0.60 without train/test or corpus/label leakage.
**independent_variables:**

- research domain
- question difficulty
- query formulation
- retrieval configuration

- **null_alternative_outcome:** Any primary metric falls below its threshold, confidence bounds are too wide, or performance depends on leaked labels/queries.
**pre_registered_protocol:**

- freeze benchmark before tuning
- seal held-out labels from implementers
- run baseline and candidate on identical snapshot
- compute per-domain and aggregate metrics
- apply bootstrap confidence intervals
- publish all failed queries

- **predicted_result:** Recall@5 >=0.90, Precision@5 >=0.60, MRR >=0.80, with stable results across clean repeats.
**provenance_requirements:**

- question and label authorship
- label timestamps
- adjudication log
- corpus/version hashes
- retriever configuration and code commit

- **statistical_reproducibility_criteria:** Paired bootstrap with >=10,000 resamples; report 95% CIs and domain strata; three clean deterministic repetitions; seed and tie-breaking fixed.
- **subsystem_layer:** Librarian information retrieval

#### Readiness Gates

**Required gate count:** 14

- `global-01` — canonical code, configuration, dataset and database authority recorded
- `global-02` — required services healthy for the preregistered observation window
- `global-03` — clean-environment build or environment lock reproduced
- `global-04` — research data physically or logically isolated from production writers
- `global-05` — backup integrity verified and at least one restore rehearsal passed
- `global-06` — monitoring detects a deliberately injected non-destructive failure
- `global-07` — dataset snapshots are immutable, hashed, licensed and provenance-complete
- `global-08` — secrets and live financial operations are excluded from experiment scope
- `global-09` — protocol, analysis code, thresholds and stopping rules are frozen
- `global-10` — independent reviewer signs the readiness record
- `NEXUS-EXP-003-01` — benchmark labels complete
- `NEXUS-EXP-003-02` — corpus snapshot immutable
- `NEXUS-EXP-003-03` — retrieval configuration frozen
- `NEXUS-EXP-003-04` — independent adjudicator assigned

#### Current Interpretation

`NEXUS-EXP-003` remains **BLOCKED / PENDING** according to the canonical experiment registry.

Implementation, test coverage, gate machinery or architectural completeness must not be substituted for a different canonical experiment state.

---

### NEXUS-EXP-004

**Canonical result status:** `BLOCKED`

**Canonical final verdict:** `PENDING`

#### Controls

- current keyword-marker heuristic
- label-shuffled negative control
- clear entailment/contradiction anchor cases
- insufficient-evidence cases

#### Replication Plan

Independent annotators build a second held-out set; replication runner receives only the frozen protocol and artifact bundle.

#### Additional Canonical Metadata

**acceptance_rejection_thresholds:**

- **accept:** macro-F1>=0.80; contradiction recall>=0.90; entailment precision>=0.95; unsupported overclaim rate<=0.02
- **reject:** contradiction recall<0.90, entailment precision<0.95, confirmed leakage, or any fabricated citation
- **otherwise:** QUALIFIED or INCONCLUSIVE

- **claim_under_test:** Research Assistant can classify evidence as confirming, contradicting, qualifying, or disproving a hypothesis using source-grounded reasoning rather than keyword polarity alone.
**contamination_leakage_checks:**

- sealed test split
- near-duplicate source and claim detection
- prompt and corpus scan for labels
- chronological holdout
- no manual correction before scoring

- **contradictory_findings:** - Current synthesis evidence explicitly describes support/contradiction classification as a keyword-marker heuristic, not semantic entailment.
**dataset_source_requirements:**

- blinded expert-labelled claim-evidence pairs
- balanced four-way relationship classes plus insufficient evidence
- primary-source text with stable identifiers

**dependent_variables:**

- macro-F1
- contradiction recall
- citation entailment precision
- abstention accuracy
- calibration error

**evidence_artifacts:**

- label guide
- adjudicated dataset
- predictions
- confusion matrix
- calibration plot
- citation entailment audit
- error analysis

**execution_prerequisites_stability_gates:**

- Research Assistant interface explicitly commissioned
- classification ontology frozen
- citation passage storage operational
- expert adjudicators assigned

- **external_literature_cross_check_status:** PENDING
- **falsifiable_hypothesis:** Against a blinded expert-labelled claim-evidence set, the system reaches macro-F1 >=0.80, contradiction recall >=0.90, and citation entailment precision >=0.95, while abstaining on insufficient evidence.
**independent_variables:**

- evidence relationship class
- domain
- source quality
- claim complexity

- **null_alternative_outcome:** Performance is at or below the baseline, contradiction recall is below threshold, citations do not entail classifications, or unsupported evidence is overclaimed.
**pre_registered_protocol:**

- freeze ontology and labelling guide
- double-annotate and adjudicate
- seal test split
- run heuristic baseline and candidate once
- score primary and safety endpoints
- manually audit every high-confidence error

- **predicted_result:** All primary thresholds met; every classification links to exact source passages and provenance records; uncertainty is calibrated.
**provenance_requirements:**

- source identifiers and hashes
- passage offsets
- annotator identities and conflicts
- adjudication log
- model/prompt/config version

- **statistical_reproducibility_criteria:** At least 100 adjudicated examples per relationship class; bootstrap 95% CIs; inter-annotator agreement reported; independent repeat on a second-domain sample.
- **subsystem_layer:** Research Assistant evidence synthesis and contradiction detection

#### Readiness Gates

**Required gate count:** 14

- `global-01` — canonical code, configuration, dataset and database authority recorded
- `global-02` — required services healthy for the preregistered observation window
- `global-03` — clean-environment build or environment lock reproduced
- `global-04` — research data physically or logically isolated from production writers
- `global-05` — backup integrity verified and at least one restore rehearsal passed
- `global-06` — monitoring detects a deliberately injected non-destructive failure
- `global-07` — dataset snapshots are immutable, hashed, licensed and provenance-complete
- `global-08` — secrets and live financial operations are excluded from experiment scope
- `global-09` — protocol, analysis code, thresholds and stopping rules are frozen
- `global-10` — independent reviewer signs the readiness record
- `NEXUS-EXP-004-01` — Research Assistant interface explicitly commissioned
- `NEXUS-EXP-004-02` — classification ontology frozen
- `NEXUS-EXP-004-03` — citation passage storage operational
- `NEXUS-EXP-004-04` — expert adjudicators assigned

#### Current Interpretation

`NEXUS-EXP-004` remains **BLOCKED / PENDING** according to the canonical experiment registry.

Implementation, test coverage, gate machinery or architectural completeness must not be substituted for a different canonical experiment state.

---

### NEXUS-EXP-005

**Canonical result status:** `BLOCKED`

**Canonical final verdict:** `PENDING`

#### Controls

- read-only copied snapshot
- known-tampered snapshot
- known-missing-provenance rows
- production-path access sentinel

#### Replication Plan

Independent process rebuilds the snapshot from the upstream manifest and must reproduce the same row counts, schema and hashes.

#### Additional Canonical Metadata

**acceptance_rejection_thresholds:**

- **accept:** hash drift=0; provenance coverage=100%; writer overlap=0; unit ambiguity=0
- **reject:** any unexplained drift, writer overlap, missing provenance or ambiguous unit
- **otherwise:** INVALID until provenance is repaired and a new snapshot preregistered

- **claim_under_test:** Experimental results can be generated from immutable, provenance-complete research datasets without contamination from live or production writers.
**contamination_leakage_checks:**

- open-handle census
- WAL and journal isolation
- live-vs-historical source flag validation
- timestamp boundary checks
- duplicate and orphan scan

- **contradictory_findings:** - Platform readiness review reports research and production sharing storage, untested restores, missing provenance flags, and unit/scale mismatches.
**dataset_source_requirements:**

- read-only experiment-specific snapshot
- explicit source/type/unit fields
- row or partition hashes
- documented inclusion/exclusion manifest

**dependent_variables:**

- snapshot hash stability
- provenance coverage
- writer overlap count
- unit/schema validation failures

**evidence_artifacts:**

- snapshot manifest
- hash ledger
- writer census
- provenance coverage report
- unit validation report
- quarantine log

**execution_prerequisites_stability_gates:**

- tested restore
- research/production physical or logical separation
- writer identities known
- disk headroom safe
- schema and unit conflicts resolved

- **external_literature_cross_check_status:** NOT_APPLICABLE_INTERNAL_INTEGRITY
- **falsifiable_hypothesis:** Repeated reads of the sealed research snapshot remain hash-identical; all rows resolve to a source and transformation chain; no production writer accesses the experimental store during execution.
**independent_variables:**

- dataset snapshot
- reader process
- execution time

- **null_alternative_outcome:** Any unexplained hash drift, missing provenance, mixed live/historical data, shared WAL/writer activity, unit ambiguity, or non-repeatable input selection.
**pre_registered_protocol:**

- create snapshot only after backup/restore gate
- record open-file handles and writers
- validate schema, units and provenance
- hash before and after each read
- run analysis against snapshot only
- quarantine on any mismatch

- **predicted_result:** Zero snapshot drift, 100% row-level provenance, zero production-writer overlap, and identical analysis input hashes across repetitions.
**provenance_requirements:**

- upstream acquisition record
- transform chain
- schema version
- unit metadata
- snapshot creator and timestamp
- content hashes

- **statistical_reproducibility_criteria:** Deterministic integrity checks across at least three time-separated reads and two independent processes; exact hash equality required.
- **subsystem_layer:** NEXUS research data integrity and production isolation

#### Readiness Gates

**Required gate count:** 15

- `global-01` — canonical code, configuration, dataset and database authority recorded
- `global-02` — required services healthy for the preregistered observation window
- `global-03` — clean-environment build or environment lock reproduced
- `global-04` — research data physically or logically isolated from production writers
- `global-05` — backup integrity verified and at least one restore rehearsal passed
- `global-06` — monitoring detects a deliberately injected non-destructive failure
- `global-07` — dataset snapshots are immutable, hashed, licensed and provenance-complete
- `global-08` — secrets and live financial operations are excluded from experiment scope
- `global-09` — protocol, analysis code, thresholds and stopping rules are frozen
- `global-10` — independent reviewer signs the readiness record
- `NEXUS-EXP-005-01` — tested restore
- `NEXUS-EXP-005-02` — research/production physical or logical separation
- `NEXUS-EXP-005-03` — writer identities known
- `NEXUS-EXP-005-04` — disk headroom safe
- `NEXUS-EXP-005-05` — schema and unit conflicts resolved

#### Current Interpretation

`NEXUS-EXP-005` remains **BLOCKED / PENDING** according to the canonical experiment registry.

Implementation, test coverage, gate machinery or architectural completeness must not be substituted for a different canonical experiment state.

---

### NEXUS-EXP-006

**Canonical result status:** `BLOCKED`

**Canonical final verdict:** `PENDING`

#### Controls

- known-complete reference bundle
- intentionally incomplete bundle must fail closed

#### Replication Plan

This record defines the mandatory replication phase for NEXUS-EXP-001 through NEXUS-EXP-005 and future experiments.

#### Additional Canonical Metadata

**acceptance_rejection_thresholds:**

- **accept:** all input hashes equal; undocumented steps=0; verdict agreement=100%; deterministic metrics exact and stochastic metrics within preregistered CI/tolerance
- **reject:** missing provenance, input mismatch, undocumented intervention or verdict disagreement
- **otherwise:** INCONCLUSIVE for infrastructure failure unrelated to the bundle

- **claim_under_test:** A completed NEXUS experiment can be independently reproduced from its evidence bundle and preregistration without undocumented operator knowledge.
**contamination_leakage_checks:**

- replicator has no access to mutable original working data
- result blinding until replication verdict
- bundle hash verified before use
- fresh output namespace

- **contradictory_findings:** - Current readiness evidence reports no tested restore and non-reproducible runtime/dependency conditions.
**dataset_source_requirements:**

- immutable input snapshot
- machine-readable manifest
- environment lock
- analysis code and seeds

**dependent_variables:**

- reconstruction success
- input hash agreement
- metric delta
- verdict agreement
- undocumented-step count

**evidence_artifacts:**

- sealed replication bundle
- environment reconstruction log
- replication outputs
- metric comparison
- deviation log
- signed replication verdict

**execution_prerequisites_stability_gates:**

- original experiment completed validly
- evidence bundle sealed
- replicator independent
- clean environment available

- **external_literature_cross_check_status:** PENDING_METHODS_REVIEW
- **falsifiable_hypothesis:** A reviewer who did not design or run the original experiment can reconstruct the environment, verify inputs, rerun the analysis, and reach the same preregistered verdict within the specified tolerance.
**independent_variables:**

- operator
- clean environment
- execution host

- **null_alternative_outcome:** Replication requires undocumented steps, cannot resolve provenance, uses different inputs, exceeds metric tolerance, or reaches a different verdict.
**pre_registered_protocol:**

- seal original bundle before results are shared with replicator
- replicator validates provenance first
- reconstruct clean environment
- run frozen analysis
- compare metrics and verdict
- record every deviation and failed step

- **predicted_result:** Environment reconstruction succeeds; input hashes match; primary metrics reproduce within tolerance; verdict and deviations agree.
**provenance_requirements:**

- artifact hashes
- code commit
- dependency lock
- host/runtime manifest
- operator and timestamps
- documented deviations

- **statistical_reproducibility_criteria:** At least one blinded independent replication for every accepted experiment; two for high-impact claims; stochastic experiments repeat enough seeds for CI overlap and effect-direction agreement.
- **subsystem_layer:** Cross-system reproducibility and independent replication

#### Readiness Gates

**Required gate count:** 14

- `global-01` — canonical code, configuration, dataset and database authority recorded
- `global-02` — required services healthy for the preregistered observation window
- `global-03` — clean-environment build or environment lock reproduced
- `global-04` — research data physically or logically isolated from production writers
- `global-05` — backup integrity verified and at least one restore rehearsal passed
- `global-06` — monitoring detects a deliberately injected non-destructive failure
- `global-07` — dataset snapshots are immutable, hashed, licensed and provenance-complete
- `global-08` — secrets and live financial operations are excluded from experiment scope
- `global-09` — protocol, analysis code, thresholds and stopping rules are frozen
- `global-10` — independent reviewer signs the readiness record
- `NEXUS-EXP-006-01` — original experiment completed validly
- `NEXUS-EXP-006-02` — evidence bundle sealed
- `NEXUS-EXP-006-03` — replicator independent
- `NEXUS-EXP-006-04` — clean environment available

#### Current Interpretation

`NEXUS-EXP-006` remains **BLOCKED / PENDING** according to the canonical experiment registry.

Implementation, test coverage, gate machinery or architectural completeness must not be substituted for a different canonical experiment state.

---

## Global Readiness Principles

The requirements architecture contains global controls that apply across the experimental programme.

These controls include requirements concerning experimental definition, dataset integrity and provenance, exclusion of secrets or live financial operations, frozen protocol and analysis conditions, and independent review of readiness.

The exact canonical gate definitions remain in `experiment_requirements.json`; this document does not redefine them.

### Independent Reviewer Gate

The global readiness model includes independent reviewer approval.

Automated technical evidence must not silently substitute for a gate that requires independent human authority.

### Frozen Experimental Definition

Protocol, analysis code, thresholds and stopping rules should be frozen before governed execution where required by the canonical readiness model.

This reduces post-hoc alteration of evaluation criteria after outcomes become known.

### Dataset Integrity

Dataset snapshots used for governed experiments should satisfy the applicable immutability, hashing, licensing and provenance requirements.

### Operational Exclusions

Secrets and live financial operations are excluded from experimental scope where required by the global readiness gates.

---

## EXP-006 Replication Dependency

`NEXUS-EXP-006` contains explicit replication-related prerequisites:

- `NEXUS-EXP-006-01` — original experiment completed validly
- `NEXUS-EXP-006-02` — evidence bundle sealed
- `NEXUS-EXP-006-03` — replicator independent
- `NEXUS-EXP-006-04` — clean environment available

Accordingly, EXP-006 must not be treated as an ordinary independent experiment that can run without a valid predecessor and replication conditions.

---

## Scientific Claim Boundary

The experiment programme distinguishes:

```text
experiment registered
        != experiment ready

experiment ready
        != experiment successful

experiment completed
        != claim supported

internal result reproduced
        != independently replicated
```

Each stronger state requires the evidence and authority defined for that transition.

At this release point:

- canonical experiments: **BLOCKED / PENDING**;
- central scientific hypothesis: **not yet experimentally validated**;
- independent replication: **not claimed**.

---

## Source of Truth

Machine-readable experiment state:

`systems/librarian/experiments/registry.json`

Machine-readable readiness requirements:

`systems/engineering_studio/experimental_validation/config/experiment_requirements.json`

Research workflow:

`systems/librarian/experiments/RESEARCH_WORKFLOW.md`

Experimental Validation implementation:

`systems/engineering_studio/experimental_validation/`

Independent verification and replication architecture:

`research/external_verification/`

## How to Interpret an Experiment Record

Each canonical experiment record represents a governed scientific object rather than a general project task.

Readers should distinguish the experiment definition from its readiness state, execution state, result and later replication state.

### Registration Is Not Readiness

An experiment appearing in the canonical registry establishes that the experiment is formally represented. It does not establish that its prerequisites have been satisfied.

### Readiness Is Not Success

`READY` means the applicable prerequisites for governed execution have been satisfied. It does not predict the experimental outcome.

### Execution Is Not Validation

Successful execution establishes that the experimental procedure ran sufficiently to produce an evaluable result. It does not establish that the hypothesis was supported.

### Completion Is Not Support

A completed experiment may produce positive, negative, null, contradictory, qualified or invalid evidence according to the applicable protocol.

Under the canonical workflow, scientific support remains constrained by the independent-replication requirement.

---

## Reproducibility Model

Reproducibility is treated as an evidence property rather than a descriptive claim.

Where applicable, a reproducible experiment should preserve enough information to reconstruct the evaluated conditions, including:

- canonical experiment identity;
- frozen protocol;
- dataset identity and hashes;
- transformation history;
- analysis code;
- thresholds and stopping rules;
- execution environment;
- dependency state;
- evidence artifacts;
- deviations from protocol;
- result-scoring procedure.

### Reproduction Versus Replication

Internal reproduction asks whether the result can be reconstructed under sufficiently equivalent controlled conditions.

Independent replication asks a stronger question: whether an appropriately independent process can reproduce the relevant scientific result while satisfying the applicable replication protocol.

These states must not be treated as synonyms.

### Clean Environment

A clean replication environment reduces contamination from hidden local state, undocumented dependencies, mutable inputs or implementation-specific residue.

EXP-006 explicitly includes clean-environment availability among its experiment-specific readiness requirements.

---

## Contamination Controls

Experimental validity can be weakened when information from evaluation conditions leaks into development, analysis or decision criteria.

Contamination controls should therefore preserve separation between preregistered experimental definitions and information learned after execution begins.

Potential contamination channels include:

- changing thresholds after observing results;
- modifying stopping rules post hoc;
- selecting favourable subsets after outcome inspection;
- allowing mutable datasets to change between runs without provenance;
- using evaluation outputs to alter the evaluated implementation without recording a new experimental state;
- hidden environment state;
- undeclared manual intervention;
- reuse of evidence from an incompatible experimental context.

### Frozen Criteria

The global readiness requirements explicitly require protocol, analysis code, thresholds and stopping rules to be frozen.

This provides an architectural boundary against adapting the success criteria to observed outcomes.

### Immutable Dataset Evidence

The global readiness requirements also require dataset snapshots to be immutable, hashed, licensed and provenance-complete.

This allows later reviewers to distinguish a defined experimental dataset from a mutable data source.

---

## Null, Negative and Invalid Results

NEXUS does not require an experiment to support its hypothesis in order for the experiment to be scientifically useful.

A governed experiment may legitimately produce:

- support for the preregistered prediction;
- support for a null or alternative explanation;
- a null result;
- contradictory evidence;
- an inconclusive result;
- an invalid result caused by protocol or evidence failure;
- a replication failure.

Negative and null results should remain in the evidence history rather than being removed because they weaken the preferred hypothesis.

### Invalid Runs

An invalid run should be distinguished from evidence against the hypothesis.

Examples may include contamination, protocol violation, corrupted evidence, missing required inputs or execution conditions that make the preregistered analysis uninterpretable.

Invalidation should itself be justified by evidence rather than used as a post-hoc mechanism for discarding an unfavourable result.

---

## Replication and NEXUS-EXP-006

`NEXUS-EXP-006` occupies a distinct position in the canonical programme because its experiment-specific readiness gates explicitly depend on prior experimental evidence.

Its canonical experiment-specific gates require:

- the original experiment to have completed validly;
- the evidence bundle to have been sealed;
- the replicator to be independent;
- a clean environment to be available.

EXP-006 therefore cannot legitimately bypass the predecessor experiment simply because replication infrastructure exists.

Likewise, an internal rerun of an experiment is not automatically equivalent to EXP-006 independent replication.

### Failed Replication

The canonical research workflow treats failed or partial replication as contradictory evidence that may reduce confidence in the original result.

A replication failure must remain visible and must not be rewritten as successful independent replication.

---

## Experiment-State Interpretation

The following interpretation should be used when reading NEXUS experimental state:

| State | Defensible interpretation | Must not be inferred |
|---|---|---|
| `PREREGISTERED` | Experimental definition exists | Ready to run |
| `BLOCKED` | One or more required readiness conditions remain unsatisfied | Failed hypothesis |
| `READY` | Required readiness gates have been satisfied | Successful result |
| `RUNNING` | Governed execution is in progress | Final verdict |
| `COMPLETED` | Execution and required result processing completed | Independent replication or scientific support by itself |

The result status, final verdict and replication state should therefore be inspected separately.

---
