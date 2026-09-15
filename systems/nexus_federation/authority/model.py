"""Federation authority taxonomy.

New module, NEXUS Federation F2. A delegation proposal must state, in a
closed typed vocabulary, exactly what it is asking a recipient institution
to do -- not leave that to be inferred from the free-text `objective`
field. A recipient may not read "assess the financial implications of X"
and conclude it was granted authority to act on those implications; the
`authority` field is the only place that grant is expressed, and it is
always the narrowest level that satisfies the request.

Ordering below is deliberately a ladder, from least to most consequential,
mirroring the same "narrowest first" discipline used throughout this
estate's contract and capability models. NEXUS Federation F1/F2 never
issues anything above ANALYSE: nothing in this codebase requests
generation of durable output, reversible or irreversible modification, or
any external/high-consequence action. That ceiling is enforced by
`delegation/schema.py` and `relevance/router.py`, and documented here so a
future change to grant a broader authority is a visible, deliberate edit
rather than an inferred behavior change.
"""

from __future__ import annotations

from enum import Enum


class AuthorityLevel(str, Enum):
    OBSERVE = "OBSERVE"                              # read/monitor only, no output requested
    RESEARCH = "RESEARCH"                             # gather and report information
    ANALYSE = "ANALYSE"                               # interpret/assess already-gathered information
    GENERATE_INTERNAL = "GENERATE_INTERNAL"           # produce a durable internal artifact (report, dataset)
    MODIFY_REVERSIBLE = "MODIFY_REVERSIBLE"           # change internal state in a way that can be undone
    ARCHITECTURAL_CHANGE = "ARCHITECTURAL_CHANGE"     # change structure/schema/contracts
    EXTERNAL_ACTION = "EXTERNAL_ACTION"               # act on a system outside the federation
    HIGH_CONSEQUENCE_ACTION = "HIGH_CONSEQUENCE_ACTION"  # financial, legal, safety-relevant, or otherwise hard-to-reverse


# The maximum authority level any component in NEXUS Federation F1/F2 may
# grant in a delegation proposal. Raising this requires a deliberate,
# reviewed change to this constant -- never an inferred escalation from an
# objective's wording.
_LADDER = [
    AuthorityLevel.OBSERVE,
    AuthorityLevel.RESEARCH,
    AuthorityLevel.ANALYSE,
    AuthorityLevel.GENERATE_INTERNAL,
    AuthorityLevel.MODIFY_REVERSIBLE,
    AuthorityLevel.ARCHITECTURAL_CHANGE,
    AuthorityLevel.EXTERNAL_ACTION,
    AuthorityLevel.HIGH_CONSEQUENCE_ACTION,
]

MAX_GRANTABLE_AUTHORITY_THIS_PHASE = AuthorityLevel.GENERATE_INTERNAL
# NEXUS Federation F8: deliberately, visibly raised one rung, from ANALYSE
# to GENERATE_INTERNAL. This is the first mission whose institution
# (YouTube Production) is asked to produce a durable internal artifact
# (a script, a rendered video, a thumbnail) rather than only research or
# analysis -- so the prior ceiling was a genuine blocker, not a
# convention to route around. GENERATE_INTERNAL remains far short of
# EXTERNAL_ACTION (publishing, uploading, posting) and
# HIGH_CONSEQUENCE_ACTION: those remain unreachable by this same
# structural mechanism (`_authority_never_exceeds_phase_ceiling` below),
# which is exactly what YOUTUBE_PUBLICATION_BOUNDARY_TEST.md exercises.


def authority_rank(level: AuthorityLevel) -> int:
    return _LADDER.index(level)


def exceeds_phase_ceiling(level: AuthorityLevel) -> bool:
    return authority_rank(level) > authority_rank(MAX_GRANTABLE_AUTHORITY_THIS_PHASE)
