"""Integration tests for the zoning data ingestion pipeline.

The pipeline is exercised end-to-end (JSON file -> normalised rows in
`planning_zones`) against an in-memory SQLite database whose geometry column
is degraded to TEXT, mirroring `tests/unit/models/test_zoning.py`. PostGIS is
not installable in this environment; the pipeline renders WKT either way, so
the transformation logic under test is identical.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from sqlalchemy import MetaData, Text, create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from app.models import PlanningZone  # noqa: E402
from worker.tasks.ingest_zoning_data import (  # noqa: E402
    export_to_geojson,
    extract_zone_category,
    ingest_zoning_data,
    normalize_land_use_category,
    parse_geometries,
)

pytestmark = pytest.mark.integration

REAL_DATA_PATH = REPO_ROOT / "data" / "zoning_raw" / "dong_nai_2024.json"

SQUARE = [
    [
        [106.85, 10.88],
        [106.86, 10.88],
        [106.86, 10.89],
        [106.85, 10.89],
        [106.85, 10.88],
    ]
]


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    md = MetaData()
    table = PlanningZone.__table__.to_metadata(md)
    table.c.geom.type = Text()
    md.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def test_data_file(tmp_path):
    """Two synthetic zones: one complete, one missing its geometry."""
    records = [
        {
            "id": "test_zone_1",
            "fullName": "Quy hoạch phân khu tỷ lệ 1/5000 phân khu T1",
            "niceName": "Quy hoạch phân khu T1",
            "name": "T1",
            "desc": "Bản đồ quy hoạch sử dụng đất",
            "type": "QHXD_PK",
            "dvhc": ["26380", "731"],
            "sourceUrl": "https://quyhoach.xaydung.gov.vn/vn/quy-hoach/1",
            "geometries": json.dumps(SQUARE),
            "nameMap": json.dumps(
                {
                    "Đất ở thấp tầng": {"id": "OTT", "color": [254, 224, 133]},
                    "Đất ở cao tầng": {"id": "OCT", "color": [255, 127, 0]},
                    "Đường giao thông": {"id": "DGT", "color": [255, 169, 48]},
                },
                ensure_ascii=False,
            ),
        },
        {
            "id": "test_zone_no_geom",
            "fullName": "Quy hoạch không có hình học",
            "type": "QHXD_CT",
            "dvhc": ["26401"],
            "geometries": "",
            "nameMap": None,
        },
    ]
    path = tmp_path / "test_zones.json"
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------- unit-ish


def test_normalize_land_use_category():
    assert normalize_land_use_category("Đất ở thấp tầng") == "residential_low"
    assert normalize_land_use_category("Đất ở cao tầng") == "residential_high"
    assert normalize_land_use_category("Đất thương mại") == "commercial"
    assert normalize_land_use_category("Đường giao thông") == "transport"
    assert normalize_land_use_category("Khu cây xanh cách ly") == "green_space"
    assert normalize_land_use_category("Sông ngòi - Ao hồ cảnh quan") == "water"
    assert normalize_land_use_category("Đất giáo dục") == "education"
    assert normalize_land_use_category("Đất y tế") == "healthcare"
    assert normalize_land_use_category("Đất tôn giáo") == "religious"
    assert normalize_land_use_category("Đất công nghiệp") == "industrial"

    # Diacritic- and case-insensitive
    assert normalize_land_use_category("DAT O THAP TANG") == "residential_low"
    assert normalize_land_use_category("dat cong nghiep") == "industrial"

    # Compound labels resolve on their leading term, not the longest keyword.
    assert normalize_land_use_category("Khu cây xanh - giao thông") == "green_space"
    assert normalize_land_use_category("Đất đầu mối hạ tầng kỹ thuật") == "infrastructure"

    # Unknown / empty input never raises
    assert normalize_land_use_category("Quy hoạch chưa xác định") == "unclassified"
    assert normalize_land_use_category("") == "unclassified"
    assert normalize_land_use_category(None) == "unclassified"


def test_parse_geometries():
    polygon = parse_geometries(json.dumps(SQUARE))
    assert isinstance(polygon, Polygon)
    assert polygon.is_valid
    # Source is [lng, lat]; shapely keeps x=lng, y=lat.
    minx, miny, maxx, maxy = polygon.bounds
    assert (minx, maxx) == pytest.approx((106.85, 106.86))
    assert (miny, maxy) == pytest.approx((10.88, 10.89))

    # Already-decoded lists and bare rings are accepted too.
    assert parse_geometries(SQUARE).equals(polygon)
    assert parse_geometries(SQUARE[0]).equals(polygon)

    # Malformed / insufficient input returns None rather than raising.
    assert parse_geometries(None) is None
    assert parse_geometries("") is None
    assert parse_geometries("not json") is None
    assert parse_geometries("[]") is None
    assert parse_geometries(json.dumps([[[106.85, 10.88], [106.86, 10.88]]])) is None

    # Real source geometry parses.
    records = json.loads(REAL_DATA_PATH.read_text(encoding="utf-8"))
    real = parse_geometries(records[0]["geometries"])
    assert isinstance(real, Polygon)
    assert real.is_valid and real.area > 0


def test_extract_zone_category():
    name_map = {
        "Đất ở thấp tầng": {"id": "OTT", "color": [254, 224, 133]},
        "Đất ở cao tầng": {"id": "OCT", "color": [255, 127, 0]},
        "Đường giao thông": {"id": "DGT", "color": [255, 169, 48]},
        "Khu cây xanh cách ly": {"id": "CX", "color": [55, 168, 0]},
        "Khu cây xanh - Công viên - Cấp đô thị": {"id": "CX", "color": [152, 224, 156]},
        "Đất thương mại": {"id": "TM", "color": [230, 0, 0]},
    }
    primary, subs = extract_zone_category(name_map)

    assert primary == "green_space"  # 2 green entries beat the singletons
    assert len(subs) == 6
    first = subs[0]
    assert first["vietnamese_name"] == "Đất ở thấp tầng"
    assert first["code"] == "OTT"
    assert first["color"] == [254, 224, 133]
    assert first["category"] == "residential_low"
    assert {s["category"] for s in subs} >= {
        "residential_low",
        "residential_high",
        "transport",
        "green_space",
        "commercial",
    }

    # JSON-string input (the shape the raw export actually uses)
    primary_str, subs_str = extract_zone_category(json.dumps(name_map, ensure_ascii=False))
    assert primary_str == primary
    assert subs_str == subs

    # Missing / unusable input
    assert extract_zone_category(None) == ("unclassified", [])
    assert extract_zone_category({}) == ("unclassified", [])
    assert extract_zone_category("not json") == ("unclassified", [])


# ---------------------------------------------------------------- pipeline


def test_ingest_zoning_data_with_test_data(db_session, test_data_file):
    summary = ingest_zoning_data(
        test_data_file, province="Dong Nai", confidence=0.95, session=db_session
    )

    assert summary["total_records"] == 2
    assert summary["inserted"] == 1
    assert summary["updated"] == 0
    assert summary["skipped_no_geometry"] == 1
    assert summary["errors"] == []
    assert summary["province"] == "Dong Nai"

    zone = db_session.query(PlanningZone).filter_by(project_id="test_zone_1").one()
    assert zone.project_name == "Quy hoạch phân khu tỷ lệ 1/5000 phân khu T1"
    assert zone.name == "Quy hoạch phân khu T1"
    assert zone.zone_type == "subdivision_plan"
    assert zone.administrative_code == "26380"
    assert zone.data_confidence == 0.95
    assert zone.validation_status == "ingested"
    assert zone.source_url == "https://quyhoach.xaydung.gov.vn/vn/quy-hoach/1"
    assert zone.zone_category in {"residential_low", "residential_high", "transport"}
    assert len(zone.sub_categories) == 3
    assert zone.geom is not None and zone.geom.startswith("POLYGON")

    # Re-running updates in place instead of duplicating.
    again = ingest_zoning_data(
        test_data_file, province="Dong Nai", confidence=0.9, session=db_session
    )
    assert again["inserted"] == 0
    assert again["updated"] == 1
    assert db_session.query(PlanningZone).count() == 1
    assert (
        db_session.query(PlanningZone).filter_by(project_id="test_zone_1").one()
        .data_confidence
        == 0.9
    )


def test_ingest_missing_geometry(db_session, test_data_file):
    summary = ingest_zoning_data(
        test_data_file, province="Dong Nai", confidence=0.95, session=db_session
    )

    assert summary["skipped_no_geometry"] == 1
    # The geometry-less record is not persisted at all.
    assert (
        db_session.query(PlanningZone)
        .filter_by(project_id="test_zone_no_geom")
        .one_or_none()
        is None
    )
    assert db_session.query(PlanningZone).count() == 1
    assert summary["errors"] == []


def test_ingest_real_dong_nai_export(db_session):
    """The shipped Đồng Nai export ingests without errors."""
    summary = ingest_zoning_data(
        str(REAL_DATA_PATH), province="Dong Nai", confidence=0.95, session=db_session
    )

    assert summary["errors"] == []
    assert summary["inserted"] == summary["total_records"]
    assert db_session.query(PlanningZone).count() == summary["total_records"]

    c4 = db_session.query(PlanningZone).filter_by(project_id="c4").one()
    assert c4.zone_category != "unclassified"
    assert len(c4.sub_categories) == 15
    assert c4.administrative_code == "26380"
    assert c4.geom.startswith("POLYGON")

    # A project with no nameMap still ingests, classified as unclassified.
    camduong = db_session.query(PlanningZone).filter_by(project_id="camduong").one()
    assert camduong.zone_category == "unclassified"
    assert camduong.sub_categories == []


def test_export_to_geojson(db_session, test_data_file, tmp_path):
    ingest_zoning_data(
        test_data_file, province="Dong Nai", confidence=0.95, session=db_session
    )

    out = tmp_path / "zones.geojson"
    collection = export_to_geojson(str(out), session=db_session)

    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 1
    feature = collection["features"][0]
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["project_id"] == "test_zone_1"

    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == collection
