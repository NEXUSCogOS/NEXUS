"""Typed failures for the satellite pipeline.

Every failure is classified. ``failure_class`` is persisted to
``satellite_ingest_log`` so that an operator can distinguish "the catalogue was
down" from "we have no credentials" from "the raster was corrupt" without
reading free-text logs.
"""

from __future__ import annotations


class SatelliteError(RuntimeError):
    """Base class for all satellite pipeline failures."""

    failure_class = "unknown"


class CatalogueUnavailable(SatelliteError):
    """The STAC catalogue could not be reached or returned an error."""

    failure_class = "catalogue_unavailable"


class NoProductsFound(SatelliteError):
    """The catalogue responded correctly but matched no products."""

    failure_class = "no_products_found"


class CredentialsMissing(SatelliteError):
    """A required credential is absent. Never a reason to fabricate data."""

    failure_class = "credentials_missing"


class AcquisitionFailed(SatelliteError):
    """An asset could not be downloaded or failed integrity verification."""

    failure_class = "acquisition_failed"


class IntegrityError(SatelliteError):
    """A downloaded asset did not match its expected size/checksum."""

    failure_class = "integrity_error"


class RasterError(SatelliteError):
    """A raster could not be decoded, or its georeferencing is unusable."""

    failure_class = "raster_error"


class PreprocessingError(SatelliteError):
    """Band alignment / masking / normalisation failed."""

    failure_class = "preprocessing_error"


class ModelNotPromoted(SatelliteError):
    """Inference was requested from a model not cleared for this runtime mode."""

    failure_class = "model_not_promoted"


class InferenceError(SatelliteError):
    """The model failed to produce output."""

    failure_class = "inference_error"


class GeometryError(SatelliteError):
    """Vectorisation produced no valid georeferenced geometry."""

    failure_class = "geometry_error"


class ValidationSourceUnavailable(SatelliteError):
    """An external validation source (e.g. Planet) is not configured/reachable.

    This is reported, never substituted.
    """

    failure_class = "validation_source_unavailable"
