"""Lifecycle Manager: age/size-based migration between storage tiers, plus
a daemon-style scheduler that runs migration cycles on an interval.

Every migration is a real filesystem operation (compress with
``CompressionPipeline``, move the compressed artifact, delete the
original) and every cycle records a real measured event to the
``EvidenceLedger`` via ``ResourceMeter`` — what moved, old size, new size,
compression ratio, and wall/CPU time spent doing it.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from systems.engineering_studio.studio_v3.observatory import (
    EvidenceLedger,
    ResourceMeter,
    measure_storage_delta,
)

from .compression_pipeline import CompressionPipeline
from .tiered_storage import FileDescriptor, Tier, TierManager


class LifecycleManager:
    """Scans a Tier-1 root, classifies files, and migrates the ones that
    have aged out (or grown too large) into the appropriate colder tier,
    compressing them on the way.
    """

    def __init__(
        self,
        tier_manager: TierManager,
        compression_pipeline: CompressionPipeline | None = None,
        ledger: EvidenceLedger | None = None,
        *,
        agent_name: str = "lifecycle_manager",
    ) -> None:
        self.tier_manager = tier_manager
        self.compression = compression_pipeline or CompressionPipeline()
        self.ledger = ledger
        self.agent_name = agent_name

    # -- scanning -----------------------------------------------------

    def _scan_root(self, root: Path, tier: Tier) -> list[FileDescriptor]:
        """Walk `root` and return a FileDescriptor for every file found,
        tagged with `tier` as its *current* (physical) location.

        `current_tier` must reflect where a file actually is on disk right
        now, not where classification thinks it belongs -- callers pass
        the tier that corresponds to the root being walked (e.g. the
        Tier-2 warm root when scanning for warm->cold escalation
        candidates). Never hardcode this to TIER_1_HOT for an arbitrary
        root: that previously made the warm->cold branch in
        migrate_sized_files unreachable dead code, since every scanned
        file looked like it was already Tier-1 regardless of which root
        it was actually found under.
        """
        descriptors: list[FileDescriptor] = []
        if not root.exists():
            return descriptors
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                fpath = Path(dirpath) / fname
                try:
                    descriptors.append(FileDescriptor.from_path(fpath, current_tier=tier))
                except OSError:
                    continue
        return descriptors

    def _scan_tier1(self, root: Path) -> list[FileDescriptor]:
        """Back-compat wrapper: scan `root` tagging every file Tier-1 hot.
        Only valid when `root` really is a Tier-1 root (e.g. from
        migrate_aged_files, which only ever walks the Tier-1 root)."""
        return self._scan_root(root, Tier.TIER_1_HOT)

    # -- migration ------------------------------------------------------

    def _migrate_one(self, descriptor: FileDescriptor, target_tier: Tier) -> dict:
        """Compress + move a single file into `target_tier`. Returns a
        measurement dict (also recorded to the ledger if one was given).
        """
        target_config = self.tier_manager.get_tier_config(target_tier)
        dest_dir = self.tier_manager.target_path_for(descriptor, target_tier).parent

        with ResourceMeter(label=f"migrate:{descriptor.path.name}") as meter:
            if target_config.compress:
                compression_result = self.compression.compress(descriptor.path, dest_dir)
                os.remove(descriptor.path)
                result = {
                    "file": str(descriptor.path),
                    "target_tier": target_tier.value,
                    "compressed": True,
                    **compression_result,
                }
            else:
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / descriptor.path.name
                before = measure_storage_delta(descriptor.path)
                shutil.move(str(descriptor.path), str(dest_path))
                after = measure_storage_delta(dest_path)
                result = {
                    "file": str(descriptor.path),
                    "target_tier": target_tier.value,
                    "compressed": False,
                    "compressed_path": str(dest_path),
                    "size_before": before["size_bytes"],
                    "size_after": after["size_bytes"],
                    "saved_bytes": before["size_bytes"] - after["size_bytes"],
                    "ratio": 0.0,
                }

        result["resource_cost"] = meter.result

        if self.ledger is not None:
            self.ledger.record_event(
                agent=self.agent_name,
                action="migrate_file",
                input_data={"path": str(descriptor.path), "target_tier": target_tier.value},
                output_data={k: v for k, v in result.items() if k != "resource_cost"},
                resource_cost=meter.result,
                files_modified=[str(descriptor.path), result.get("compressed_path", "")],
            )

        return result

    def migrate_aged_files(self, root_dir: str | Path | None = None) -> list[dict]:
        """Migrate every Tier-1 file whose classified tier (by real mtime
        age) is colder than Tier 1. Uses the TierManager's configured
        warm/cold age thresholds.
        """
        root = Path(root_dir) if root_dir else self.tier_manager.get_tier_config(Tier.TIER_1_HOT).root_path
        results: list[dict] = []
        for descriptor in self._scan_tier1(root):
            if not self.tier_manager.should_migrate(descriptor):
                continue
            target = self.tier_manager.classify_file(descriptor)
            results.append(self._migrate_one(descriptor, target))
        return results

    # Hard ceiling on how many files a single migrate_sized_files() call
    # will move, regardless of how far over `percent_full` the volume
    # still is. Without this, a disk that's severely over threshold (e.g.
    # a one-off huge backlog) could have its *entire* tree swept in one
    # uninterrupted pass -- a large, hard-to-abort filesystem operation
    # with no checkpointing. Bounding it means a single cycle does bounded
    # work and, if still over threshold afterward, the next scheduled
    # cycle (see MigrationScheduler) picks up where this one left off.
    DEFAULT_MAX_FILES_PER_CYCLE = 200

    def migrate_sized_files(
        self,
        root_dir: str | Path | None = None,
        *,
        percent_full: float = 85.0,
        disk_usage_fn: Callable[[str], tuple] | None = None,
        max_files_per_cycle: int = DEFAULT_MAX_FILES_PER_CYCLE,
    ) -> list[dict]:
        """If the Tier-1 volume is at or above `percent_full` percent
        utilization (measured via real ``shutil.disk_usage``), migrate the
        largest files first (oldest-among-largest as tiebreak) until usage
        drops back under the threshold, there is nothing left to move, or
        `max_files_per_cycle` files have been migrated (whichever comes
        first) -- this call never migrates more than `max_files_per_cycle`
        files, bounding the worst-case size of a single migration pass.

        Candidates are drawn from both the Tier-1 hot root (escalating
        hot -> warm) and the Tier-2 warm root (escalating warm -> cold),
        so a volume that's still over threshold after every hot candidate
        has moved can keep freeing space by pushing warm files to cold.
        """
        root = Path(root_dir) if root_dir else self.tier_manager.get_tier_config(Tier.TIER_1_HOT).root_path
        if not root.exists():
            return []

        usage_fn = disk_usage_fn or shutil.disk_usage
        usage = usage_fn(str(root))
        total, used = usage[0], usage[1]
        current_percent = (used / total * 100.0) if total else 0.0

        if current_percent < percent_full:
            return []

        warm_root = self.tier_manager.get_tier_config(Tier.TIER_2_WARM).root_path
        hot_descriptors = self._scan_root(root, Tier.TIER_1_HOT)
        warm_descriptors = self._scan_root(warm_root, Tier.TIER_2_WARM) if warm_root != root else []

        descriptors = sorted(
            hot_descriptors + warm_descriptors,
            key=lambda d: (-d.size_bytes, -d.age_days),
        )

        results: list[dict] = []
        for descriptor in descriptors:
            if len(results) >= max_files_per_cycle:
                break

            target = Tier.TIER_2_WARM if descriptor.current_tier == Tier.TIER_1_HOT else Tier.TIER_3_COLD
            result = self._migrate_one(descriptor, target)
            results.append(result)

            usage = usage_fn(str(root))
            total, used = usage[0], usage[1]
            current_percent = (used / total * 100.0) if total else 0.0
            if current_percent < percent_full:
                break

        return results

    def run_cycle(
        self,
        root_dir: str | Path | None = None,
        *,
        percent_full: float = 85.0,
    ) -> dict:
        """One full lifecycle pass: age-based migration, then size-based
        migration if still over threshold. Records a summary event.
        """
        with ResourceMeter(label="lifecycle_cycle") as meter:
            aged = self.migrate_aged_files(root_dir)
            sized = self.migrate_sized_files(root_dir, percent_full=percent_full)

        summary = {
            "aged_migrations": len(aged),
            "sized_migrations": len(sized),
            "total_saved_bytes": sum(r.get("saved_bytes", 0) for r in aged + sized),
            "files": [r["file"] for r in aged + sized],
        }

        if self.ledger is not None:
            self.ledger.record_event(
                agent=self.agent_name,
                action="run_cycle",
                output_data=summary,
                resource_cost=meter.result,
                files_modified=summary["files"],
            )

        summary["resource_cost"] = meter.result
        return summary


class MigrationScheduler:
    """Runs `LifecycleManager.run_cycle()` on an interval.

    Uses APScheduler's BackgroundScheduler when available (real cron-style
    scheduling); if apscheduler isn't installed, falls back to a plain
    ``threading.Timer`` re-arming loop so the daemon still functions with
    stdlib only.
    """

    def __init__(self, lifecycle_manager: LifecycleManager, *, interval_seconds: int = 86400) -> None:
        self.lifecycle_manager = lifecycle_manager
        self.interval_seconds = interval_seconds
        self._scheduler = None
        self._timer = None
        self._running = False

    def schedule_audit_cycle(self) -> None:  # pragma: no cover - naming symmetry w/ audit_loop
        """Alias for schedule_cycle(), kept for interface symmetry with the
        audit_loop scheduler in Stream C."""
        self.schedule_cycle()

    def schedule_cycle(self) -> None:
        """Start recurring execution of `run_cycle` every `interval_seconds`."""
        if self._running:
            return
        self._running = True

        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                self.lifecycle_manager.run_cycle,
                "interval",
                seconds=self.interval_seconds,
                id="lifecycle_cycle",
                next_run_time=None,  # first run scheduled below, not immediate
            )
            self._scheduler.start()
        except ImportError:
            self._arm_timer()

    def _arm_timer(self) -> None:
        import threading

        def _tick() -> None:
            if not self._running:
                return
            self.lifecycle_manager.run_cycle()
            self._arm_timer()

        self._timer = threading.Timer(self.interval_seconds, _tick)
        self._timer.daemon = True
        self._timer.start()

    def stop(self) -> None:
        self._running = False
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
