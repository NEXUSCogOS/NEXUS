"""Resource budget schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from budget.schema import DEFAULT_ANALYSIS_ONLY_BUDGET, UNBOUNDED_NOT_ALLOWED, ResourceBudget


def test_default_budget_is_valid_and_fully_bounded():
    b = DEFAULT_ANALYSIS_ONLY_BUDGET
    assert b.cpu_seconds > 0
    assert b.model_tokens == 0
    assert b.basis


def test_none_dimension_rejected_as_unbounded():
    with pytest.raises(ValidationError) as exc_info:
        ResourceBudget(
            cpu_seconds=None,
            memory_bytes=1,
            elapsed_seconds=1.0,
            local_storage_bytes=1,
            external_storage_bytes=0,
            api_cost_usd=0.0,
            model_tokens=0,
            basis="test",
        )
    assert UNBOUNDED_NOT_ALLOWED in str(exc_info.value)


def test_negative_dimension_rejected():
    with pytest.raises(ValidationError):
        ResourceBudget(
            cpu_seconds=-1.0,
            memory_bytes=1,
            elapsed_seconds=1.0,
            local_storage_bytes=1,
            external_storage_bytes=0,
            api_cost_usd=0.0,
            model_tokens=0,
            basis="test",
        )


def test_missing_basis_rejected():
    with pytest.raises(ValidationError):
        ResourceBudget(
            cpu_seconds=1.0,
            memory_bytes=1,
            elapsed_seconds=1.0,
            local_storage_bytes=1,
            external_storage_bytes=0,
            api_cost_usd=0.0,
            model_tokens=0,
            basis="",
        )


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ResourceBudget(
            cpu_seconds=1.0,
            memory_bytes=1,
            elapsed_seconds=1.0,
            local_storage_bytes=1,
            external_storage_bytes=0,
            api_cost_usd=0.0,
            model_tokens=0,
            basis="test",
            unbounded=True,
        )


def test_zero_is_a_valid_finite_bound():
    """Zero is a legitimate, explicit bound (e.g. 'no external storage
    permitted') -- distinct from None/unbounded."""
    b = ResourceBudget(
        cpu_seconds=0.0,
        memory_bytes=0,
        elapsed_seconds=0.0,
        local_storage_bytes=0,
        external_storage_bytes=0,
        api_cost_usd=0.0,
        model_tokens=0,
        basis="zero-budget test",
    )
    assert b.external_storage_bytes == 0
