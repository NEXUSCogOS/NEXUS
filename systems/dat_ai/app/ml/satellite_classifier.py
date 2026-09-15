"""Sentinel-2 land-use classifier — loading, provenance audit, and gating.

AUDIT FINDING (2026-08-14, reproducible via ``cli.py check-classifier``):

    The shipped checkpoint ``satellite_classifier_v1.2.pth`` is a torchvision
    ResNet50 whose ``conv1.weight`` is **bit-identical** to the public
    ``IMAGENET1K_V1`` weights, with a freshly initialised 5-unit ``fc`` head
    (bias mean 0.0098, std 0.0110 — untouched Kaiming/uniform init).

    No domain training occurred. There is no training dataset, no label source,
    no validation split, no confusion matrix and no calibration. Its outputs on
    Sentinel-2 imagery are arbitrary.

    Additionally ``conv1`` accepts **3** channels, while the previous pipeline
    fed it an 11-channel array. Every real call would have raised — and the old
    ``classify_tile`` swallowed the exception and returned an all-zero class map
    with all-zero confidence, which the caller then persisted as 'urban'.

CONSEQUENCE: promotion status is ``UNTRAINED_DEVELOPMENT_ONLY``. This module
refuses to produce output that will be persisted as an observation unless the
loaded checkpoint is explicitly promoted. See docs/MODEL_CARD.md.

There is no dummy-model fallback in this file. A model that cannot load is an
error, not an opportunity to invent one.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.config import Settings, settings as default_settings
from app.satellite.errors import InferenceError, ModelNotPromoted

logger = logging.getLogger(__name__)

CLASSES = ("urban", "agricultural", "water", "forest", "vacant")
NUM_CLASSES = len(CLASSES)
INPUT_SIZE = 224

# Band order this model expects, matching preprocess.BAND_ORDER.
EXPECTED_BANDS = ("B02", "B03", "B04", "B08")
EXPECTED_CHANNELS = len(EXPECTED_BANDS)


class PromotionStatus(str, Enum):
    """How far a checkpoint may be trusted."""

    UNTRAINED_DEVELOPMENT_ONLY = "UNTRAINED_DEVELOPMENT_ONLY"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    PRODUCTION_PROMOTED = "PRODUCTION_PROMOTED"

    @property
    def may_persist_observations(self) -> bool:
        return self is PromotionStatus.PRODUCTION_PROMOTED


@dataclass
class ModelAudit:
    """Everything known about the loaded checkpoint's provenance."""

    model_version: str
    path: str
    exists: bool
    sha256: str | None
    architecture: str
    input_channels: int | None
    output_classes: int | None
    backbone_is_pristine_imagenet: bool | None
    head_appears_untrained: bool | None
    promotion_status: PromotionStatus
    findings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "path": self.path,
            "exists": self.exists,
            "sha256": self.sha256,
            "architecture": self.architecture,
            "input_channels": self.input_channels,
            "output_classes": self.output_classes,
            "expected_channels": EXPECTED_CHANNELS,
            "expected_bands": list(EXPECTED_BANDS),
            "classes": list(CLASSES),
            "backbone_is_pristine_imagenet": self.backbone_is_pristine_imagenet,
            "head_appears_untrained": self.head_appears_untrained,
            "promotion_status": self.promotion_status.value,
            "may_persist_observations": (
                self.promotion_status.may_persist_observations
            ),
            "findings": list(self.findings),
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state_dict_of(obj: Any) -> dict[str, torch.Tensor]:
    if hasattr(obj, "state_dict"):
        return obj.state_dict()
    if isinstance(obj, dict):
        for key in ("state_dict", "model_state_dict"):
            if key in obj and isinstance(obj[key], dict):
                return obj[key]
        return obj
    raise InferenceError(f"Unrecognised checkpoint object: {type(obj)}")


def _backbone_matches_imagenet(state: dict[str, torch.Tensor]) -> bool | None:
    """True if conv1 is byte-identical to public ImageNet ResNet50 weights."""
    if "conv1.weight" not in state:
        return None
    try:
        import torchvision.models as models

        reference = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    except Exception as exc:
        logger.warning("Could not fetch reference ImageNet weights: %s", exc)
        return None

    candidate = state["conv1.weight"]
    if candidate.shape != reference.conv1.weight.shape:
        return False
    return bool(torch.equal(candidate.cpu(), reference.conv1.weight.cpu()))


