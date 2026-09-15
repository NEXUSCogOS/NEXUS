"""Three-tier storage subsystem (Engineering Studio v4, Phase 2 Stream A).

Tier 1 (hot):  local repo disk, CPU-adjacent, no compression.
Tier 2 (warm): external volume (/Volumes/NEXUS by default), lightly compressed.
Tier 3 (cold): iCloud Drive (or another sync target), heavily compressed archive.

Every migration and compression operation records real, measured evidence
(via ``ResourceMeter`` / ``measure_storage_delta``) to the shared
``EvidenceLedger`` — nothing here reports a size or ratio that wasn't
actually measured from bytes on disk.
"""

from .tiered_storage import FileDescriptor, Tier, TierConfig, TierManager
from .compression_pipeline import CompressionPipeline, CompressionStrategy
from .lifecycle_manager import LifecycleManager, MigrationScheduler

__all__ = [
    "Tier",
    "TierConfig",
    "FileDescriptor",
    "TierManager",
    "CompressionPipeline",
    "CompressionStrategy",
    "LifecycleManager",
    "MigrationScheduler",
]
