"""NEXUS Executive Resource Governance.

F9 hardening: every mission carries bounded, auditable resource budgets.

No mission gets implicit unlimited resources. NEXUS enforces ceilings
across CPU, RAM, elapsed time, storage (local + external), API cost,
model tokens, render compute.

Budgets are policy-derived or explicitly set per mission.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ResourceBudget:
    """Bounded resource allocation for one mission.

    All fields are optional (null = unbounded for that resource).
    When set, these are hard ceilings -- missions exceeding them are
    terminated/rejected.
    """

    cpu_seconds: Optional[float] = None  # wall-clock CPU seconds
    peak_rss_bytes: Optional[float] = None  # peak resident set size, bytes
    elapsed_seconds: Optional[float] = None  # total wall-clock time, seconds
    local_storage_bytes: Optional[float] = None  # disk usage on this machine
    external_storage_bytes: Optional[float] = None  # usage on mounted external storage
    api_calls: Optional[int] = None  # number of external API invocations
    api_cost_usd: Optional[float] = None  # maximum USD spend on API calls
    model_tokens: Optional[int] = None  # maximum tokens for LLM invocations
    render_compute_seconds: Optional[float] = None  # GPU/codec render time
    parallel_mission_count: Optional[int] = None  # max # of concurrent sub-missions

    def __post_init__(self):
        """Sanity check: budgets must be non-negative if set."""
        for name, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, (int, float)) and value < 0:
                    raise ValueError(f"{name} must be non-negative, got {value}")

    @property
    def is_unbounded(self) -> bool:
        """True if ALL budgets are null (no constraints)."""
        return all(v is None for v in self.__dict__.values())

    def exceeded_by(self, actual: "ResourceUsage") -> list[str]:
        """Return list of budget categories exceeded by actual usage."""
        exceeded = []
        if self.cpu_seconds is not None and actual.cpu_seconds is not None:
            if actual.cpu_seconds > self.cpu_seconds:
                exceeded.append(f"cpu_seconds ({actual.cpu_seconds} > {self.cpu_seconds})")
        if self.peak_rss_bytes is not None and actual.peak_rss_bytes is not None:
            if actual.peak_rss_bytes > self.peak_rss_bytes:
                exceeded.append(f"peak_rss_bytes ({actual.peak_rss_bytes} > {self.peak_rss_bytes})")
        if self.elapsed_seconds is not None and actual.elapsed_seconds is not None:
            if actual.elapsed_seconds > self.elapsed_seconds:
                exceeded.append(f"elapsed_seconds ({actual.elapsed_seconds} > {self.elapsed_seconds})")
        if self.local_storage_bytes is not None and actual.local_storage_bytes is not None:
            if actual.local_storage_bytes > self.local_storage_bytes:
                exceeded.append(f"local_storage_bytes ({actual.local_storage_bytes} > {self.local_storage_bytes})")
        if self.external_storage_bytes is not None and actual.external_storage_bytes is not None:
            if actual.external_storage_bytes > self.external_storage_bytes:
                exceeded.append(f"external_storage_bytes ({actual.external_storage_bytes} > {self.external_storage_bytes})")
        if self.api_calls is not None and actual.api_calls is not None:
            if actual.api_calls > self.api_calls:
                exceeded.append(f"api_calls ({actual.api_calls} > {self.api_calls})")
        if self.api_cost_usd is not None and actual.api_cost_usd is not None:
            if actual.api_cost_usd > self.api_cost_usd:
                exceeded.append(f"api_cost_usd ({actual.api_cost_usd} > {self.api_cost_usd})")
        if self.model_tokens is not None and actual.model_tokens is not None:
            if actual.model_tokens > self.model_tokens:
                exceeded.append(f"model_tokens ({actual.model_tokens} > {self.model_tokens})")
        if self.render_compute_seconds is not None and actual.render_compute_seconds is not None:
            if actual.render_compute_seconds > self.render_compute_seconds:
                exceeded.append(f"render_compute_seconds ({actual.render_compute_seconds} > {self.render_compute_seconds})")
        return exceeded


@dataclass(frozen=True)
class ResourceUsage:
    """Actual resource consumption for one mission."""

    cpu_seconds: Optional[float] = None
    peak_rss_bytes: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    local_storage_bytes: Optional[float] = None
    external_storage_bytes: Optional[float] = None
    api_calls: Optional[int] = None
    api_cost_usd: Optional[float] = None
    model_tokens: Optional[int] = None
    render_compute_seconds: Optional[float] = None
    measured_at: str = ""  # ISO 8601 timestamp

    def percentage_of_budget(self, budget: ResourceBudget) -> dict[str, Optional[float]]:
        """For each budget item, return (actual / budget * 100) or None if unbounded."""
        result = {}
        if budget.cpu_seconds is not None and self.cpu_seconds is not None:
            result["cpu_seconds"] = (self.cpu_seconds / budget.cpu_seconds) * 100
        if budget.peak_rss_bytes is not None and self.peak_rss_bytes is not None:
            result["peak_rss_bytes"] = (self.peak_rss_bytes / budget.peak_rss_bytes) * 100
        if budget.elapsed_seconds is not None and self.elapsed_seconds is not None:
            result["elapsed_seconds"] = (self.elapsed_seconds / budget.elapsed_seconds) * 100
        if budget.local_storage_bytes is not None and self.local_storage_bytes is not None:
            result["local_storage_bytes"] = (self.local_storage_bytes / budget.local_storage_bytes) * 100
        if budget.external_storage_bytes is not None and self.external_storage_bytes is not None:
            result["external_storage_bytes"] = (self.external_storage_bytes / budget.external_storage_bytes) * 100
        if budget.api_calls is not None and self.api_calls is not None:
            result["api_calls"] = (self.api_calls / budget.api_calls) * 100
        if budget.api_cost_usd is not None and self.api_cost_usd is not None:
            result["api_cost_usd"] = (self.api_cost_usd / budget.api_cost_usd) * 100
        if budget.model_tokens is not None and self.model_tokens is not None:
            result["model_tokens"] = (self.model_tokens / budget.model_tokens) * 100
        if budget.render_compute_seconds is not None and self.render_compute_seconds is not None:
            result["render_compute_seconds"] = (self.render_compute_seconds / budget.render_compute_seconds) * 100
        return result


# Policy-derived default budgets for common mission types.

DEFAULT_ANALYSIS_BUDGET = ResourceBudget(
    cpu_seconds=30.0,
    peak_rss_bytes=500_000_000,  # 500 MB
    elapsed_seconds=120.0,  # 2 minutes
    local_storage_bytes=100_000_000,  # 100 MB
    api_calls=10,
    api_cost_usd=1.0,
    model_tokens=10_000,
)

DEFAULT_RESEARCH_BUDGET = ResourceBudget(
    cpu_seconds=120.0,
    peak_rss_bytes=2_000_000_000,  # 2 GB
    elapsed_seconds=600.0,  # 10 minutes
    local_storage_bytes=500_000_000,  # 500 MB
    api_calls=50,
    api_cost_usd=5.0,
    model_tokens=50_000,
)

DEFAULT_MEDIA_PRODUCTION_BUDGET = ResourceBudget(
    cpu_seconds=300.0,  # rendering can be expensive
    peak_rss_bytes=4_000_000_000,  # 4 GB
    elapsed_seconds=1800.0,  # 30 minutes
    external_storage_bytes=5_000_000_000,  # 5 GB
    api_calls=20,
    api_cost_usd=10.0,
    model_tokens=100_000,
    render_compute_seconds=600.0,
)

# Budget for executive kernel's own operations (checking, scheduling, etc.)
DEFAULT_EXECUTIVE_KERNEL_BUDGET = ResourceBudget(
    cpu_seconds=5.0,
    peak_rss_bytes=200_000_000,  # 200 MB
    elapsed_seconds=30.0,
    api_calls=5,
    api_cost_usd=0.1,
)
