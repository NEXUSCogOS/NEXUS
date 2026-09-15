"""Regression test: an untrained checkpoint must never be promotable.

New file, DAT.AI Phase C, per mission section 10 ("Add a regression test
preventing untrained checkpoints from being promoted as validated domain
models"). Marked `unit`: loads the real checkpoint file from disk (a local
file read, no network/database/credentials involved) and runs the donor's
own `audit_checkpoint()` function against it -- this is the same function
independently exercised during Phase A+B's DATAI_MODEL_ARTIFACT_VERIFICATION.md,
now captured as a permanent regression rather than a one-off manual check.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.ml.satellite_classifier import PromotionStatus, audit_checkpoint

pytestmark = pytest.mark.unit


def test_real_checkpoint_is_confirmed_untrained():
    """Ground truth this test depends on: as of Phase C, the only checkpoint
    present is bit-identical to stock ImageNet weights with a fresh head.
    If this ever becomes false because someone genuinely trained the model,
    this specific assertion should be updated -- but the promotion-blocking
    behavior below must never be weakened regardless."""
    audit = audit_checkpoint(
        settings.model_path, settings.model_version, promoted_flag=False
    )
    if not audit.exists:
        pytest.skip("checkpoint file not present in this environment")
    assert audit.promotion_status == PromotionStatus.UNTRAINED_DEVELOPMENT_ONLY


def test_promoted_flag_true_does_not_override_untrained_evidence():
    """The core fail-closed guarantee: setting MODEL_PROMOTED_FOR_PRODUCTION
    (promoted_flag=True) must NOT be able to force an untrained checkpoint's
    status to PRODUCTION_PROMOTED. Configuration cannot promote a model the
    evidence rejects."""
    audit = audit_checkpoint(
        settings.model_path, settings.model_version, promoted_flag=True
    )
    if not audit.exists:
        pytest.skip("checkpoint file not present in this environment")
    assert audit.promotion_status != PromotionStatus.PRODUCTION_PROMOTED
    assert audit.promotion_status == PromotionStatus.UNTRAINED_DEVELOPMENT_ONLY
    assert any(
        "overridden" in finding.lower() or "untrained" in finding.lower()
        for finding in audit.findings
    ), "audit must explicitly record that the promotion flag was overridden"


def test_untrained_status_may_not_persist_observations():
    """PromotionStatus.may_persist_observations must be False for the
    untrained state -- this is the property /readiness relies on to decide
    whether classifier output is safe to record as an observation."""
    assert PromotionStatus.UNTRAINED_DEVELOPMENT_ONLY.may_persist_observations is False


def test_model_status_register_reports_base_pretrained_not_trained():
    """Per mission section 10: the checkpoint must be classified
    BASE_PRETRAINED_WEIGHTS + UNTRAINED_DOMAIN_HEAD, never as TRAINED,
    VALIDATED, or PROMOTABLE anywhere the registry exposes status."""
    audit = audit_checkpoint(
        settings.model_path, settings.model_version, promoted_flag=False
    )
    if not audit.exists:
        pytest.skip("checkpoint file not present in this environment")
    assert audit.backbone_is_pristine_imagenet is True
    assert audit.head_appears_untrained is True
    # None of these forbidden labels may appear in any finding string.
    forbidden = ("VALIDATED", "PROMOTABLE", "PRODUCTION-READY", "TRAINED MODEL")
    for finding in audit.findings:
        for word in forbidden:
            assert word.lower() not in finding.lower(), (
                f"finding wrongly implies '{word}': {finding!r}"
            )
