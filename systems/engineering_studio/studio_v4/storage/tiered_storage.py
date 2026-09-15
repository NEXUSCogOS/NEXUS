"""Tier Manager: classification and configuration for the 3-tier storage system.

Tier 1 (hot):  local, CPU-adjacent disk. Recently touched / small files live here.
Tier 2 (warm): external volume. Aged-but-still-wanted files, lightly compressed.
Tier 3 (cold): iCloud Drive (or equivalent sync target). Old, rarely-touched
               files, heavily compressed.

Classification is driven entirely by real, measured facts about a file —
its mtime-derived age and its on-disk size via ``os.stat`` — never by
estimates or self-reported metadata.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Tier(str, Enum):
    """The three storage tiers."""

    TIER_1_HOT = "tier1_hot"
    TIER_2_WARM = "tier2_warm"
    TIER_3_COLD = "tier3_cold"


@dataclass(frozen=True)
class TierConfig:
    """Configuration for a single storage tier."""

    tier: Tier
    root_path: Path
    min_age_days: float
    max_size_bytes: int | None = None
    compress: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", Path(self.root_path))


@dataclass
class FileDescriptor:
    """Real, measured facts about a file, used for tier classification."""

    path: Path
    size_bytes: int
    mtime: float
    current_tier: Tier = Tier.TIER_1_HOT

    @classmethod
    def from_path(cls, path: str | Path, current_tier: Tier = Tier.TIER_1_HOT) -> "FileDescriptor":
        p = Path(path)
        st = os.stat(p)
        return cls(path=p, size_bytes=st.st_size, mtime=st.st_mtime, current_tier=current_tier)

    @property
    def age_days(self) -> float:
        return max(0.0, (time.time() - self.mtime) / 86400.0)


# Default tier layout for this NEXUS installation:
#   Tier 1: repo-local (hot, CPU-adjacent)
#   Tier 2: /Volumes/NEXUS (external, warm)
#   Tier 3: iCloud Drive (cold archive)
DEFAULT_TIER_ROOTS: dict[Tier, Path] = {
    Tier.TIER_1_HOT: Path.home() / "NEXUS" / ".storage_tiers" / "tier1_hot",
    Tier.TIER_2_WARM: Path("/Volumes/NEXUS/storage_tiers/tier2_warm"),
    Tier.TIER_3_COLD: Path.home()
    / "Library"
    / "Mobile Documents"
    / "com~apple~CloudDocs"
    / "nexus_storage_tier3_cold",
}


class TierManager:
    """Classifies files into tiers and exposes tier configuration.

    Thresholds are age-based by default (small, recently-touched files stay
    hot; aged files migrate warm, then cold), with an optional size override
    so very large files can be pushed to a colder tier sooner regardless of
    age — the "size-based migration" path required by the lifecycle manager.
    """

    def __init__(
        self,
        tier_roots: dict[Tier, Path] | None = None,
        *,
        warm_age_days: float = 30.0,
        cold_age_days: float = 90.0,
        large_file_bytes: int = 100 * 1024 * 1024,  # 100MB
    ) -> None:
        roots = dict(DEFAULT_TIER_ROOTS)
        if tier_roots:
            roots.update(tier_roots)
        self.tier_roots = roots
        self.warm_age_days = warm_age_days
        self.cold_age_days = cold_age_days
        self.large_file_bytes = large_file_bytes

        self._configs: dict[Tier, TierConfig] = {
            Tier.TIER_1_HOT: TierConfig(
                tier=Tier.TIER_1_HOT,
                root_path=roots[Tier.TIER_1_HOT],
                min_age_days=0.0,
                compress=False,
                description="CPU-hot local storage, no compression",
            ),
            Tier.TIER_2_WARM: TierConfig(
                tier=Tier.TIER_2_WARM,
                root_path=roots[Tier.TIER_2_WARM],
                min_age_days=warm_age_days,
                compress=True,
                description="External-warm storage, gzip/zip compression",
            ),
            Tier.TIER_3_COLD: TierConfig(
                tier=Tier.TIER_3_COLD,
                root_path=roots[Tier.TIER_3_COLD],
                min_age_days=cold_age_days,
                compress=True,
                description="iCloud-cold archive, maximum compression",
            ),
        }

    def get_tier_config(self, tier: Tier) -> TierConfig:
        return self._configs[tier]

    def classify_file(self, descriptor: FileDescriptor) -> Tier:
        """Determine which tier a file belongs in, from real measured facts.

        Rule: age dominates (older -> colder), but an oversized file is
        bumped at least to Tier 2 regardless of age, since large files are
        expensive to keep hot even when fresh.
        """
        if descriptor.age_days >= self.cold_age_days:
            return Tier.TIER_3_COLD
        if descriptor.age_days >= self.warm_age_days:
            return Tier.TIER_2_WARM
        if descriptor.size_bytes >= self.large_file_bytes:
            return Tier.TIER_2_WARM
        return Tier.TIER_1_HOT

    def should_migrate(self, descriptor: FileDescriptor) -> bool:
        """True if the file's classified tier differs from its current tier
        and is a "forward" migration (hot -> warm -> cold), never backward.
        """
        target = self.classify_file(descriptor)
        tier_order = [Tier.TIER_1_HOT, Tier.TIER_2_WARM, Tier.TIER_3_COLD]
        return tier_order.index(target) > tier_order.index(descriptor.current_tier)

    def target_path_for(self, descriptor: FileDescriptor, tier: Tier) -> Path:
        """Compute the destination path for a file being migrated to `tier`,
        preserving its relative structure under the Tier 1 root when possible.
        """
        config = self.get_tier_config(tier)
        try:
            rel = descriptor.path.relative_to(self._configs[Tier.TIER_1_HOT].root_path)
        except ValueError:
            rel = Path(descriptor.path.name)
        return config.root_path / rel
