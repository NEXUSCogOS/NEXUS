"""Bounded evidence-synthesis workflow, research-gap model, and hypothesis
model.

NEW module, NEXUS Librarian F4.

HONESTY NOTE (read before using `classify_claim_support`): Librarian has
NO semantic entailment / claim-verification capability. The classifier
below is a disclosed, narrow KEYWORD-MARKER HEURISTIC (does the retrieved
excerpt contain language like "supports"/"consistent with" vs.
"contradicts"/"in contrast"/"underperform"?) — it is NOT true NLP
entailment and must never be presented as though it determined that a
source actually agrees or disagrees with a claim. It is tested only
against clearly-labeled synthetic fixtures
(`tests/academic/test_synthesis.py`) with KNOWN ground truth. When run
against the real 22-source corpus, its output is reported with this
limitation stated explicitly in every result (see
`research_question_synthesis()` below).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from academic.retrieval import AcademicSearchHit


class ClaimSupportStatus(str, Enum):
    CONSENSUS = "CONSENSUS"
    MIXED = "MIXED"
    CONTRADICTORY = "CONTRADICTORY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ResearchGapType(str, Enum):
    CORPUS_GAP = "CORPUS_GAP"                    # the corpus was never populated for this topic at all
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"        # corpus may have relevant content, but retrieval found none (query/mechanism limitation)
    EVIDENCE_GAP = "EVIDENCE_GAP"                  # sources found, but none carry strong-enough evidence for the specific claim
    LITERATURE_GAP = "LITERATURE_GAP"              # the corpus reflects that the wider literature itself has not addressed this
    OPEN_SCIENTIFIC_QUESTION = "OPEN_SCIENTIFIC_QUESTION"  # sources explicitly frame this as unresolved


class ResearchGap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gap_type: ResearchGapType
    detail: str


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal["HYPOTHESIS"] = "HYPOTHESIS"
    statement: str
    basis: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradictory_evidence: list[str] = Field(default_factory=list)
    falsifiability: str
    possible_experiment: str
    expected_observation: str
    alternative_explanations: list[str] = Field(default_factory=list)


class SynthesisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str
    evidence_refs: list[str] = Field(default_factory=list)  # academic source_ids
    support_status: ClaimSupportStatus
    basis_for_status: str  # ALWAYS states the mechanism honestly (heuristic marker match, or "no sources found")


class SynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_question: str
    findings: list[SynthesisFinding] = Field(default_factory=list)
    gaps: list[ResearchGap] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


_SUPPORT_MARKERS = ["support", "consistent with", "confirm", "validat", "in line with", "demonstrate the effectiveness"]
_CONTRADICT_MARKERS = ["contradict", "inconsistent", "conflict with", "fail to replicate", "underperform", "however,", "in contrast", "unlike", "limitation", "gap that limits", "remains underdeveloped", "remains an open challenge"]


def classify_claim_support(hits: list[AcademicSearchHit]) -> tuple[ClaimSupportStatus, str]:
    """Disclosed keyword-marker heuristic -- see module docstring. NEVER a
    substitute for real semantic entailment."""
    if not hits:
        return ClaimSupportStatus.INSUFFICIENT_EVIDENCE, "no matching sources retrieved for this claim"

    support_hits = []
    contradict_hits = []

    for h in hits:
        text_lower = h.excerpt.lower()
        # Check contradict first (prevents "consistent with" from matching "inconsistent with")
        if any(m in text_lower for m in _CONTRADICT_MARKERS):
            contradict_hits.append(h)
        elif any(m in text_lower for m in _SUPPORT_MARKERS):
            support_hits.append(h)

    basis_prefix = (
        f"heuristic keyword-marker match only (NOT semantic entailment) over {len(hits)} "
        f"retrieved source(s): "
    )
    if support_hits and contradict_hits:
        return ClaimSupportStatus.MIXED, (
            basis_prefix + f"{len(support_hits)} contain support-language markers, "
            f"{len(contradict_hits)} contain contrast/limitation-language markers"
        )
    if support_hits:
        return ClaimSupportStatus.CONSENSUS, (
            basis_prefix + f"{len(support_hits)} contain support-language markers, none contain contrast markers"
        )
    if contradict_hits:
        return ClaimSupportStatus.CONTRADICTORY, (
            basis_prefix + f"{len(contradict_hits)} contain contrast/limitation-language markers, none contain support markers"
        )
    return ClaimSupportStatus.INSUFFICIENT_EVIDENCE, (
        basis_prefix + "no support or contrast markers found -- classifying agreement/disagreement "
        "requires semantic entailment capability, which is NOT_COMMISSIONED"
    )


def classify_research_gap(*, hits: list[AcademicSearchHit], corpus_has_any_sources: bool) -> Optional[ResearchGap]:
    """Distinguishes a genuine gap type rather than collapsing every
    'no result' into a blanket 'research gap' claim (mission section 19)."""
    if hits:
        return None  # evidence was found; no gap to report for this specific query
    if not corpus_has_any_sources:
        return ResearchGap(gap_type=ResearchGapType.CORPUS_GAP, detail="the academic corpus contains zero sources at all")
    return ResearchGap(
        gap_type=ResearchGapType.RETRIEVAL_FAILURE,
        detail=(
            "the corpus is non-empty but lexical retrieval found no matching source for "
            "these query terms -- this is a RETRIEVAL limitation (or the corpus genuinely "
            "lacks coverage of this specific sub-topic), not evidence that the wider "
            "literature has never addressed the question (that would require LITERATURE_GAP, "
            "which needs an external literature-coverage check this mission does not perform)"
        ),
    )
