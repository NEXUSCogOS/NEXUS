"""
Satellite Intelligence Agent models
SQLAlchemy ORM for satellite_layers, changes, validations, etc.

Recovered into canonical NEXUS during DAT.AI Phase C (2026-08-27) from
NEXUS_LOCAL donor commit 359499f (systems/dat_ai/backend/app/models/satellite.py).
Two defects found during Phase A+B donor verification are fixed here; see the
inline "Phase C fix" comments and DATAI_DEFECT_REPAIR_EVIDENCE.md for the full
evidence chain. No other semantic change was made to this file.
"""

from datetime import datetime
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship
from .base import Base


class SatelliteProduct(Base):
    """A Sentinel-2 product discovered in the CDSE STAC catalogue.

    A row here means the catalogue described this product. It does NOT mean any
    imagery was downloaded — that is recorded per-file in ``SatelliteAsset``.
    Conflating the two is the defect this table exists to prevent.
    """

    __tablename__ = "satellite_products"

    id = Column(BigInteger, primary_key=True)
    stac_id = Column(String(255), nullable=False, unique=True, index=True)
    collection = Column(String(100), nullable=False)
    catalogue_url = Column(Text, nullable=False)
    mgrs_tile = Column(String(20), index=True)
    grid_code = Column(String(50))
    platform = Column(String(50))
    processing_level = Column(String(20))
    product_type = Column(String(50))
    sensed_at = Column(DateTime, nullable=False, index=True)
    cloud_cover = Column(Float)
    geom = Column(Geometry("POLYGON", srid=4326))
    bbox_min_lon = Column(Float)
    bbox_min_lat = Column(Float)
    bbox_max_lon = Column(Float)
    bbox_max_lat = Column(Float)
    aoi_name = Column(String(100), index=True)
    asset_inventory = Column(JSONB)
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Real foreign keys exist for both of these, so the ORM relationships are
    # relationally justified (unlike the removed SatelliteLayer.changes).
    assets = relationship(
        "SatelliteAsset",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    layers = relationship("SatelliteLayer", back_populates="source_product")

    def to_dict(self):
        return {
            "id": self.id,
            "stac_id": self.stac_id,
            "collection": self.collection,
            "mgrs_tile": self.mgrs_tile,
            "sensed_at": self.sensed_at.isoformat() if self.sensed_at else None,
            "cloud_cover": self.cloud_cover,
            "platform": self.platform,
            "processing_level": self.processing_level,
            "aoi_name": self.aoi_name,
            "discovered_at": (
                self.discovered_at.isoformat() if self.discovered_at else None
            ),
        }


class SatelliteAsset(Base):
    """A file that genuinely exists on disk, verified by size and checksum."""

    __tablename__ = "satellite_assets"

    id = Column(BigInteger, primary_key=True)
    product_id = Column(
        BigInteger,
        ForeignKey("satellite_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_key = Column(String(50), nullable=False, index=True)
    band_name = Column(String(20))
    resolution_m = Column(Integer)
    source_uri = Column(Text, nullable=False)
    transport = Column(String(20), nullable=False)
    local_path = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    raster_crs = Column(String(100))
    raster_width = Column(Integer)
    raster_height = Column(Integer)
    raster_transform = Column(ARRAY(Float))
    downloaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    product = relationship("SatelliteProduct", back_populates="assets")

    __table_args__ = (
        UniqueConstraint("product_id", "asset_key", name="uq_assets_product_key"),
        CheckConstraint("size_bytes > 0", name="chk_assets_size"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "asset_key": self.asset_key,
            "band_name": self.band_name,
            "resolution_m": self.resolution_m,
            "transport": self.transport,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "raster_crs": self.raster_crs,
            "downloaded_at": (
                self.downloaded_at.isoformat() if self.downloaded_at else None
            ),
        }


class SatelliteProcessingRun(Base):
    """One invocation of the satellite pipeline."""

    __tablename__ = "satellite_processing_runs"

    id = Column(BigInteger, primary_key=True)
    run_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    runtime_mode = Column(String(20), nullable=False)
    aoi_name = Column(String(100))
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime)
    status = Column(String(30), nullable=False, default="running", index=True)
    gate_reached = Column(String(50))
    products_discovered = Column(Integer, nullable=False, default=0)
    products_acquired = Column(Integer, nullable=False, default=0)
    products_classified = Column(Integer, nullable=False, default=0)
    layers_written = Column(Integer, nullable=False, default=0)
    changes_written = Column(Integer, nullable=False, default=0)
    # Phase C fix (DATAI defect 1): `default=0` alone is a client-side/ORM-only
    # default -- it never reaches the generated DDL, so any insert that
    # bypasses the ORM (raw SQL, another process) violated NOT NULL. Adding
    # server_default makes the database itself enforce the same default the
    # ORM already intended. See DATAI_DEFECT_REPAIR_EVIDENCE.md.
    bytes_downloaded = Column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    model_version = Column(String(50))
    model_sha256 = Column(String(64))
    model_promotion_status = Column(String(50))
    preprocessing_version = Column(String(50))
    code_version = Column(String(100))
    failure_class = Column(String(50))
    error_message = Column(Text)
    notes = Column(JSONB)

    def to_dict(self):
        return {
            "run_id": str(self.run_id),
            "runtime_mode": self.runtime_mode,
            "aoi_name": self.aoi_name,
            "status": self.status,
            "gate_reached": self.gate_reached,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "products_discovered": self.products_discovered,
            "products_acquired": self.products_acquired,
            "products_classified": self.products_classified,
            "layers_written": self.layers_written,
            "changes_written": self.changes_written,
            "bytes_downloaded": self.bytes_downloaded,
            "model_version": self.model_version,
            "model_promotion_status": self.model_promotion_status,
            "preprocessing_version": self.preprocessing_version,
            "failure_class": self.failure_class,
        }


class SatelliteLayer(Base):
    """Weekly land-use classification from Sentinel-2"""
    __tablename__ = "satellite_layers"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False, index=True)
    tile_id = Column(String(50), nullable=False, index=True)
    land_use_class = Column(String(30), nullable=False, index=True)  # urban, agricultural, water, forest, vacant
    confidence = Column(Float, nullable=False)  # 0-1.0
    # Phase C fix (DATAI defect 3): spatial_index=False added. The plain
    # `index=True` above (donor original) let GeoAlchemy2 auto-manage a
    # spatial index using the same derived name as the explicit
    # Index('idx_satellite_layers_geom', ...) below, causing a DuplicateTable
    # error on create_all(). zoning.py's PlanningZone.geom already established
    # the correct pattern; this brings SatelliteLayer in line with it.
    geom = Column(
        Geometry('POLYGON', srid=4326, spatial_index=False),
        nullable=False,
        index=True,
    )
    source = Column(String(50), default='sentinel2')
    model_version = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---- provenance (migration 003) --------------------------------------
    source_product_id = Column(
        BigInteger,
        ForeignKey("satellite_products.id", ondelete="RESTRICT"),
        index=True,
    )
    run_id = Column(UUID(as_uuid=True), index=True)
    preprocessing_version = Column(String(50))
    model_sha256 = Column(String(64))
    model_promotion_status = Column(String(50))
    observation_date = Column(Date, index=True)
    cloud_cover = Column(Float)
    area_sqm = Column(Float)
    pixel_count = Column(Integer)
    source_crs = Column(String(100))
    data_class = Column(String(20), nullable=False, default="derived")
    quality_flags = Column(JSONB)

    # A layer IS derived from exactly one product, and migration 003 creates
    # that foreign key, so this relationship is relationally justified.
    source_product = relationship("SatelliteProduct", back_populates="layers")

    # There is still NO direct ORM relationship to SatelliteChange keyed off
    # the layer. A change references two layers (prev/new) via explicit
    # nullable FKs on SatelliteChange; modelling it as a single collection here
    # would misrepresent that bitemporal structure.

    __table_args__ = (
        UniqueConstraint('week_start', 'tile_id', 'geom', name='uq_satellite_layers'),
        Index('idx_satellite_layers_geom', 'geom', postgresql_using='gist'),
        Index('idx_satellite_layers_week', 'week_start'),
        Index('idx_satellite_layers_class', 'land_use_class'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'week_start': self.week_start.isoformat(),
            'tile_id': self.tile_id,
            'land_use_class': self.land_use_class,
            'confidence': self.confidence,
            'model_version': self.model_version,
            'model_promotion_status': self.model_promotion_status,
            'preprocessing_version': self.preprocessing_version,
            'source_product_id': self.source_product_id,
            'observation_date': (
                self.observation_date.isoformat() if self.observation_date else None
            ),
            'cloud_cover': self.cloud_cover,
            'area_sqm': self.area_sqm,
            'data_class': self.data_class,
            'run_id': str(self.run_id) if self.run_id else None,
        }


class SatelliteChange(Base):
    """Week-to-week change detection results"""
    __tablename__ = "satellite_changes"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False, index=True)
    prev_week_start = Column(Date)
    change_type = Column(String(50), nullable=False, index=True)  # new_construction, clearing, etc.
    prev_class = Column(String(30))
    new_class = Column(String(30))
    confidence = Column(Float, nullable=False)  # 0-1.0
    # Phase C fix (DATAI defect 3): same spatial_index=False fix as
    # SatelliteLayer.geom above -- this was the second of exactly two
    # instances found during Phase A+B verification.
    geom = Column(
        Geometry('POLYGON', srid=4326, spatial_index=False),
        nullable=False,
        index=True,
    )
    severity = Column(String(20), index=True)  # low, medium, high
    area_sqm = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ---- provenance (migration 003) --------------------------------------
    run_id = Column(UUID(as_uuid=True), index=True)
    prev_layer_id = Column(
        BigInteger, ForeignKey("satellite_layers.id", ondelete="SET NULL")
    )
    new_layer_id = Column(
        BigInteger, ForeignKey("satellite_layers.id", ondelete="SET NULL")
    )
    prev_product_id = Column(
        BigInteger, ForeignKey("satellite_products.id", ondelete="SET NULL")
    )
    new_product_id = Column(
        BigInteger, ForeignKey("satellite_products.id", ondelete="SET NULL")
    )
    prev_observation_date = Column(Date)
    new_observation_date = Column(Date)
    model_version = Column(String(50))
    preprocessing_version = Column(String(50))
    data_class = Column(String(20), nullable=False, default="derived")

    # Relationships
    validations = relationship("SatelliteValidation", back_populates="change")
    prev_layer = relationship("SatelliteLayer", foreign_keys=[prev_layer_id])
    new_layer = relationship("SatelliteLayer", foreign_keys=[new_layer_id])

    __table_args__ = (
        Index('idx_satellite_changes_geom', 'geom', postgresql_using='gist'),
        Index('idx_satellite_changes_week', 'week_start'),
        Index('idx_satellite_changes_type', 'change_type'),
        Index('idx_satellite_changes_severity', 'severity'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'week_start': self.week_start.isoformat(),
            'change_type': self.change_type,
            'prev_class': self.prev_class,
            'new_class': self.new_class,
            'confidence': self.confidence,
            'severity': self.severity,
            'area_sqm': self.area_sqm,
        }


class SatelliteValidation(Base):
    """Ground-truth validation collection (Dong Nai focus)"""
    __tablename__ = "satellite_validations"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id', ondelete='CASCADE'), nullable=False, index=True)
    satellite_change_id = Column(Integer, ForeignKey('satellite_changes.id'), index=True)
    validation_source = Column(String(50))  # planet_labs, manual, scraper_photo
    validation_status = Column(String(30), default='pending', index=True)  # pending, confirmed, rejected, uncertain
    confidence = Column(Float)  # 0-1.0, validator's confidence
    notes = Column(Text)
    validated_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    validated_by = Column(String(100))
    unavailable_reason = Column(Text)

    # Relationships
    change = relationship("SatelliteChange", back_populates="validations")
    imagery = relationship("PlanetImagery", back_populates="validation")

    def to_dict(self):
        return {
            'id': self.id,
            'listing_id': self.listing_id,
            'satellite_change_id': self.satellite_change_id,
            'validation_source': self.validation_source,
            'validation_status': self.validation_status,
            'confidence': self.confidence,
            'validated_date': self.validated_date.isoformat() if self.validated_date else None,
        }


class PlanetImagery(Base):
    """High-resolution validation imagery from Planet Labs"""
    __tablename__ = "planet_imagery"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id', ondelete='CASCADE'), nullable=False, index=True)
    satellite_validation_id = Column(Integer, ForeignKey('satellite_validations.id'), index=True)
    planet_image_id = Column(String(255), unique=True)
    acquisition_date = Column(Date, nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    resolution_m = Column(Float)  # 3m, 5m, etc.
    confidence = Column(Float)  # 0-1.0, relevance to property
    stored_locally = Column(Boolean, default=False)
    local_path = Column(String(255))  # S3 path if cached
    created_at = Column(DateTime, default=datetime.utcnow)
    data_class = Column(String(20), nullable=False, default="observed")
    source_api = Column(String(50))
    retrieved_at = Column(DateTime)

    # Relationships
    validation = relationship("SatelliteValidation", back_populates="imagery")

    __table_args__ = (
        Index('idx_planet_listing', 'listing_id'),
        Index('idx_planet_validation', 'satellite_validation_id'),
        Index('idx_planet_date', 'acquisition_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'planet_image_id': self.planet_image_id,
            'acquisition_date': self.acquisition_date.isoformat(),
            'image_url': self.image_url,
            'resolution_m': self.resolution_m,
            'confidence': self.confidence,
            'stored_locally': self.stored_locally,
        }


class SatellitePhoto(Base):
    """Scraped photos with extracted features"""
    __tablename__ = "satellite_photos"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id', ondelete='CASCADE'), nullable=False, index=True)
    photo_url = Column(Text, nullable=False)
    photo_source = Column(String(50))  # batdongsan, chotot, planet_labs
    photo_order = Column(Integer)  # Sequence in listing
    extracted_features = Column(JSONB)  # {has_construction: true, vegetation: low, ...}
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_photos_listing', 'listing_id'),
        Index('idx_photos_source', 'photo_source'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'listing_id': self.listing_id,
            'photo_url': self.photo_url,
            'photo_source': self.photo_source,
            'photo_order': self.photo_order,
            'extracted_features': self.extracted_features,
        }


class ModelMetrics(Base):
    """Track classifier accuracy over time"""
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True)
    model_version = Column(String(20), unique=True, nullable=False, index=True)
    accuracy = Column(Float, nullable=False)  # 0-1.0
    trained_date = Column(DateTime, nullable=False)
    training_samples = Column(Integer)
    test_set_accuracy = Column(Float)  # Separate test set accuracy
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'model_version': self.model_version,
            'accuracy': self.accuracy,
            'trained_date': self.trained_date.isoformat(),
            'training_samples': self.training_samples,
            'test_set_accuracy': self.test_set_accuracy,
        }


class SatelliteIngestLog(Base):
    """Track ingestion status and performance"""
    __tablename__ = "satellite_ingest_log"

    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False, index=True)
    tile_id = Column(String(50))
    # See IngestStatus in app.satellite.pipeline for the permitted vocabulary.
    # 'success' is deliberately absent from what new code emits: it cannot
    # distinguish "catalogue answered" from "imagery ingested".
    ingestion_status = Column(String(50), index=True)
    cloud_cover_percent = Column(Float)
    file_size_bytes = Column(BigInteger)
    processing_time_seconds = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ---- truthful semantics (migration 003) ------------------------------
    run_id = Column(UUID(as_uuid=True), index=True)
    product_id = Column(
        BigInteger, ForeignKey("satellite_products.id", ondelete="SET NULL")
    )
    stac_id = Column(String(255))
    observation_date = Column(Date)
    # Phase C fix (DATAI defect 1): server_default added -- see
    # SatelliteProcessingRun.bytes_downloaded above for the full rationale.
    # This is the exact column that failed in Phase A+B's integration tests
    # (5 test cases) when inserted via raw SQL bypassing the ORM default.
    bytes_downloaded = Column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    duration_seconds = Column(Float)
    failure_class = Column(String(50), index=True)
    # Phase C fix (same root cause as bytes_downloaded above, found via the
    # defect-1 regression test itself exercising a raw insert): retry_count
    # had the identical client-side-only default gap.
    retry_count = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    model_version = Column(String(50))
    preprocessing_version = Column(String(50))

    __table_args__ = (
        Index('idx_ingest_week', 'week_start'),
        Index('idx_ingest_status', 'ingestion_status'),
    )

    def to_dict(self):
        return {
            'week_start': self.week_start.isoformat() if self.week_start else None,
            'tile_id': self.tile_id,
            'stac_id': self.stac_id,
            'ingestion_status': self.ingestion_status,
            'cloud_cover_percent': self.cloud_cover_percent,
            'bytes_downloaded': self.bytes_downloaded,
            'duration_seconds': self.duration_seconds,
            'failure_class': self.failure_class,
            'retry_count': self.retry_count,
            'error_message': self.error_message,
            'run_id': str(self.run_id) if self.run_id else None,
            'model_version': self.model_version,
            'preprocessing_version': self.preprocessing_version,
        }