def _head_appears_untrained(state: dict[str, torch.Tensor]) -> bool | None:
    """Heuristic: a trained classifier head develops non-trivial bias spread.

    A freshly initialised nn.Linear(2048, 5) has bias ~ U(-1/sqrt(2048),
    +1/sqrt(2048)) => std around 0.013. A head that has seen gradient updates
    on real class-imbalanced data moves well away from that.
    """
    bias = state.get("fc.bias")
    if bias is None:
        return None
    std = float(bias.float().std())
    init_bound = 1.0 / (2048**0.5)
    expected_init_std = init_bound / (3**0.5) * 2  # std of U(-b, b) is b/sqrt(3)
    return std < expected_init_std * 1.5


def audit_checkpoint(
    path: Path, model_version: str, promoted_flag: bool
) -> ModelAudit:
    """Inspect a checkpoint and decide how far it may be trusted."""
    findings: list[str] = []
    path = Path(path)

    if not path.exists():
        return ModelAudit(
            model_version=model_version,
            path=str(path),
            exists=False,
            sha256=None,
            architecture="unknown",
            input_channels=None,
            output_classes=None,
            backbone_is_pristine_imagenet=None,
            head_appears_untrained=None,
            promotion_status=PromotionStatus.UNTRAINED_DEVELOPMENT_ONLY,
            findings=[f"Checkpoint does not exist at {path}"],
        )

    # Security boundary: public/reproducible checkpoints are data-only.
    # Never deserialize arbitrary Python model objects during audit.
    try:
        obj = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise InferenceError(
            "Checkpoint could not be loaded through the restricted "
            "weights-only deserialization boundary. Convert legacy "
            "full-object checkpoints to a state_dict before use."
        ) from exc

    state = _state_dict_of(obj)
    architecture = "state_dict"

    conv1 = state.get("conv1.weight")
    fc_weight = state.get("fc.weight")
    input_channels = int(conv1.shape[1]) if conv1 is not None else None
    output_classes = int(fc_weight.shape[0]) if fc_weight is not None else None

    pristine = _backbone_matches_imagenet(state)
    untrained_head = _head_appears_untrained(state)

    if pristine:
        findings.append(
            "conv1.weight is bit-identical to torchvision IMAGENET1K_V1 — the "
            "backbone has received no domain training on satellite imagery."
        )
    if untrained_head:
        findings.append(
            "fc.bias statistics are consistent with fresh initialisation — the "
            "5-class head has not been trained."
        )
    if input_channels is not None and input_channels != EXPECTED_CHANNELS:
        findings.append(
            f"Checkpoint accepts {input_channels} input channels but the "
            f"preprocessing contract supplies {EXPECTED_CHANNELS} "
            f"({', '.join(EXPECTED_BANDS)}). conv1 must be adapted; any such "
            f"adaptation is itself untrained."
        )
    if output_classes is not None and output_classes != NUM_CLASSES:
        findings.append(
            f"Checkpoint emits {output_classes} classes, expected {NUM_CLASSES}."
        )

    is_untrained = bool(pristine) or bool(untrained_head)
    if is_untrained:
        status = PromotionStatus.UNTRAINED_DEVELOPMENT_ONLY
        if promoted_flag:
            findings.append(
                "MODEL_PROMOTED_FOR_PRODUCTION=true was set, but the checkpoint "
                "audit shows it is untrained. The flag is overridden — "
                "configuration cannot promote a model the evidence rejects."
            )
    elif promoted_flag:
        status = PromotionStatus.PRODUCTION_PROMOTED
    else:
        status = PromotionStatus.RESEARCH_ONLY
        findings.append(
            "Checkpoint shows evidence of training but has not been promoted "
            "(MODEL_PROMOTED_FOR_PRODUCTION is not true)."
        )

    return ModelAudit(
        model_version=model_version,
        path=str(path),
        exists=True,
        sha256=_sha256(path),
        architecture=architecture,
        input_channels=input_channels,
        output_classes=output_classes,
        backbone_is_pristine_imagenet=pristine,
        head_appears_untrained=untrained_head,
        promotion_status=status,
        findings=findings,
    )


