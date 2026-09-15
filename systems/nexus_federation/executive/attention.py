"""NEXUS Executive Attention Model.

F9 hardening: formalize an inspectable executive attention model.

Attention is orthogonal to priority. An item can be high-attention but
low-priority (interesting but not urgent), or low-attention but
high-priority (routine, but urgent).

Deterministic, weights-based model. NOT scientifically calibrated unless
validated against real outcomes (stated as limitation).

Every factor is explicit and auditable.
"""

from dataclasses import dataclass
from enum import Enum


class AttentionClass(str, Enum):
    CRITICAL = "CRITICAL"  # >0.8 score
    HIGH = "HIGH"  # 0.6-0.8
    NORMAL = "NORMAL"  # 0.4-0.6
    LOW = "LOW"  # 0.2-0.4
    MINIMAL = "MINIMAL"  # <0.2


@dataclass(frozen=True)
class AttentionFactors:
    """All factors that influence attention scoring.

    Each factor is a float [0.0, 1.0]. Multiplication model: lower of any
    factor can suppress a signal even if others are high.
    """

    materiality: float  # 0.0 (not material) to 1.0 (existential)
    novelty: float  # 0.0 (seen before) to 1.0 (entirely new)
    time_sensitivity: float  # 0.0 (can wait forever) to 1.0 (immediate action required)
    evidence_quality: float  # 0.0 (no evidence) to 1.0 (verified ground truth)
    uncertainty: float  # 0.0 (certain) to 1.0 (highly uncertain) -- INVERTED in scoring
    cross_domain_relevance: float  # 0.0 (isolated finding) to 1.0 (touches many domains)
    risk: float  # 0.0 (safe) to 1.0 (high risk/consequence)
    reversibility: float  # 0.0 (permanent change) to 1.0 (fully reversible)
    institutional_coverage: float  # 0.0 (no institution ready) to 1.0 (multiple ready)

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


def compute_attention_score(factors: AttentionFactors) -> float:
    """Deterministic attention scoring.

    Model: weighted product of key factors + explicit penalties.
    Returns float [0.0, 1.0].

    Logic:
    - No evidence = no attention, regardless of other factors
    - High uncertainty + low materiality = lower attention
    - Low reversibility + high risk = higher attention (act now before permanent)
    - Isolated findings (low institutional coverage) = lower attention
    """

    # Cannot act on something with no evidence.
    if factors.evidence_quality < 0.1:
        return 0.0

    # Core factors: what matters, how new, how urgent, how supported.
    core_score = (
        factors.materiality * 0.3 +
        factors.novelty * 0.2 +
        factors.time_sensitivity * 0.2 +
        factors.evidence_quality * 0.2 +
        (1.0 - factors.uncertainty) * 0.1  # Invert: certainty is good
    )

    # Modifiers: is this reversible? is there institutional support?
    # Irreversible, high-risk findings get attention boost.
    irreversibility_factor = (1.0 - factors.reversibility) * factors.risk
    core_score += irreversibility_factor * 0.15

    # If no one can act on it, attention is muted.
    if factors.institutional_coverage < 0.1:
        core_score *= 0.5
    else:
        core_score += factors.institutional_coverage * 0.1

    # Cross-domain findings are inherently more interesting.
    core_score += factors.cross_domain_relevance * 0.05

    # Clamp to [0.0, 1.0].
    return min(1.0, max(0.0, core_score))


def classify_attention(score: float) -> AttentionClass:
    """Map numeric score to attention class."""
    if score >= 0.8:
        return AttentionClass.CRITICAL
    elif score >= 0.6:
        return AttentionClass.HIGH
    elif score >= 0.4:
        return AttentionClass.NORMAL
    elif score >= 0.2:
        return AttentionClass.LOW
    else:
        return AttentionClass.MINIMAL


@dataclass(frozen=True)
class AttentionSignal:
    """An event/finding ready for executive attention."""

    signal_id: str  # unique identifier
    source: str  # which institution/capability generated this
    signal_class: str  # what kind of signal (finding, event, result, etc.)
    timestamp: str  # when it occurred (ISO 8601)
    factors: AttentionFactors
    evidence_refs: list[str]  # what evidence supports this

    @property
    def attention_score(self) -> float:
        return compute_attention_score(self.factors)

    @property
    def attention_class(self) -> AttentionClass:
        return classify_attention(self.attention_score)
