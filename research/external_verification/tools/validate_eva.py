#!/usr/bin/env python3

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

failures = []
passes = []

def check(condition, message):
    if condition:
        passes.append(message)
        print("PASS:", message)
    else:
        failures.append(message)
        print("FAIL:", message)

# ---------------------------------------------------------------------------
# Required structure
# ---------------------------------------------------------------------------

required_dirs = [
    "00_master/governance",
    "00_protocol_review",
    "01_scientific_replication",
    "02_agent_evaluation",
    "03_software_assurance",
    "04_cleanroom_reproduction",
    "05_professional_assurance",
    "registry",
    "schemas",
    "tools",
    "reports",
    "logs",
]

for rel in required_dirs:
    check((ROOT / rel).is_dir(), f"directory {rel}")

# ---------------------------------------------------------------------------
# Required artifacts
# ---------------------------------------------------------------------------

required_files = [
    "INSTALL_STATE",

    "00_master/governance/PROGRESSIVE_ASSURANCE.md",
    "00_master/governance/HARD_INVARIANTS.md",
    "00_master/governance/LIFECYCLE.md",
    "00_master/governance/SEPARATION_OF_DUTIES.md",

    "00_protocol_review/templates/PROTOCOL_REVIEW.md",
    "01_scientific_replication/templates/REPLICATION.md",
    "02_agent_evaluation/templates/AGENT_EVALUATION.md",
    "03_software_assurance/templates/SOFTWARE_ASSURANCE.md",
    "04_cleanroom_reproduction/templates/CLEANROOM.md",
    "05_professional_assurance/templates/PROFESSIONAL_ASSURANCE.md",

    "00_master/independence/EXTERNAL_REVIEWER_ATTESTATION.md",
    "00_master/claims/CLAIM_TEMPLATE.md",

    "registry/claims/CLAIM_REGISTER.json",
    "registry/verifiers/VERIFIER_REGISTER.json",
    "registry/organisations/ORGANISATION_REGISTER.json",
    "registry/packages/PACKAGE_REGISTER.json",
    "registry/evidence/EVIDENCE_REGISTER.json",
    "registry/conflicts/CONFLICT_REGISTER.json",
    "registry/attestations/ATTESTATION_REGISTER.json",
    "registry/events/EVENT_LEDGER.json",

    "schemas/claim.schema.json",
    "schemas/verifier.schema.json",
    "schemas/package.schema.json",
    "schemas/external_result.schema.json",
    "schemas/conflict.schema.json",
    "schemas/lifecycle.json",
    "schemas/event.schema.json",

    "registry/EXPERIMENTAL_VALIDATION_INTERFACE_STATUS.json",
    "reports/experimental_validation_discovery.txt",
]

for rel in required_files:
    p = ROOT / rel
    check(p.is_file() and p.stat().st_size > 0, f"artifact {rel}")

# ---------------------------------------------------------------------------
# JSON parse validation
# ---------------------------------------------------------------------------

for p in sorted(ROOT.rglob("*.json")):
    try:
        json.loads(p.read_text(encoding="utf-8"))
        check(True, f"JSON parse {p.relative_to(ROOT)}")
    except Exception as exc:
        check(False, f"JSON parse {p.relative_to(ROOT)}: {exc}")

# ---------------------------------------------------------------------------
# Authority barriers
# ---------------------------------------------------------------------------

state_path = ROOT / "INSTALL_STATE"

if state_path.exists():
    state = state_path.read_text(encoding="utf-8")

    required_barriers = [
        "STATUS=CANONICAL_CANDIDATE",
        "EXPERIMENT_EXECUTION=PROHIBITED",
        "EXPERIMENT_STATE_TRANSITION=PROHIBITED",
        "EXPERIMENT_REGISTRY_MUTATION=PROHIBITED",
        "SELF_VERIFICATION=PROHIBITED",
        "EXTERNAL_VERDICT_GENERATION=PROHIBITED",
        "EXTERNAL_VERDICT_MUTATION=PROHIBITED",
    ]

    for barrier in required_barriers:
        check(barrier in state, f"authority barrier {barrier}")

# ---------------------------------------------------------------------------
# Experimental Validation interface barriers
# ---------------------------------------------------------------------------

interface_path = (
    ROOT /
    "registry" /
    "EXPERIMENTAL_VALIDATION_INTERFACE_STATUS.json"
)

if interface_path.exists():

    interface = json.loads(
        interface_path.read_text(encoding="utf-8")
    )

    check(
        interface.get("status") == "INTEGRATION_PENDING",
        "EV integration remains pending"
    )

    check(
        interface.get("authority") == "NONE",
        "EV integration authority NONE"
    )

    check(
        interface.get("experiment_execution") == "PROHIBITED",
        "EV experiment execution prohibited"
    )

    check(
        interface.get("experiment_state_transition") == "PROHIBITED",
        "EV state transition prohibited"
    )

    check(
        interface.get("experimental_registry_mutation") == "PROHIBITED",
        "EV registry mutation prohibited"
    )

    check(
        interface.get("automatic_gate_satisfaction") == "PROHIBITED",
        "automatic gate satisfaction prohibited"
    )

# ---------------------------------------------------------------------------
# Progressive assurance sanity
# ---------------------------------------------------------------------------

policy = (
    ROOT /
    "00_master" /
    "governance" /
    "PROGRESSIVE_ASSURANCE.md"
)

if policy.exists():

    text = policy.read_text(encoding="utf-8")

    check(
        "External verification required: 0" in text,
        "ordinary internal experimentation requires zero external layers"
    )

    check(
        "L1 Scientific Independent Replication" in text,
        "L1 scientific replication policy"
    )

    check(
        "L4 Clean-Room Reproduction" in text,
        "L4 clean-room policy"
    )

    check(
        "L3 Software/Formal" in text,
        "L3 control assurance policy"
    )

# ---------------------------------------------------------------------------
# Lifecycle sanity
# ---------------------------------------------------------------------------

life = json.loads(
    (ROOT / "schemas" / "lifecycle.json").read_text(encoding="utf-8")
)

expected = [
    "DRAFT",
    "PACKAGE_FROZEN",
    "DISPATCHED",
    "RECEIVED",
    "INTEGRITY_VERIFIED",
    "INDEPENDENCE_VERIFIED",
    "ADJUDICATED",
    "SEALED",
]

check(
    life.get("states") == expected,
    "verification lifecycle ordering"
)

check(
    life["allowed_transitions"].get("SEALED") == [],
    "SEALED terminal state"
)

# ---------------------------------------------------------------------------
# Verdict sanity
# ---------------------------------------------------------------------------

result_schema = json.loads(
    (
        ROOT /
        "schemas" /
        "external_result.schema.json"
    ).read_text(encoding="utf-8")
)

verdicts = (
    result_schema
    .get("properties", {})
    .get("verdict", {})
    .get("enum", [])
)

check(
    verdicts == ["PASS", "PARTIAL", "FAIL", "INCONCLUSIVE"],
    "external verdict domain preserves negative/inconclusive outcomes"
)

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("NEXUS-EVA VALIDATION")
print("=" * 70)
print("PASSES   =", len(passes))
print("FAILURES =", len(failures))

if failures:
    print()
    print("RESULT = FAIL")
    print()
    for item in failures:
        print(" -", item)
    raise SystemExit(1)

print("RESULT = PASS")
print()
print("NOTE: This validates the EVA installation.")
print("NOTE: It does NOT externally validate NEXUS.")
print("NOTE: It does NOT grant canonical authority.")
