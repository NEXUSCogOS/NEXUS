"""Deterministic delegation idempotency key.

New module, NEXUS Federation F2. The same accepted report + the same
executive rule (the routing-table category that fired) must never produce
more than one semantically identical delegation -- including across a
process restart, where nothing in memory survives to remember "I already
did this."

The key is a pure function of the inputs that DEFINE sameness for this
purpose: which institution, which accepted cycle, which capability, and
which relevance category triggered the rule. It deliberately excludes
anything that varies between calls for no semantic reason (proposal_id is
a random UUID; created_at is wall-clock time) -- those must never be part
of an idempotency key, or every call would produce a "new" key.
"""

from __future__ import annotations

import hashlib


def compute_idempotency_key(
    *, institution: str, cycle_id: str, capability_name: str, category: str
) -> str:
    canonical = f"{institution}|{cycle_id}|{capability_name}|{category}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
