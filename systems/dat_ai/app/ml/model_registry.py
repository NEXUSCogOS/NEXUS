"""Model registry: version control and metadata storage.

Records all trained models with:
- Version (v1.0, v2.0, v2.1, ...)
- Training date and git commit
- Dataset version (manifest hash)
- Evaluation metrics + baseline comparison
- Promotion status (draft, submitted, approved, rejected, promoted)
- Checksum (SHA256 for integrity)

No model is deployed without registry entry + promotion approval.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class PromotionStatus(str, Enum):
    """Model promotion workflow status."""

    DRAFT = "draft"  # Trained, not submitted to gate
    SUBMITTED = "submitted"  # Submitted to promotion gate
    APPROVED = "approved"  # Gate passed + human approved
    REJECTED = "rejected"  # Gate failed or human rejected
    PROMOTED = "promoted"  # Live in production
    DEPRECATED = "deprecated"  # Replaced by newer version


@dataclass
class ModelMetadata:
    """Complete model metadata."""

    version: str  # e.g., "v2.0"
    model_type: str  # e.g., "MultispectralResNet50"
    input_channels: int  # e.g., 4 (B02, B03, B04, B08)
    num_classes: int  # e.g., 5
    class_names: list[str]  # ["urban", "agricultural", "water", "forest", "vacant"]

    training_date: str  # ISO timestamp
    git_commit: str  # Training code commit hash
    git_branch: str  # Branch used for training
    dataset_version: str  # Manifest hash or version ID

    # Metrics
    overall_accuracy: float
    macro_f1: float
    weighted_f1: float
    macro_precision: float
    macro_recall: float
    per_class_f1: dict[str, float]  # {"urban": 0.75, ...}

    # Baseline comparison
    accuracy_delta_spectral: float  # Trained - spectral indices baseline
    f1_delta_spectral: float

    # Files
    model_checkpoint: str  # Path or S3 URI
    model_checksum: str  # SHA256 of model.pth
    config_path: str  # Path to training config
    provenance_path: str  # Path to full provenance JSON

    # Promotion
    promotion_status: PromotionStatus = PromotionStatus.DRAFT
    promotion_date: Optional[str] = None
    promotion_approved_by: Optional[str] = None
    promotion_reason: Optional[str] = None

    # Lifecycle
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """Set timestamps if not provided."""
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        """Export as dictionary."""
        d = asdict(self)
        d["promotion_status"] = self.promotion_status.value
        return d

    def can_be_deployed(self) -> bool:
        """Check if model can be deployed (promoted + approved)."""
        return self.promotion_status == PromotionStatus.PROMOTED


class ModelRegistry:
    """Versioned registry with optional durable JSON persistence.

    The JSON backend is intentionally small and append-friendly for local
    experiments. Production deployments should replace it with the same
    schema in Postgres, but must preserve the immutable metadata contract.
    """

    def __init__(self, storage_path: Optional[Path | str] = None):
        """Initialize a registry, loading an existing durable record if set."""
        self.storage_path = Path(storage_path) if storage_path else None
        self.models: dict[str, ModelMetadata] = {}
        self.version_history: list[str] = []  # Ordered list of version IDs
        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self) -> None:
        """Load registry state from its durable JSON representation."""
        payload = json.loads(self.storage_path.read_text())
        for raw in payload.get("models", []):
            raw["promotion_status"] = PromotionStatus(raw["promotion_status"])
            metadata = ModelMetadata(**raw)
            self.models[metadata.version] = metadata
        self.version_history = list(payload.get("version_history", self.models))

    def _persist(self) -> None:
        """Persist a complete, deterministic registry snapshot."""
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version_history": self.version_history,
            "models": [self.models[v].to_dict() for v in self.version_history],
        }
        temporary = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temporary.replace(self.storage_path)

    def register(self, metadata: ModelMetadata) -> None:
        """
        Register a new model.

        Args:
            metadata: ModelMetadata to register

        Raises:
            ValueError if version already exists
        """
        if metadata.version in self.models:
            raise ValueError(f"Model version {metadata.version} already registered")

        self.models[metadata.version] = metadata
        self.version_history.append(metadata.version)
        self._persist()

    def get(self, version: str) -> Optional[ModelMetadata]:
        """Get model metadata by version."""
        return self.models.get(version)

    def promote(
        self,
        version: str,
        approved_by: str,
        reason: str,
    ) -> ModelMetadata:
        """
        Promote model to production.

        Args:
            version: Model version
            approved_by: Approver name
            reason: Promotion justification

        Returns:
            Updated ModelMetadata

        Raises:
            ValueError if version not found or already promoted
        """
        if version not in self.models:
            raise ValueError(f"Model version {version} not found")

        metadata = self.models[version]
        if metadata.promotion_status == PromotionStatus.PROMOTED:
            raise ValueError(f"Model {version} is already promoted")

        metadata.promotion_status = PromotionStatus.PROMOTED
        metadata.promotion_date = datetime.now(timezone.utc).isoformat()
        metadata.promotion_approved_by = approved_by
        metadata.promotion_reason = reason
        metadata.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()

        return metadata

    def reject(
        self,
        version: str,
        rejected_by: str,
        reason: str,
    ) -> ModelMetadata:
        """
        Reject model promotion.

        Args:
            version: Model version
            rejected_by: Person rejecting
            reason: Rejection reason

        Returns:
            Updated ModelMetadata
        """
        if version not in self.models:
            raise ValueError(f"Model version {version} not found")

        metadata = self.models[version]
        metadata.promotion_status = PromotionStatus.REJECTED
        metadata.promotion_date = datetime.now(timezone.utc).isoformat()
        metadata.promotion_approved_by = rejected_by
        metadata.promotion_reason = reason
        metadata.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()

        return metadata

    def get_latest_promoted(self) -> Optional[ModelMetadata]:
        """Get latest promoted model (for inference)."""
        for version in reversed(self.version_history):
            metadata = self.models[version]
            if metadata.promotion_status == PromotionStatus.PROMOTED:
                return metadata
        return None

    def list_versions(self, status_filter: Optional[PromotionStatus] = None) -> list[str]:
        """
        List all versions, optionally filtered by status.

        Args:
            status_filter: Filter by promotion status (None = all)

        Returns:
            List of version strings
        """
        if status_filter is None:
            return self.version_history.copy()

        return [
            v for v in self.version_history
            if self.models[v].promotion_status == status_filter
        ]

    def get_summary(self) -> dict:
        """Get registry summary stats."""
        return {
            "total_models": len(self.models),
            "promoted": len(self.list_versions(PromotionStatus.PROMOTED)),
            "draft": len(self.list_versions(PromotionStatus.DRAFT)),
            "rejected": len(self.list_versions(PromotionStatus.REJECTED)),
            "latest_promoted": self.get_latest_promoted().version if self.get_latest_promoted() else None,
        }


def format_model_summary(metadata: ModelMetadata) -> str:
    """Format model metadata as readable summary."""
    lines = [
        "=" * 70,
        "MODEL REGISTRY ENTRY",
        "=" * 70,
        f"Version: {metadata.version}",
        f"Model: {metadata.model_type} ({metadata.input_channels} channels → {metadata.num_classes} classes)",
        f"Trained: {metadata.training_date}",
        f"Git: {metadata.git_commit[:8]}... ({metadata.git_branch})",
        f"Dataset: {metadata.dataset_version}",
        "",
        "Metrics:",
        f"  Overall Accuracy: {metadata.overall_accuracy:.4f}",
        f"  Macro F1:         {metadata.macro_f1:.4f}",
        f"  Weighted F1:      {metadata.weighted_f1:.4f}",
        f"  Macro Precision:  {metadata.macro_precision:.4f}",
        f"  Macro Recall:     {metadata.macro_recall:.4f}",
        "",
        "vs. Spectral Baseline:",
        f"  Accuracy delta:   {metadata.accuracy_delta_spectral:+.4f}",
        f"  F1 delta:         {metadata.f1_delta_spectral:+.4f}",
        "",
        f"Promotion Status: {metadata.promotion_status.value.upper()}",
        f"Deployable: {'✓ Yes' if metadata.can_be_deployed() else '✗ No'}",
        "=" * 70,
    ]
    return "\n".join(lines)


def main():
    """CLI entry point."""
    print("Model registry module; use ModelRegistry for version control")


if __name__ == "__main__":
    main()