@dataclass
class InferenceResult:
    """Model output plus the provenance needed to defend it."""

    class_map: np.ndarray
    confidence_map: np.ndarray
    model_version: str
    model_sha256: str | None
    promotion_status: PromotionStatus
    classes: tuple[str, ...]
    patch_size: int
    stride: int


class SatelliteClassifier:
    """ResNet-based land-use classifier with explicit promotion gating."""

    def __init__(self, config: Settings | None = None):
        self.settings = config or default_settings
        self.classes = CLASSES
        self.model_version = self.settings.model_version
        self.device = torch.device("cpu")
        self.audit = audit_checkpoint(
            self.settings.model_path,
            self.settings.model_version,
            self.settings.model_promoted_for_production,
        )
        self.model: torch.nn.Module | None = None

    # ---- loading --------------------------------------------------------

    def load(self) -> SatelliteClassifier:
        """Load weights. Raises rather than substituting a dummy model."""
        if not self.audit.exists:
            raise InferenceError(
                f"Model checkpoint not found: {self.settings.model_path}"
            )

        # Security boundary: executable/full-object PyTorch checkpoints are
        # prohibited. Architecture is reconstructed locally and only tensor
        # state is accepted from the checkpoint.
        try:
            obj = torch.load(
                self.settings.model_path,
                map_location=self.device,
                weights_only=True,
            )
        except Exception as exc:
            raise InferenceError(
                "Checkpoint could not be loaded through the restricted "
                "weights-only deserialization boundary. Convert legacy "
                "full-object checkpoints to a state_dict before use."
            ) from exc

        import torchvision.models as models

        model = models.resnet50(weights=None)
        model.fc = torch.nn.Linear(2048, NUM_CLASSES)
        model.load_state_dict(_state_dict_of(obj))

        model = self._adapt_input_channels(model)
        model.eval()
        model.to(self.device)
        self.model = model

        logger.info(
            "Loaded classifier %s (%s) status=%s",
            self.model_version,
            self.audit.architecture,
            self.audit.promotion_status.value,
        )
        for finding in self.audit.findings:
            logger.warning("MODEL AUDIT: %s", finding)
        return self

    def _adapt_input_channels(self, model: torch.nn.Module) -> torch.nn.Module:
        """Widen conv1 from 3 to 4 channels for B02/B03/B04/B08.

        The new NIR channel is initialised from the mean of the RGB filters.
        This is a standard adaptation, but it is *not* training: the adapted
        layer has never seen a labelled Sentinel-2 sample. It exists so that the
        inference plumbing is exercisable end-to-end under commissioning; it
        does not make the model valid.
        """
        conv1 = getattr(model, "conv1", None)
        if conv1 is None or conv1.in_channels == EXPECTED_CHANNELS:
            return model

        if conv1.in_channels != 3:
            raise InferenceError(
                f"Cannot adapt conv1 from {conv1.in_channels} to "
                f"{EXPECTED_CHANNELS} channels"
            )

        adapted = torch.nn.Conv2d(
            EXPECTED_CHANNELS,
            conv1.out_channels,
            kernel_size=conv1.kernel_size,
            stride=conv1.stride,
            padding=conv1.padding,
            bias=conv1.bias is not None,
        )
        with torch.no_grad():
            adapted.weight[:, :3] = conv1.weight
            adapted.weight[:, 3:] = conv1.weight.mean(dim=1, keepdim=True)
            if conv1.bias is not None:
                adapted.bias.copy_(conv1.bias)

        model.conv1 = adapted
        logger.warning(
            "conv1 widened 3->%d channels by RGB-mean initialisation. "
            "This adaptation is UNTRAINED.",
            EXPECTED_CHANNELS,
        )
        return model

    # ---- gating ---------------------------------------------------------

    def require_promoted(self, purpose: str = "persisted observation") -> None:
        """Raise unless this checkpoint may back a persisted observation."""
        if not self.audit.promotion_status.may_persist_observations:
            raise ModelNotPromoted(
                f"Refusing {purpose}: model {self.model_version} has promotion "
                f"status {self.audit.promotion_status.value}.\n"
                + "\n".join(f"  - {f}" for f in self.audit.findings)
                + "\nSee docs/MODEL_CARD.md. Persisting output from an "
                "untrained model would fabricate satellite intelligence."
            )

    # ---- inference ------------------------------------------------------

    def classify(
        self,
        data: np.ndarray,
        valid_mask: np.ndarray | None = None,
        patch_size: int = INPUT_SIZE,
        stride: int | None = None,
        batch_size: int = 16,
    ) -> InferenceResult:
        """Run sliding-window inference over a (C, H, W) reflectance array.

        Returns per-pixel class indices and confidences. Probabilities from
        overlapping windows are averaged before the argmax, so the result does
        not depend on window visitation order — the previous implementation
        overwrote whole patches and was order-dependent.
        """
        if self.model is None:
            raise InferenceError("Classifier not loaded; call load() first")

        if data.ndim != 3:
            raise InferenceError(
                f"Expected (C, H, W) input, got shape {data.shape}"
            )
        channels, height, width = data.shape
        if channels != EXPECTED_CHANNELS:
            raise InferenceError(
                f"Model expects {EXPECTED_CHANNELS} channels "
                f"({', '.join(EXPECTED_BANDS)}), got {channels}"
            )
        if height < patch_size or width < patch_size:
            raise InferenceError(
                f"Input {height}x{width} is smaller than the {patch_size} "
                f"patch size"
            )

        stride = stride or patch_size // 2

        prob_sum = np.zeros((NUM_CLASSES, height, width), dtype=np.float32)
        count = np.zeros((height, width), dtype=np.float32)

        rows = list(range(0, height - patch_size + 1, stride))
        cols = list(range(0, width - patch_size + 1, stride))
        # Ensure the trailing edge is covered.
        if rows and rows[-1] + patch_size < height:
            rows.append(height - patch_size)
        if cols and cols[-1] + patch_size < width:
            cols.append(width - patch_size)

        coordinates = [(r, c) for r in rows for c in cols]
        tensor_source = torch.from_numpy(np.ascontiguousarray(data))

        with torch.no_grad():
            for start in range(0, len(coordinates), batch_size):
                chunk = coordinates[start : start + batch_size]
                batch = torch.stack(
                    [
                        tensor_source[:, r : r + patch_size, c : c + patch_size]
                        for r, c in chunk
                    ]
                ).to(self.device)

                probs = torch.softmax(self.model(batch), dim=1).cpu().numpy()

                for (r, c), patch_probs in zip(chunk, probs):
                    prob_sum[:, r : r + patch_size, c : c + patch_size] += (
                        patch_probs[:, None, None]
                    )
                    count[r : r + patch_size, c : c + patch_size] += 1.0

        covered = count > 0
        if not covered.any():
            raise InferenceError("Sliding window covered no pixels")

        prob_sum[:, covered] /= count[covered]

        class_map = np.argmax(prob_sum, axis=0).astype(np.uint8)
        confidence_map = np.max(prob_sum, axis=0).astype(np.float32)

        # Pixels never covered, or masked out upstream, carry zero confidence
        # so downstream vectorisation excludes them explicitly.
        confidence_map[~covered] = 0.0
        if valid_mask is not None:
            confidence_map[~valid_mask] = 0.0

        return InferenceResult(
            class_map=class_map,
            confidence_map=confidence_map,
            model_version=self.model_version,
            model_sha256=self.audit.sha256,
            promotion_status=self.audit.promotion_status,
            classes=self.classes,
            patch_size=patch_size,
            stride=stride,
        )

    def get_class_name(self, index: int) -> str:
        if 0 <= index < len(self.classes):
            return self.classes[index]
        raise InferenceError(f"Class index {index} out of range")

    def get_class_index(self, name: str) -> int:
        if name not in self.classes:
            raise InferenceError(f"Unknown class {name!r}")
        return self.classes.index(name)


_classifier: SatelliteClassifier | None = None


def get_classifier(config: Settings | None = None) -> SatelliteClassifier:
    """Return the process-wide classifier, loading it on first use."""
    global _classifier
    if _classifier is None:
        _classifier = SatelliteClassifier(config).load()
    return _classifier


def load_classifier(config: Settings | None = None) -> SatelliteClassifier:
    """Load a fresh classifier instance (no caching)."""
    return SatelliteClassifier(config).load()


def audit_only(config: Settings | None = None) -> ModelAudit:
    """Audit the configured checkpoint without loading it for inference."""
    cfg = config or default_settings
    return audit_checkpoint(
        cfg.model_path, cfg.model_version, cfg.model_promoted_for_production
    )
