# NEXUS Security Policy

## Scope

This document describes the security posture and vulnerability-reporting boundary of the public NEXUS research repository.

The initial public release passed a defined publication-security and release-hygiene gate before publication.

That result is bounded evidence about the checks that were performed. It does **not** establish that NEXUS is unhackable, free from every vulnerability or suitable for unrestricted deployment.

## Initial Publication Security Baseline

The authorized initial public release was checked for:

- private owner-path exposure;
- high-confidence secret exposure;
- prohibited generated runtime artifacts;
- nested Git repositories;
- oversized files;
- executable `shell=True` use;
- production `eval()` / `exec()`;
- generic unsafe deserialization;
- unsafe PyTorch full-object checkpoint loading;
- execution-command boundaries;
- Python parse/compile integrity;
- release-manifest integrity;
- local/remote commit identity.

The final publication baseline reported zero blocking findings in the defined checked categories.

## PyTorch Deserialization Boundary

Public DAT_AI checkpoint loading was hardened to use the restricted `weights_only=True` boundary.

Full serialized Python model-object loading is prohibited by the hardened public loading path.

This reduces a defined deserialization risk; it does not establish universal model or application security.

## Execution Boundary

The public Engineering Studio release includes explicit command-policy hardening intended to constrain selected test-execution paths.

The presence of this policy must not be interpreted as proof that every possible execution path in every subsystem is governed by one universal command filter.

## Secrets

Secrets, private credentials and private operational configuration should not be committed to the public repository.

If a secret is discovered, treat it as compromised where appropriate, revoke or rotate it through the relevant provider, and remove it from future repository state.

Historical Git removal alone does not invalidate an already exposed credential.

## Vulnerability Reporting

Security findings should include, where safely possible:

- affected component;
- affected release or commit;
- vulnerability class;
- reproducible evidence;
- expected versus observed behaviour;
- impact;
- prerequisites;
- suggested mitigation if known.

Do not include live credentials, unnecessary personal information or destructive proof-of-concept material in public reports.

## Security Claims

Security findings and mitigations should be described in bounded terms.

Passing a security test establishes that the tested condition passed under the tested assumptions. It does not prove the absence of all vulnerabilities.

## Release Identity

The initial authorized public release identity documented by the repository is:

```text
Commit: 2b3f129c21bdf5ef78cfcb59721b09281c8cc489
Tree:   35a6919259d3f0317bd761e0a1a797254b285103
```

Subsequent documentation commits necessarily create new Git identities and should not be represented as the original sealed release tree.

## Scientific Boundary

Security validation and scientific validation are separate concerns.

The publication-security gate does not establish that the central NEXUS scientific hypothesis has been experimentally validated or independently replicated.
