# NEXUS-EVA → Experimental Validation Interface Contract

## Status

SPECIFIED / NOT YET ACTIVATED

## Architectural Direction

External Verifier
        ↓
Original External Evidence
        ↓
NEXUS-EVA
        ↓
Integrity + Independence + Scope Processing
        ↓
SEALED EVA Evidence Reference
        ↓
Experimental Validation

The interface is evidence-oriented.

NEXUS-EVA does not acquire experiment-control authority.

---

# Permitted Output From NEXUS-EVA

Experimental Validation may eventually receive a reference containing:

- verification_id;
- evidence_id;
- verification layer;
- claim IDs;
- experiment ID where applicable;
- verifier ID;
- independence classification;
- conflict classification;
- external verdict;
- original evidence SHA-256;
- package SHA-256;
- protocol SHA-256;
- system version;
- lifecycle state;
- seal timestamp;
- limitations;
- canonical EVA evidence locator.

---

# Required State

Only evidence reaching:

SEALED

may be eligible for downstream consumption.

SEALED does not mean PASS.

The original external verdict remains separately represented.

---

# Prohibited Behaviour

NEXUS-EVA MUST NOT:

1. execute an experiment;

2. modify an experiment registry;

3. transition BLOCKED → READY;

4. transition any other experiment state;

5. satisfy a gate merely because a package was created;

6. satisfy a gate merely because evidence was received;

7. treat integrity verification as scientific validation;

8. manufacture a human attestation;

9. manufacture an external verdict;

10. modify an external verdict;

11. suppress FAIL, PARTIAL or INCONCLUSIVE findings;

12. silently reinterpret reviewer scope;

13. generalise verification beyond tested claims;

14. modify Experimental Validation configuration;

15. modify Experimental Validation source code through this interface.

---

# Consumer Responsibility

Experimental Validation remains responsible for determining whether a
particular sealed external-evidence record satisfies its own independently
defined gate requirements.

Example:

A SEALED L0 protocol review does not automatically satisfy an L1 replication
requirement.

A SEALED L3 software-assurance PASS does not automatically establish a
scientific capability claim.

A SEALED result from a NOT_INDEPENDENT verifier cannot silently satisfy an
independent-review requirement.

---

# Fail-Closed Rule

If any required binding is missing, ambiguous or invalid:

EVA_EVIDENCE_ACCEPTABLE = FALSE

No experiment-state implication follows automatically.

---

# Authority Boundary

NEXUS-EVA provides evidence.

Experimental Validation interprets evidence under its own governed authority.

The two responsibilities must remain separate.
