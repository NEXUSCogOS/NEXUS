"""Cross-domain executive synthesis. New module, NEXUS Federation F6.

Deterministic, rule-based synthesis of two independent specialist
InstitutionalReports (Librarian + Sentinel) triggered by one DAT.AI
finding. Never concatenates reports (mission section 12's explicit
prohibition) -- builds a distinct ExecutiveSynthesis object whose fields
are each computed by a named, inspectable function, and whose
`executive_conclusion_class` is chosen from a fixed enum by explicit
rules over the two reports' own claim classes, never an opaque/learned
score (mission section 24).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class ExecutiveConclusionClass(str, Enum):
    SUPPORTED_CROSS_DOMAIN_INFERENCE = "SUPPORTED_CROSS_DOMAIN_INFERENCE"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    MIXED_EVIDENCE = "MIXED_EVIDENCE"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED = "NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED"


# A report's own claim-class vocabulary is heterogeneous across
# institutions (Librarian: SOURCE_FACT/DERIVED_SYNTHESIS/INFERENCE/
# HYPOTHESIS/CONTRADICTION/INSUFFICIENT_EVIDENCE; Sentinel:
# OBSERVED_MARKET_FACT/DERIVED_METRIC/MODEL_ESTIMATE/SIGNAL/
# RECOMMENDATION/UNKNOWN). This maps each vocabulary onto one of three
# coarse SUPPORT/CONTRADICT/INSUFFICIENT buckets for cross-institution
# comparison ONLY -- the original, institution-specific claim class is
# always preserved verbatim in supporting_findings/contradictory_findings
# below, never discarded or overwritten.
_SUPPORT_MARKERS = ("CONSENSUS", "SOURCE_FACT", "DERIVED_SYNTHESIS")
_CONTRADICT_MARKERS = ("CONTRADICTORY", "CONTRADICTION")
_INSUFFICIENT_MARKERS = ("INSUFFICIENT_EVIDENCE", "UNKNOWN")


def _bucket(claim_text: str) -> str:
    """Every finding string in this mission follows the convention
    'TAG: rest of text' (OBSERVED_MARKET_FACT: ..., INSUFFICIENT_EVIDENCE:
    ..., etc). Matching only the LEADING tag (before the first colon) is
    deliberate, not incidental: an earlier version matched markers
    anywhere in the string and was caught, during F6 construction,
    bucketing a Sentinel entity-mapping finding as INSUFFICIENT solely
    because the word 'UNKNOWN' appeared inside a classification sentence
    unrelated to that finding's own epistemic tag (which was actually
    DERIVED_METRIC). Matching only the leading tag eliminates that class
    of false match entirely, since every finding-emitting subprocess in
    this mission emits tags in that exact leading position."""
    leading_tag = claim_text.split(":", 1)[0].strip().upper()
    if any(m == leading_tag or leading_tag.startswith(m) for m in _CONTRADICT_MARKERS):
        return "CONTRADICT"
    if any(m == leading_tag or leading_tag.startswith(m) for m in _SUPPORT_MARKERS):
        return "SUPPORT"
    if any(m == leading_tag or leading_tag.startswith(m) for m in _INSUFFICIENT_MARKERS):
        return "INSUFFICIENT"
    return "NEUTRAL"


@dataclass
class ExecutiveSynthesis:
    synthesis_id: str
    trigger_id: str
    input_report_ids: list[str]
    supporting_findings: list[str]
    contradictory_findings: list[str]
    independent_corroboration: list[str]
    uncertainties: list[str]
    data_gaps: list[str]
    temporal_mismatches: list[str]
    source_quality: list[str]
    cross_domain_implications: list[str]
    executive_conclusion: str
    executive_conclusion_class: ExecutiveConclusionClass
    recommended_next_actions: list[str]
    prohibited_actions: list[str]
    confidence_basis: str
    evidence_refs: list[str]
    provenance_refs: list[str]
    synthesized_at: str
    partial: bool = False
    missing_institutions: list[str] = field(default_factory=list)


PROHIBITED_ACTIONS = [
    "PROHIBITED: place a live order",
    "PROHIBITED: cancel an order",
    "PROHIBITED: change execution_mode",
    "PROHIBITED: change execution_allowed",
    "PROHIBITED: invoke broker execution",
    "PROHIBITED: publish externally",
    "PROHIBITED: modify another institution's data or code",
    "PROHIBITED: convert this conclusion directly into a financial trade",
]


def _temporal_mismatches(
    dat_ai_observation_ts: str,
    librarian_report: Optional[dict],
    sentinel_report: Optional[dict],
    now: datetime,
) -> list[str]:
    mismatches = []
    try:
        obs_date = datetime.fromisoformat(dat_ai_observation_ts.replace("Z", "+00:00"))
        age_days = (now - obs_date.replace(tzinfo=now.tzinfo) if obs_date.tzinfo is None else now - obs_date).days
        if age_days > 30:
            mismatches.append(
                f"DAT.AI observation ({dat_ai_observation_ts}) is {age_days} "
                f"days old relative to synthesis time -- usable as "
                f"historical planning context, not presented as a new "
                f"development."
            )
    except (ValueError, TypeError):
        mismatches.append(f"DAT.AI observation_timestamp {dat_ai_observation_ts!r} could not be parsed for age comparison")

    if sentinel_report:
        sentinel_findings_text = " ".join(sentinel_report.get("findings", []))
        if "STALE_DATA" in " ".join(sentinel_report.get("limitations", [])):
            mismatches.append(
                "Sentinel's macro_data context is stale (see Sentinel "
                "report limitations) relative to its own current price/"
                "decision data -- flagged, not silently unified."
            )

    return mismatches


def synthesize(
    *,
    trigger_id: str,
    trigger_evidence_refs: list[str],
    trigger_provenance_refs: list[str],
    dat_ai_observation_ts: str,
    librarian_report: Optional[dict],
    sentinel_report: Optional[dict],
    now: Optional[datetime] = None,
    expected_institutions: Optional[list[str]] = None,
) -> ExecutiveSynthesis:
    """The one public entry point. Handles the full-both-reports case and
    the partial (one institution missing) case explicitly (mission
    section 21) -- never fabricates a missing institution's contribution.

    `expected_institutions` (F7 addition, backward-compatible): which
    institutions were actually DELEGATED TO for this trigger -- defaults
    to `["librarian", "sentinel"]` (F6's own usage, where relevance
    assessment always delegated to both). An institution absent from
    this list was never relevant in the first place (a deliberate,
    correct NEXUS decision, not a degraded/missing contribution) and
    must NOT force `partial=True`. Found and fixed during F7 construction:
    a single-recipient News-driven trigger (Sentinel relevant, Librarian
    correctly never delegated to) was incorrectly forced to
    `INSUFFICIENT_EVIDENCE`/`partial=True` by the original
    always-both-expected logic, which conflated "not relevant" with
    "relevant but failed to respond."
    """

    now = now or datetime.now()
    expected = expected_institutions if expected_institutions is not None else ["librarian", "sentinel"]

    missing = []
    if "librarian" in expected and librarian_report is None:
        missing.append("librarian")
    if "sentinel" in expected and sentinel_report is None:
        missing.append("sentinel")
    partial = bool(missing)

    input_report_ids = []
    supporting: list[str] = []
    contradictory: list[str] = []
    uncertainties: list[str] = []
    data_gaps: list[str] = []
    source_quality: list[str] = []
    evidence_refs = list(trigger_evidence_refs)
    provenance_refs = list(trigger_provenance_refs)

    lib_bucket = None
    sen_bucket = None

    if librarian_report:
        input_report_ids.append(librarian_report.get("cycle_id", "unknown"))
        evidence_refs.extend(librarian_report.get("evidence_refs", []))
        provenance_refs.extend(librarian_report.get("provenance_refs", []))
        uncertainties.extend(librarian_report.get("uncertainty", []))
        data_gaps.extend([l for l in librarian_report.get("limitations", []) if "CORPUS" in l.upper() or "GAP" in l.upper()])
        source_quality.append(
            f"Librarian: {len(librarian_report.get('evidence_refs', []))} evidence_refs, "
            f"capability confidence(s): {[cs.get('confidence') for cs in librarian_report.get('capability_statuses', [])]}"
        )
        for f in librarian_report.get("findings", []):
            bucket = _bucket(f)
            lib_bucket = bucket if lib_bucket in (None, "NEUTRAL") else lib_bucket
            if bucket == "SUPPORT":
                supporting.append(f"[LIBRARIAN] {f}")
            elif bucket == "CONTRADICT":
                contradictory.append(f"[LIBRARIAN] {f}")
            else:
                uncertainties.append(f"[LIBRARIAN, {bucket}] {f}")

    if sentinel_report:
        input_report_ids.append(sentinel_report.get("cycle_id", "unknown"))
        evidence_refs.extend(sentinel_report.get("evidence_refs", []))
        provenance_refs.extend(sentinel_report.get("provenance_refs", []))
        uncertainties.extend(sentinel_report.get("uncertainty", []))
        data_gaps.extend([l for l in sentinel_report.get("limitations", []) if "STALE" in l.upper() or "LIMITATION" in l.upper()])
        source_quality.append(
            f"Sentinel: {len(sentinel_report.get('evidence_refs', []))} evidence_refs, "
            f"capability confidence(s): {[cs.get('confidence') for cs in sentinel_report.get('capability_statuses', [])]}"
        )
        for f in sentinel_report.get("findings", []):
            bucket = _bucket(f)
            sen_bucket = bucket if sen_bucket in (None, "NEUTRAL") else sen_bucket
            if bucket == "SUPPORT":
                supporting.append(f"[SENTINEL] {f}")
            elif bucket == "CONTRADICT":
                contradictory.append(f"[SENTINEL] {f}")
            else:
                uncertainties.append(f"[SENTINEL, {bucket}] {f}")

    # ---- independent corroboration (mission section 14) ----
    # Only recorded if BOTH institutions independently produced a SUPPORT
    # bucket from their OWN, non-overlapping evidence chains (checked by
    # evidence_ref prefix -- Librarian's are arxiv:/academic-corpus-based,
    # Sentinel's are prices_daily:/companies:/frontier_decisions:-based;
    # if they ever shared an identical evidence_ref this would NOT count
    # as independent corroboration, per the mission's explicit warning
    # against double-counting the same originating fact).
    independent_corroboration: list[str] = []
    if lib_bucket == "SUPPORT" and sen_bucket == "SUPPORT":
        lib_refs = set(librarian_report.get("evidence_refs", [])) if librarian_report else set()
        sen_refs = set(sentinel_report.get("evidence_refs", [])) if sentinel_report else set()
        if not (lib_refs & sen_refs):
            independent_corroboration.append(
                "INDEPENDENT_CROSS_DOMAIN_CORROBORATION: Librarian and "
                "Sentinel independently reached SUPPORT-bucketed findings "
                "from disjoint evidence chains."
            )

    # ---- executive conclusion class (mission section 13) ----
    if partial:
        conclusion_class = ExecutiveConclusionClass.INSUFFICIENT_EVIDENCE
        conclusion = (
            f"PARTIAL SYNTHESIS: {', '.join(missing)} unavailable. "
            f"Conclusion withheld pending retry -- not fabricated from "
            f"the available institution(s) alone."
        )
    elif contradictory and (lib_bucket == "SUPPORT" or sen_bucket == "SUPPORT"):
        conclusion_class = ExecutiveConclusionClass.CONTRADICTORY_EVIDENCE
        conclusion = "Librarian and Sentinel findings conflict; neither institution's position is suppressed to force coherence."
    elif independent_corroboration:
        conclusion_class = ExecutiveConclusionClass.SUPPORTED_CROSS_DOMAIN_INFERENCE
        conclusion = "Both institutions independently corroborated a cross-domain implication from disjoint evidence."
    elif lib_bucket == "INSUFFICIENT" and sen_bucket == "INSUFFICIENT":
        conclusion_class = ExecutiveConclusionClass.INSUFFICIENT_EVIDENCE
        conclusion = (
            "Neither Librarian's academic corpus nor Sentinel's governed "
            "financial data could substantiate a specific cross-domain "
            "economic/policy claim for this finding. This is a real, "
            "evidence-grounded non-result, not a failure of the "
            "orchestration -- see supporting institutional reports."
        )
    elif supporting and not contradictory:
        conclusion_class = ExecutiveConclusionClass.PARTIALLY_SUPPORTED
        conclusion = "At least one institution reported supportive evidence; not independently corroborated by the other."
    elif supporting and contradictory:
        conclusion_class = ExecutiveConclusionClass.MIXED_EVIDENCE
        conclusion = "Supporting and contradicting findings both present; neither dominant."
    else:
        conclusion_class = ExecutiveConclusionClass.NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED
        conclusion = "No institution reported evidence establishing a material cross-domain effect."

    temporal_mismatches = _temporal_mismatches(dat_ai_observation_ts, librarian_report, sentinel_report, now)

    cross_domain_implications = []
    if librarian_report:
        cross_domain_implications.extend(librarian_report.get("cross_system_implications", []))
    if sentinel_report:
        cross_domain_implications.extend(sentinel_report.get("cross_system_implications", []))

    recommended_next_actions = []
    if conclusion_class == ExecutiveConclusionClass.INSUFFICIENT_EVIDENCE and not partial:
        recommended_next_actions.append("request DAT.AI re-analysis with facility-level geographic disclosure")
        recommended_next_actions.append("continue monitoring; no bounded experiment justified by current evidence")
    elif partial:
        recommended_next_actions.append(f"retry delegation to {', '.join(missing)}")
    else:
        recommended_next_actions.append("continue monitoring")

    confidence_basis = (
        f"Deterministic rule evaluation over {len(input_report_ids)} "
        f"institutional report(s): support={len(supporting)}, "
        f"contradiction={len(contradictory)}, "
        f"independent_corroboration={len(independent_corroboration)}, "
        f"partial={partial}. No learned or opaque scoring involved."
    )

    return ExecutiveSynthesis(
        synthesis_id=str(uuid4()),
        trigger_id=trigger_id,
        input_report_ids=input_report_ids,
        supporting_findings=supporting,
        contradictory_findings=contradictory,
        independent_corroboration=independent_corroboration,
        uncertainties=uncertainties,
        data_gaps=data_gaps,
        temporal_mismatches=temporal_mismatches,
        source_quality=source_quality,
        cross_domain_implications=cross_domain_implications,
        executive_conclusion=conclusion,
        executive_conclusion_class=conclusion_class,
        recommended_next_actions=recommended_next_actions,
        prohibited_actions=list(PROHIBITED_ACTIONS),
        confidence_basis=confidence_basis,
        evidence_refs=evidence_refs,
        provenance_refs=provenance_refs,
        synthesized_at=now.isoformat(),
        partial=partial,
        missing_institutions=missing,
    )
