from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from geoalchemy2 import Geometry

from .base import Base


class PlanningZone(Base):
    """Official urban planning zone with land-use classifications.

    Data source: Vietnamese government planning-database exports.

    Phase C provenance correction (2026-08-27, DAT.AI Phase C recovery; see
    DATAI_PROVENANCE_VERIFICATION.md): the donor docstring here previously
    read "Data source: ... (DVHC authenticated). Confidence: 0.95
    (authoritative reference data)", worded as if 0.95 were a verified,
    per-record quality measurement. Traced to the actual ingestion code
    (worker/tasks/ingest_zoning_data.py): `confidence` is a flat CLI-argument
    constant (default 0.95) applied uniformly to every row in one ingestion
    batch -- not computed or independently verified per record. No DVHC
    authentication call was found anywhere in the ingestion path either; that
    phrase describes an unverified claim about the upstream source, not
    something this code re-checks. `data_confidence` below should be read as
    a DECLARED_SOURCE_CONFIDENCE, not a verified confidence score.
    """

    __tablename__ = "planning_zones"

    id = Column(Integer, primary_key=True)

    # Administrative identification
    project_id = Column(String(100), unique=True, nullable=False, index=True)
    project_name = Column(String(500), nullable=False)
    administrative_code = Column(String(50), nullable=True, index=True)

    # Original schema fields
    name = Column(String(255), nullable=False)
    zone_type = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Land-use classification (normalized)
    zone_category = Column(String(100), nullable=True, index=True)
    sub_categories = Column(
        JSONB().with_variant(JSON(), "sqlite"), default=lambda: [], nullable=False
    )

    # Geometry (PostGIS)
    geom = Column(
        # spatial_index=False: the GIST index is declared explicitly in
        # __table_args__ (and in migration 004) as idx_planning_zones_geom.
        Geometry("POLYGON", srid=4326, spatial_index=False).with_variant(
            Text(), "sqlite"
        ),
        nullable=True,
    )

    # Data governance
    # DECLARED_SOURCE_CONFIDENCE, not a verified per-record score -- see the
    # class docstring's Phase C provenance correction above.
    data_confidence = Column(Float, default=0.95, nullable=False)
    validation_status = Column(String(50), default="ingested", index=True)
    source_url = Column(Text, nullable=True)
    ingestion_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_planning_zones_geom", "geom", postgresql_using="GIST"),
    )

    def __repr__(self):
        return f"<PlanningZone {self.project_id}: {self.zone_category}>"
