# NexusCogOS Update Direction Policy

## Authority

Canonical NEXUS evidence remains authoritative.

Public GitHub repositories are publication derivatives.

## Normal publication direction

CANONICAL NEXUS
→ VALIDATED EVIDENCE
→ PUBLICATION ADAPTER
→ ISOLATED STAGING
→ SANITISATION
→ TEST
→ RELEASE CANDIDATE
→ HUMAN APPROVAL
→ GITHUB

## Prohibited reverse paths

GITHUB → CANONICAL NEXUS

GITHUB → RAW EVIDENCE

GITHUB → EXPERIMENT RESULT

PUBLIC DOSSIER → CANONICAL CLAIM

CAREER OBJECTIVE → EXPERIMENT RESULT

## GitHub contributions

External GitHub changes shall be considered UNTRUSTED INPUT.

Required route:

GITHUB CONTRIBUTION
→ ISOLATED REVIEW
→ SANDBOX
→ TEST
→ SECURITY REVIEW
→ ENGINEERING PROPOSAL
→ HUMAN APPROVAL
→ NORMAL CANONICAL INTEGRATION

No automatic GitHub-to-NEXUS synchronization is permitted.

## Authentication

GitHub authentication credentials must remain outside canonical NEXUS.

Do not store:

- personal access tokens
- passwords
- SSH private keys
- OAuth secrets

inside the publication subsystem.

Authentication shall later use an external authenticated GitHub client/keychain.

## Human publication gate

Automated validation does not constitute permission to publish.

External publication always requires explicit human authorization.
