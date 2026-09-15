from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

from .base import Base


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)

    source = Column(String(50), nullable=False)
    source_id = Column(String(255), nullable=False, unique=True)

    title = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    commune = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    province = Column(String(100))

    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    price_vnd = Column(BigInteger, nullable=False)
    size_sqm = Column(Float, nullable=False)
    price_per_sqm = Column(BigInteger, nullable=False)

    property_type = Column(String(50), nullable=False)
    listed_date = Column(DateTime, nullable=False)

    contact_phone = Column(String(20))
    source_url = Column(Text)
    description = Column(Text)

    geom = Column(Geometry("POINT", srid=4326))

    active = Column(Boolean, default=True)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    # Provenance / governance
    data_class = Column(String(20), nullable=False, default="observed")
    validation_status = Column(String(20), nullable=False, default="pending")
    observed_at = Column(DateTime)
    ingested_at = Column(DateTime)
    source_confidence = Column(Float)
    raw_payload = Column(JSONB)

    # Satellite enrichment
    satellite_land_use = Column(String(30))
    satellite_confidence = Column(Float)
    zoning_type = Column(String(50))
    land_use_zoning_match = Column(Float)
    last_satellite_update = Column(DateTime)
