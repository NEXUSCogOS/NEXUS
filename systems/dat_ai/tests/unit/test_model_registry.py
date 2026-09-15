"""Tests for model registry."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestPromotionStatus:
    """Test promotion status enum."""

    def test_status_values(self):
        """Should have all required statuses."""
        from app.ml.model_registry import PromotionStatus

        assert PromotionStatus.DRAFT.value == "draft"
        assert PromotionStatus.APPROVED.value == "approved"
        assert PromotionStatus.PROMOTED.value == "promoted"


class TestModelMetadata:
    """Test model metadata."""

    def test_metadata_creation(self):
        """Should create metadata with all fields."""
        from app.ml.model_registry import ModelMetadata, PromotionStatus

        meta = ModelMetadata(
            version="v2.0",
            model_type="MultispectralResNet50",
            input_channels=4,
            num_classes=5,
            class_names=["urban", "agricultural", "water", "forest", "vacant"],
            training_date="2026-08-14T12:00:00",
            git_commit="abc123def456",
            git_branch="main",
            dataset_version="dataset_v1",
            overall_accuracy=0.75,
            macro_f1=0.72,
            weighted_f1=0.74,
            macro_precision=0.73,
            macro_recall=0.71,
            per_class_f1={"urban": 0.80},
            accuracy_delta_spectral=0.15,
            f1_delta_spectral=0.20,
            model_checkpoint="s3://bucket/v2.0.pth",
            model_checksum="abc123",
            config_path="s3://bucket/config.json",
            provenance_path="s3://bucket/provenance.json",
        )

        assert meta.version == "v2.0"
        assert meta.promotion_status == PromotionStatus.DRAFT
        assert meta.can_be_deployed() is False

    def test_metadata_to_dict(self):
        """Should serialize to dict."""
        from app.ml.model_registry import ModelMetadata

        meta = ModelMetadata(
            version="v2.0",
            model_type="ResNet50",
            input_channels=4,
            num_classes=5,
            class_names=["a", "b", "c", "d", "e"],
            training_date="2026-08-14T12:00:00",
            git_commit="abc123",
            git_branch="main",
            dataset_version="v1",
            overall_accuracy=0.75,
            macro_f1=0.72,
            weighted_f1=0.74,
            macro_precision=0.73,
            macro_recall=0.71,
            per_class_f1={},
            accuracy_delta_spectral=0.15,
            f1_delta_spectral=0.20,
            model_checkpoint="path",
            model_checksum="hash",
            config_path="path",
            provenance_path="path",
        )

        d = meta.to_dict()
        assert d["version"] == "v2.0"
        assert d["promotion_status"] == "draft"


class TestModelRegistry:
    """Test model registry."""

    def test_registry_init(self):
        """Registry should initialize empty."""
        from app.ml.model_registry import ModelRegistry

        registry = ModelRegistry()
        assert len(registry.models) == 0
        assert registry.get_latest_promoted() is None

    def test_registry_register(self):
        """Should register models."""
        from app.ml.model_registry import ModelRegistry, ModelMetadata

        registry = ModelRegistry()
        meta = ModelMetadata(
            version="v2.0",
            model_type="ResNet50",
            input_channels=4,
            num_classes=5,
            class_names=["a", "b", "c", "d", "e"],
            training_date="2026-08-14T12:00:00",
            git_commit="abc123",
            git_branch="main",
            dataset_version="v1",
            overall_accuracy=0.75,
            macro_f1=0.72,
            weighted_f1=0.74,
            macro_precision=0.73,
            macro_recall=0.71,
            per_class_f1={},
            accuracy_delta_spectral=0.15,
            f1_delta_spectral=0.20,
            model_checkpoint="path",
            model_checksum="hash",
            config_path="path",
            provenance_path="path",
        )

        registry.register(meta)
        assert registry.get("v2.0") is not None
        assert "v2.0" in registry.version_history

    def test_registry_persists_and_reloads(self, tmp_path):
        """A durable registry survives process reconstruction."""
        from app.ml.model_registry import ModelMetadata, ModelRegistry

        metadata = ModelMetadata(
            version="v2.0", model_type="ResNet50", input_channels=4, num_classes=5,
            class_names=["a", "b", "c", "d", "e"], training_date="2026-08-14",
            git_commit="abc123", git_branch="main", dataset_version="v1",
            overall_accuracy=0.75, macro_f1=0.72, weighted_f1=0.74,
            macro_precision=0.73, macro_recall=0.71, per_class_f1={},
            accuracy_delta_spectral=0.15, f1_delta_spectral=0.20,
            model_checkpoint="path", model_checksum="hash", config_path="config",
            provenance_path="provenance",
        )
        path = tmp_path / "registry.json"
        registry = ModelRegistry(path)
        registry.register(metadata)
        restored = ModelRegistry(path)
        assert restored.get("v2.0").dataset_version == "v1"
        assert restored.version_history == ["v2.0"]

    def test_registry_duplicate_register(self):
        """Should reject duplicate registration."""
        from app.ml.model_registry import ModelRegistry, ModelMetadata

        registry = ModelRegistry()
        meta = ModelMetadata(
            version="v2.0",
            model_type="ResNet50",
            input_channels=4,
            num_classes=5,
            class_names=["a", "b", "c", "d", "e"],
            training_date="2026-08-14T12:00:00",
            git_commit="abc123",
            git_branch="main",
            dataset_version="v1",
            overall_accuracy=0.75,
            macro_f1=0.72,
            weighted_f1=0.74,
            macro_precision=0.73,
            macro_recall=0.71,
            per_class_f1={},
            accuracy_delta_spectral=0.15,
            f1_delta_spectral=0.20,
            model_checkpoint="path",
            model_checksum="hash",
            config_path="path",
            provenance_path="path",
        )

        registry.register(meta)
        with pytest.raises(ValueError):
            registry.register(meta)

    def test_registry_promote(self):
        """Should promote models."""
        from app.ml.model_registry import ModelRegistry, ModelMetadata, PromotionStatus

        registry = ModelRegistry()
        meta = ModelMetadata(
            version="v2.0",
            model_type="ResNet50",
            input_channels=4,
            num_classes=5,
            class_names=["a", "b", "c", "d", "e"],
            training_date="2026-08-14T12:00:00",
            git_commit="abc123",
            git_branch="main",
            dataset_version="v1",
            overall_accuracy=0.75,
            macro_f1=0.72,
            weighted_f1=0.74,
            macro_precision=0.73,
            macro_recall=0.71,
            per_class_f1={},
            accuracy_delta_spectral=0.15,
            f1_delta_spectral=0.20,
            model_checkpoint="path",
            model_checksum="hash",
            config_path="path",
            provenance_path="path",
        )

        registry.register(meta)
        registry.promote("v2.0", "data_science_team", "Metrics exceed thresholds")

        promoted = registry.get("v2.0")
        assert promoted.promotion_status == PromotionStatus.PROMOTED
        assert promoted.can_be_deployed() is True

    def test_registry_get_latest_promoted(self):
        """Should return latest promoted model."""
        from app.ml.model_registry import ModelRegistry, ModelMetadata

        registry = ModelRegistry()

        for v in ["v2.0", "v2.1", "v2.2"]:
            meta = ModelMetadata(
                version=v,
                model_type="ResNet50",
                input_channels=4,
                num_classes=5,
                class_names=["a", "b", "c", "d", "e"],
                training_date="2026-08-14T12:00:00",
                git_commit="abc123",
                git_branch="main",
                dataset_version="v1",
                overall_accuracy=0.75,
                macro_f1=0.72,
                weighted_f1=0.74,
                macro_precision=0.73,
                macro_recall=0.71,
                per_class_f1={},
                accuracy_delta_spectral=0.15,
                f1_delta_spectral=0.20,
                model_checkpoint="path",
                model_checksum="hash",
                config_path="path",
                provenance_path="path",
            )
            registry.register(meta)

        registry.promote("v2.1", "team", "reason")

        latest = registry.get_latest_promoted()
        assert latest.version == "v2.1"

    def test_registry_list_versions(self):
        """Should list versions with filtering."""
        from app.ml.model_registry import ModelRegistry, ModelMetadata, PromotionStatus

        registry = ModelRegistry()

        for v in ["v2.0", "v2.1"]:
            meta = ModelMetadata(
                version=v,
                model_type="ResNet50",
                input_channels=4,
                num_classes=5,
                class_names=["a", "b", "c", "d", "e"],
                training_date="2026-08-14T12:00:00",
                git_commit="abc123",
                git_branch="main",
                dataset_version="v1",
                overall_accuracy=0.75,
                macro_f1=0.72,
                weighted_f1=0.74,
                macro_precision=0.73,
                macro_recall=0.71,
                per_class_f1={},
                accuracy_delta_spectral=0.15,
                f1_delta_spectral=0.20,
                model_checkpoint="path",
                model_checksum="hash",
                config_path="path",
                provenance_path="path",
            )
            registry.register(meta)

        registry.promote("v2.0", "team", "reason")

        draft_versions = registry.list_versions(PromotionStatus.DRAFT)
        promoted_versions = registry.list_versions(PromotionStatus.PROMOTED)

        assert len(draft_versions) == 1
        assert len(promoted_versions) == 1
        assert "v2.1" in draft_versions
        assert "v2.0" in promoted_versions

    def test_registry_summary(self):
        """Should generate registry summary."""
        from app.ml.model_registry import ModelRegistry, ModelMetadata

        registry = ModelRegistry()
        meta = ModelMetadata(
            version="v2.0",
            model_type="ResNet50",
            input_channels=4,
            num_classes=5,
            class_names=["a", "b", "c", "d", "e"],
            training_date="2026-08-14T12:00:00",
            git_commit="abc123",
            git_branch="main",
            dataset_version="v1",
            overall_accuracy=0.75,
            macro_f1=0.72,
            weighted_f1=0.74,
            macro_precision=0.73,
            macro_recall=0.71,
            per_class_f1={},
            accuracy_delta_spectral=0.15,
            f1_delta_spectral=0.20,
            model_checkpoint="path",
            model_checksum="hash",
            config_path="path",
            provenance_path="path",
        )

        registry.register(meta)
        registry.promote("v2.0", "team", "reason")

        summary = registry.get_summary()
        assert summary["total_models"] == 1
        assert summary["promoted"] == 1
        assert summary["latest_promoted"] == "v2.0"


def test_import():
    """Module should import without errors."""
    from app.ml import model_registry
    assert model_registry.ModelRegistry is not None
    assert model_registry.PromotionStatus is not None
