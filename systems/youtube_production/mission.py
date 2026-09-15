"""NEXUS-side: decide editorial suitability of a real cross-domain
synthesis and, if suitable, build a Production Mission Contract for
YouTube. NEXUS Federation F8, mission sections 5 and 23.

`NO_PRODUCTION_ACTION_REQUIRED` is a first-class, legitimate outcome
here, not a failure -- mission section 23's own words: "NO_PRODUCTION_
ACTION_REQUIRED is a valid outcome if not [editorially suitable]."
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from budget.schema import ResourceBudget

from schema import ProductionMissionContract, ProductionTerminalState
from channel import select_channel

# Conclusions with a real, positive-or-mixed cross-domain claim to build a
# grounded video around. Deliberately excludes the two "nothing to say"
# classes -- a real, disclosed rule, not a learned/opaque score.
_EDITORIALLY_SUITABLE_CLASSES = frozenset({
    "SUPPORTED_CROSS_DOMAIN_INFERENCE",
    "PARTIALLY_SUPPORTED",
    "MIXED_EVIDENCE",
    "CONTRADICTORY_EVIDENCE",
})
_NOT_SUITABLE_CLASSES = frozenset({
    "INSUFFICIENT_EVIDENCE",
    "NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED",
})


def assess_editorial_suitability(executive_conclusion_class: str) -> tuple[bool, str]:
    if executive_conclusion_class in _EDITORIALLY_SUITABLE_CLASSES:
        return True, f"executive_conclusion_class={executive_conclusion_class} carries a real cross-domain claim worth explaining to an audience"
    if executive_conclusion_class in _NOT_SUITABLE_CLASSES:
        return False, f"executive_conclusion_class={executive_conclusion_class} establishes nothing substantive enough to build a grounded video around"
    return False, f"executive_conclusion_class={executive_conclusion_class} not in the known suitability vocabulary -- defaulting to NOT suitable, never assumed suitable"


def _zero_budget(basis: str) -> ResourceBudget:
    return ResourceBudget(
        cpu_seconds=0.0, memory_bytes=0, elapsed_seconds=0.0,
        local_storage_bytes=0, external_storage_bytes=0,
        api_cost_usd=0.0, model_tokens=0, basis=basis,
    )


def _production_budget() -> ResourceBudget:
    return ResourceBudget(
        cpu_seconds=120.0,
        memory_bytes=1024 * 1024 * 1024,
        elapsed_seconds=300.0,
        local_storage_bytes=5 * 1024 * 1024,       # metadata/db only, local
        external_storage_bytes=200 * 1024 * 1024,  # rendered media, external volume
        api_cost_usd=0.0,       # no paid API is used for this mission's render path (say/Pillow/ffmpeg are local, free)
        model_tokens=0,
        basis=(
            "NEXUS Federation F8 policy default for GENERATE_INTERNAL-authority "
            "YouTube production missions: bounded to one short-form render using "
            "local, credential-free tools (macOS `say`, Pillow, ffmpeg) -- no "
            "external paid API, no model token usage, per YOUTUBE_F8_FORENSIC_"
            "REPORT.md's finding that this environment has no working cloud TTS "
            "or paid generation credentials configured"
        ),
    )


def build_production_mission(
    *,
    trigger_id: str,
    synthesis_id: str,
    executive_conclusion_class: str,
    executive_conclusion: str,
    evidence_refs: list[str],
    provenance_refs: list[str],
    event_headline: str,
    event_keywords: list[str],
    uncertainties: list[str],
    contradictory_findings: list[str],
) -> ProductionMissionContract | None:
    """Returns None if NOT editorially suitable (caller records
    NO_PRODUCTION_ACTION_REQUIRED and stops -- no contract is built at
    all, since a contract implies a real production commitment)."""

    suitable, reason = assess_editorial_suitability(executive_conclusion_class)
    if not suitable:
        return None

    production_mission_id = str(uuid5(NAMESPACE_URL, f"f8-mission:{synthesis_id}"))
    now = datetime.now(timezone.utc).isoformat()

    channel_id, channel_reason = select_channel(event_headline, event_keywords)
    if channel_id is None:
        # A contract still records the attempt and its own terminal
        # state, honestly, rather than silently doing nothing.
        return ProductionMissionContract(
            production_mission_id=production_mission_id,
            parent_trigger_id=trigger_id,
            parent_synthesis_id=synthesis_id,
            channel_id=None,
            editorial_objective=f"Explain: {event_headline}",
            target_audience="UNKNOWN (no channel identity matched)",
            evidence_refs=evidence_refs,
            provenance_refs=provenance_refs,
            allowed_claims=[],
            uncertain_claims=uncertainties,
            prohibited_claims=[],
            tone="UNKNOWN",
            format="UNKNOWN",
            target_duration_seconds=0,
            resource_budget=_zero_budget(f"NO_APPROPRIATE_CHANNEL: {channel_reason}").model_dump(),
            rights_constraints=[],
            authority="GENERATE_INTERNAL",
            success_criteria=[],
            terminal_state=ProductionTerminalState.NO_APPROPRIATE_CHANNEL.value,
            created_at=now,
        )

    return ProductionMissionContract(
        production_mission_id=production_mission_id,
        parent_trigger_id=trigger_id,
        parent_synthesis_id=synthesis_id,
        channel_id=channel_id,
        editorial_objective=f"Explain, for a general audience, what the federation's real cross-domain analysis established about: {event_headline}",
        target_audience="general_interest_viewers_of_the_selected_channel_identity",
        evidence_refs=evidence_refs,
        provenance_refs=provenance_refs,
        allowed_claims=[executive_conclusion],
        uncertain_claims=uncertainties,
        prohibited_claims=[
            "Any claim stronger than the executive_conclusion_class established",
            "Any specific numeric forecast not present in the evidence pack",
        ] + contradictory_findings,
        tone="measured_explainer",
        format="short_form_explainer",
        target_duration_seconds=45,
        resource_budget=_production_budget().model_dump(),
        rights_constraints=["all visual/audio assets must reach a non-UNKNOWN rights_status before render acceptance"],
        authority="GENERATE_INTERNAL",
        success_criteria=[
            "every factual claim in the script traces to an evidence_ref",
            "no claim upgraded beyond its source claim_class",
            "fact_check_results contain zero UNSUPPORTED claims in the final script",
            "terminal_state reaches READY_FOR_PUBLICATION_AUTHORIZATION, never PUBLISHED",
        ],
        terminal_state=ProductionTerminalState.RECEIVED.value,
        created_at=now,
    )
