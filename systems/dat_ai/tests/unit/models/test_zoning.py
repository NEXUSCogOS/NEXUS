import pytest
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Text
from sqlalchemy.orm import sessionmaker

from app.models import Base, PlanningZone

pytestmark = pytest.mark.unit


@pytest.fixture
def db_session():
    """In-memory SQLite for testing.

    PostGIS/SpatiaLite are not available in unit tests, so the physical test
    table is created from a copy of the model's table with the geometry column
    degraded to TEXT. Column names/types otherwise match, so the ORM mapping
    reads and writes it unchanged.
    """
    engine = create_engine("sqlite:///:memory:")
    md = MetaData()
    test_table = PlanningZone.__table__.to_metadata(md)
    test_table.c.geom.type = Text()
    md.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_planning_zone_creation(db_session):
    """Test creating a planning zone with basic attributes."""
    zone = PlanningZone(
        project_id="c4_bien_hoa",
        project_name="Quy hoạch phân khu C4 Biên Hòa",
        zone_category="residential_mixed",
        zone_type="qhxd_pk",
        administrative_code="26380",
        data_confidence=0.95,
        validation_status="ingested",
        source_url="https://example.com/c4",
        name="C4 Long Hưng",
    )

    db_session.add(zone)
    db_session.commit()

    retrieved = db_session.query(PlanningZone).filter_by(project_id="c4_bien_hoa").first()
    assert retrieved is not None
    assert retrieved.project_name == "Quy hoạch phân khu C4 Biên Hòa"
    assert retrieved.data_confidence == 0.95


def test_planning_zone_sub_categories(db_session):
    """Test storing and retrieving sub-category classifications."""
    zone = PlanningZone(
        project_id="d1_bien_hoa",
        project_name="D1 Phước Tân",
        zone_category="mixed_use",
        sub_categories=[
            {"id": "OTT", "name": "Đất ở thấp tầng", "color": [254, 224, 133]},
            {"id": "DGT", "name": "Đường giao thông", "color": [255, 169, 48]},
        ],
        administrative_code="26377",
        name="D1 C3",
    )

    db_session.add(zone)
    db_session.commit()

    retrieved = db_session.query(PlanningZone).filter_by(project_id="d1_bien_hoa").first()
    assert len(retrieved.sub_categories) == 2
    assert retrieved.sub_categories[0]["name"] == "Đất ở thấp tầng"


def test_planning_zone_defaults(db_session):
    """Test that default values are set correctly."""
    zone = PlanningZone(
        project_id="test_zone",
        project_name="Test Zone",
        name="Test",
    )

    db_session.add(zone)
    db_session.commit()

    retrieved = db_session.query(PlanningZone).filter_by(project_id="test_zone").first()
    assert retrieved.data_confidence == 0.95
    assert retrieved.validation_status == "ingested"
    assert retrieved.sub_categories == []
    assert retrieved.ingestion_date is not None
    assert isinstance(retrieved.ingestion_date, datetime)


def test_planning_zone_geometry_column_is_polygon_4326():
    """Geometry column must be POLYGON in EPSG:4326."""
    geom_type = PlanningZone.__table__.c.geom.type
    assert geom_type.geometry_type == "POLYGON"
    assert geom_type.srid == 4326


def test_planning_zone_repr():
    """Test string representation of zone."""
    zone = PlanningZone(
        project_id="c4",
        project_name="C4 Zone",
        zone_category="residential",
        name="C4",
    )
    assert "c4" in repr(zone)
    assert "residential" in repr(zone)
