"""Integration tests for the zoning API (``app/routes/zoning.py``).

The app is exercised through a real ``TestClient`` against a real database
session; only the *dialect* is substituted. PostGIS cannot be installed in this
environment (see the Task 2/3 reports), so ``planning_zones.geom`` degrades to
TEXT/WKT exactly as ``app/models/zoning.py`` declares for SQLite, and the route
module's documented Shapely fallback answers the spatial predicates.

That means these tests verify the endpoints, the routing order, the parameter
validation, the response shapes and the *spatial semantics* — a point inside a
polygon is found, a point outside it is not. They do NOT verify the PostGIS SQL
itself. ``test_postgis_sql_is_used_when_the_dialect_is_postgresql`` pins the
branch selection so the production path cannot be deleted unnoticed, and
``test_against_real_postgis`` runs the whole suite's core assertions against a
live database when ``TEST_DATABASE_URL`` points at one.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
from sqlalchemy import JSON, MetaData, Text, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.listings import Listing
from app.models.zoning import PlanningZone

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------

#: A 0.01 x 0.01 degree box near Bien Hoa, Dong Nai. (106.85, 10.88) is its
#: south-west corner, so (106.855, 10.885) is comfortably inside.
ZONE_A_WKT = (
    "POLYGON ((106.85 10.88, 106.86 10.88, 106.86 10.89, "
    "106.85 10.89, 106.85 10.88))"
)
#: Fully contains ZONE_A — overlapping plans are normal (a detailed plan sits
#: inside a subdivision plan), and the API must return both, smallest first.
ZONE_B_WKT = (
    "POLYGON ((106.84 10.87, 106.87 10.87, 106.87 10.90, "
    "106.84 10.90, 106.84 10.87))"
)
#: Disjoint from both, ~20 km east.
ZONE_C_WKT = (
    "POLYGON ((107.07 10.81, 107.08 10.81, 107.08 10.82, "
    "107.07 10.82, 107.07 10.81))"
)

INSIDE_LAT, INSIDE_LNG = 10.885, 106.855
OUTSIDE_LAT, OUTSIDE_LNG = 21.0285, 105.8542  # Hanoi — nowhere near any zone


@pytest.fixture
def db_session():
    """A SQLite session whose geometry/JSONB columns are degraded for the dialect.

    ``PlanningZone.geom`` already declares a Text variant for SQLite;
    ``Listing.geom`` and ``Listing.raw_payload`` do not, so they are remapped
    here. Nothing in the application is patched — only the test schema.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()

    zones = PlanningZone.__table__.to_metadata(metadata)
    zones.c.geom.type = Text()
    zones.c.sub_categories.type = JSON()

    listings = Listing.__table__.to_metadata(metadata)
    listings.c.geom.type = Text()
    listings.c.raw_payload.type = JSON()

    metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    # Carried so the seed fixture can INSERT listings through the *remapped*
    # table. `Listing` itself stays mapped to the original PostGIS table, whose
    # geoalchemy2 bind expression emits GeomFromEWKT() — a function SQLite does
    # not have. Reads are unaffected: the routes never select listings.geom,
    # and geoalchemy2's result processor passes NULL straight through.
    session.info["listings_table"] = listings
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded(db_session):
    """Three zones and two listings."""
    db_session.add_all(
        [
            PlanningZone(
                project_id="zone_a",
                project_name="Quy hoạch chi tiết khu dân cư A",
                name="A",
                zone_type="detailed_plan",
                description="Bản đồ quy hoạch sử dụng đất",
                zone_category="residential",
                sub_categories=[
                    {
                        "vietnamese_name": "Đất ở thấp tầng",
                        "code": "OTT",
                        "category": "residential_low",
                        "color": [254, 224, 133],
                    }
                ],
                administrative_code="26380",
                data_confidence=0.95,
                validation_status="ingested",
                source_url="https://quyhoach.xaydung.gov.vn/vn/quy-hoach/a",
                geom=ZONE_A_WKT,
                ingestion_date=datetime(2026, 8, 14, 12, 0, 0),
            ),
            PlanningZone(
                project_id="zone_b",
                project_name="Quy hoạch phân khu B",
                name="B",
                zone_type="subdivision_plan",
                zone_category="green_space",
                sub_categories=[],
                administrative_code="26380",
                data_confidence=0.95,
                validation_status="ingested",
                geom=ZONE_B_WKT,
                ingestion_date=datetime(2026, 8, 14, 12, 0, 0),
            ),
            PlanningZone(
                project_id="zone_c",
                project_name="Quy hoạch chung C",
                name="C",
                zone_type="general_plan",
                zone_category="industrial",
                sub_categories=[],
                administrative_code="26401",
                data_confidence=0.80,
                validation_status="pending_review",
                geom=ZONE_C_WKT,
                ingestion_date=datetime(2026, 8, 15, 9, 30, 0),
            ),
        ]
    )
    db_session.execute(
        db_session.info["listings_table"].insert(),
        [
            {
                "id": 1,
                "source": "test",
                "source_id": "listing-inside",
                "title": "Nhà trong khu dân cư A",
                "address": "Biên Hòa, Đồng Nai",
                "commune": "Tân Phong",
                "district": "Biên Hòa",
                "province": "Đồng Nai",
                "lat": INSIDE_LAT,
                "lng": INSIDE_LNG,
                "price_vnd": 3_000_000_000,
                "size_sqm": 100.0,
                "price_per_sqm": 30_000_000,
                "property_type": "house",
                "listed_date": datetime(2026, 8, 1),
                "geom": None,
                "data_class": "observed",
                "validation_status": "pending",
                "satellite_land_use": "urban",
                "satellite_confidence": 0.82,
            },
            {
                "id": 2,
                "source": "test",
                "source_id": "listing-outside",
                "title": "Nhà ở Hà Nội",
                "address": "Hà Nội",
                "commune": "Hoàn Kiếm",
                "district": "Hoàn Kiếm",
                "province": "Hà Nội",
                "lat": OUTSIDE_LAT,
                "lng": OUTSIDE_LNG,
                "price_vnd": 5_000_000_000,
                "size_sqm": 80.0,
                "price_per_sqm": 62_500_000,
                "property_type": "house",
                "listed_date": datetime(2026, 8, 1),
                "geom": None,
                "data_class": "observed",
                "validation_status": "pending",
                "satellite_land_use": None,
                "satellite_confidence": None,
            },
        ],
    )
    db_session.commit()
    return db_session


@pytest.fixture
def client(db_session):
    """TestClient with the app's DB dependency bound to the test session.

    Instantiated without the context manager on purpose: the lifespan would
    start the background scheduler, which these tests neither need nor want.
    """
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------
# 1. GET /zoning/zones
# ---------------------------------------------------------------------


def test_list_zones(client, seeded):
    response = client.get("/zoning/zones")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["total"] == 3
    assert body["count"] == 3
    assert body["limit"] == 100 and body["offset"] == 0
    assert [z["project_id"] for z in body["zones"]] == [
        "zone_a", "zone_b", "zone_c"
    ]

    zone_a = body["zones"][0]
    assert zone_a["zone_category"] == "residential"
    assert zone_a["project_name"] == "Quy hoạch chi tiết khu dân cư A"
    assert zone_a["has_geometry"] is True
    # A 0.01 x 0.01 degree box at 10.88N is ~1.21 km^2. Bounds, not equality:
    # the assertion must survive a switch to PostGIS ST_Area(::geography).
    assert 1.1e6 < zone_a["area_sqm"] < 1.3e6
    # The list endpoint is deliberately geometry-free — it is a directory.
    assert "geometry" not in zone_a


def test_list_zones_with_filtering(client, seeded):
    by_category = client.get("/zoning/zones", params={"category": "residential"})
    assert by_category.status_code == 200
    assert by_category.json()["total"] == 1
    assert by_category.json()["zones"][0]["project_id"] == "zone_a"

    by_status = client.get("/zoning/zones", params={"status": "pending_review"})
    assert by_status.json()["total"] == 1
    assert by_status.json()["zones"][0]["project_id"] == "zone_c"

    by_admin = client.get(
        "/zoning/zones", params={"administrative_code": "26380"}
    )
    assert by_admin.json()["total"] == 2

    by_confidence = client.get("/zoning/zones", params={"min_confidence": 0.9})
    assert by_confidence.json()["total"] == 2
    assert "zone_c" not in [z["project_id"] for z in by_confidence.json()["zones"]]

    combined = client.get(
        "/zoning/zones",
        params={"category": "residential", "status": "pending_review"},
    )
    assert combined.json()["total"] == 0
    assert combined.json()["zones"] == []

    unknown = client.get("/zoning/zones", params={"category": "no_such_category"})
    assert unknown.status_code == 200
    assert unknown.json()["total"] == 0


def test_list_zones_pagination(client, seeded):
    page = client.get("/zoning/zones", params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 3 and page["count"] == 2
    assert [z["project_id"] for z in page["zones"]] == ["zone_a", "zone_b"]

    tail = client.get("/zoning/zones", params={"limit": 2, "offset": 2}).json()
    # `total` must stay the full result-set size, not the page size, or a
    # client can never tell how many pages remain.
    assert tail["total"] == 3 and tail["count"] == 1
    assert tail["zones"][0]["project_id"] == "zone_c"

    assert client.get("/zoning/zones", params={"limit": 0}).status_code == 422
    assert client.get("/zoning/zones", params={"limit": 5000}).status_code == 422
    assert client.get("/zoning/zones", params={"offset": -1}).status_code == 422


# ---------------------------------------------------------------------
# 2. GET /zoning/zones/{project_id}
# ---------------------------------------------------------------------


def test_get_zone_detail(client, seeded):
    response = client.get("/zoning/zones/zone_a")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_id"] == "zone_a"
    assert body["zone_type"] == "detailed_plan"
    assert body["source_url"].startswith("https://quyhoach.xaydung.gov.vn")
    assert body["sub_categories"][0]["code"] == "OTT"

    geometry = body["geometry"]
    assert geometry is not None, "detail endpoint must return the boundary"
    assert geometry["type"] == "Polygon"
    ring = geometry["coordinates"][0]
    assert len(ring) == 5 and ring[0] == ring[-1], "ring must be closed"
    # GeoJSON is (lng, lat) — the longitude is the ~106 value, not the ~10 one.
    assert all(106.0 < lng < 107.0 for lng, _lat in ring)
    assert all(10.0 < lat < 11.0 for _lng, lat in ring)

    assert body["bbox"] == pytest.approx([106.85, 10.88, 106.86, 10.89])


def test_get_nonexistent_zone(client, seeded):
    response = client.get("/zoning/zones/does_not_exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Planning zone not found"


def test_zone_detail_route_does_not_shadow_intersect_routes(client, seeded):
    """`/zones/intersect/point` must not be parsed as project_id='intersect'."""
    response = client.get(
        "/zoning/zones/intersect/point",
        params={"lat": INSIDE_LAT, "lng": INSIDE_LNG},
    )
    assert response.status_code == 200
    assert "zones" in response.json() and "count" in response.json()


# ---------------------------------------------------------------------
# 3. GET /zoning/zones/intersect/point
# ---------------------------------------------------------------------


def test_find_zones_at_point(client, seeded):
    response = client.get(
        "/zoning/zones/intersect/point",
        params={"lat": INSIDE_LAT, "lng": INSIDE_LNG},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["lat"] == INSIDE_LAT and body["lng"] == INSIDE_LNG
    assert body["count"] == 2
    # Smallest first: the most specific plan leads.
    assert [z["project_id"] for z in body["zones"]] == ["zone_a", "zone_b"]
    assert body["zones"][0]["area_sqm"] < body["zones"][1]["area_sqm"]
    assert body["zones"][0]["geometry"]["type"] == "Polygon"


def test_find_zones_at_point_outside_every_zone(client, seeded):
    response = client.get(
        "/zoning/zones/intersect/point",
        params={"lat": OUTSIDE_LAT, "lng": OUTSIDE_LNG},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0 and body["zones"] == []
    # An empty result must say so, not look like a failure.
    assert any("No planning zone covers" in n for n in body["notes"])


def test_coordinate_order_is_not_swapped(client, seeded):
    """(lat=106.855, lng=10.885) is in the Arctic Ocean, not Dong Nai."""
    swapped = client.get(
        "/zoning/zones/intersect/point",
        params={"lat": 10.885, "lng": 106.855},
    ).json()
    assert swapped["count"] == 2

    # Feeding the values in the wrong order must not accidentally still match.
    wrong = client.get(
        "/zoning/zones/intersect/point",
        params={"lat": 89.0, "lng": 10.885},
    ).json()
    assert wrong["count"] == 0


def test_invalid_coordinates(client, seeded):
    bad_params = [
        {"lat": 91.0, "lng": 106.85},     # lat above +90
        {"lat": -91.0, "lng": 106.85},    # lat below -90
        {"lat": 10.88, "lng": 181.0},     # lng above +180
        {"lat": 10.88, "lng": -180.5},    # lng below -180
        {"lat": "north", "lng": 106.85},  # not a number
        {"lng": 106.85},                  # lat missing
        {"lat": 10.88},                   # lng missing
    ]
    for params in bad_params:
        response = client.get("/zoning/zones/intersect/point", params=params)
        assert response.status_code == 422, f"{params} -> {response.status_code}"
        assert "detail" in response.json()

    # The bounds are inclusive: the poles and the antimeridian are valid input.
    for params in ({"lat": 90.0, "lng": 180.0}, {"lat": -90.0, "lng": -180.0}):
        assert (
            client.get("/zoning/zones/intersect/point", params=params).status_code
            == 200
        )


# ---------------------------------------------------------------------
# 4. GET /zoning/zones/intersect/property/{listing_id}
# ---------------------------------------------------------------------


def test_find_zones_for_property(client, seeded):
    response = client.get("/zoning/zones/intersect/property/1")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["listing_id"] == 1
    assert body["lat"] == INSIDE_LAT and body["lng"] == INSIDE_LNG
    assert [z["project_id"] for z in body["zones"]] == ["zone_a", "zone_b"]


def test_find_zones_for_property_outside_every_zone(client, seeded):
    body = client.get("/zoning/zones/intersect/property/2").json()
    assert body["count"] == 0
    assert any("No planning zone covers" in n for n in body["notes"])


def test_find_zones_for_nonexistent_property(client, seeded):
    response = client.get("/zoning/zones/intersect/property/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Listing not found"


def test_find_zones_for_invalid_property_id(client, seeded):
    assert client.get("/zoning/zones/intersect/property/0").status_code == 422
    assert client.get("/zoning/zones/intersect/property/abc").status_code == 422


# ---------------------------------------------------------------------
# 5. GET /zoning/stats
# ---------------------------------------------------------------------


def test_zoning_statistics(client, seeded):
    response = client.get("/zoning/stats")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["has_data"] is True
    assert body["total_zones"] == 3
    assert body["zones_with_geometry"] == 3
    assert body["zones_without_geometry"] == 0
    assert body["total_area_sqm"] > 0
    assert body["distinct_categories"] == 3

    categories = {c["zone_category"]: c for c in body["categories"]}
    assert set(categories) == {"residential", "green_space", "industrial"}
    assert categories["residential"]["zone_count"] == 1
    assert categories["residential"]["avg_confidence"] == pytest.approx(0.95)
    # zone_b is 3x3 sub-boxes of zone_a's size, so ~9x the area.
    assert (
        categories["green_space"]["total_area_sqm"]
        > 8 * categories["residential"]["total_area_sqm"]
    )

    assert body["validation_status"] == {"ingested": 2, "pending_review": 1}
    assert body["confidence"]["min"] == pytest.approx(0.80)
    assert body["confidence"]["max"] == pytest.approx(0.95)
    assert body["confidence"]["avg"] == pytest.approx(0.90, abs=1e-3)
    assert body["administrative_codes"] == ["26380", "26401"]
    assert body["latest_ingestion_date"].startswith("2026-08-15")


def test_zoning_statistics_when_empty(client, db_session):
    """An empty table is a real state and must report itself as one."""
    body = client.get("/zoning/stats").json()
    assert body["has_data"] is False
    assert body["total_zones"] == 0
    assert body["categories"] == []
    assert body["confidence"] == {"avg": None, "min": None, "max": None}
    assert any("No planning zones have been ingested" in n for n in body["notes"])


def test_zoning_statistics_flags_zones_without_geometry(client, db_session):
    db_session.add(
        PlanningZone(
            project_id="no_geom",
            project_name="Missing boundary",
            name="X",
            zone_category="unclassified",
            sub_categories=[],
            data_confidence=0.95,
            validation_status="ingested",
            geom=None,
        )
    )
    db_session.commit()

    body = client.get("/zoning/stats").json()
    assert body["zones_without_geometry"] == 1
    assert any("invisible to every spatial query" in n for n in body["notes"])


# ---------------------------------------------------------------------
# 6. POST /zoning/validate
# ---------------------------------------------------------------------


def test_validate_match(client, seeded):
    response = client.post(
        "/zoning/validate",
        json={
            "lat": INSIDE_LAT,
            "lng": INSIDE_LNG,
            "satellite_land_use": "urban",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["zones_found"] == 2
    assert body["primary_zone_category"] == "residential"
    assert body["match"] is True
    assert body["match_score"] == 1.0
    assert body["verdict"] == "match"
    assert body["zoning_confidence"] == pytest.approx(0.95)


def test_validate_mismatch(client, seeded):
    body = client.post(
        "/zoning/validate",
        json={
            "lat": INSIDE_LAT,
            "lng": INSIDE_LNG,
            "satellite_land_use": "water",
        },
    ).json()
    # 'water' against residential/green_space: green_space is a partial pairing,
    # so this is inconclusive rather than a clean conflict.
    assert body["verdict"] == "partial_match"
    assert body["match_score"] == 0.5
    # A partial pairing must NOT report match=True: downstream that reads as
    # "zoning confirms the classifier", which a loose pairing does not do.
    assert body["match"] is None

    conflict = client.post(
        "/zoning/validate",
        json={"lat": 10.815, "lng": 107.075, "satellite_land_use": "water"},
    ).json()
    assert conflict["primary_zone_category"] == "industrial"
    assert conflict["verdict"] == "mismatch"
    assert conflict["match"] is False
    assert conflict["match_score"] == 0.0


def test_validate_by_listing_id_uses_stored_satellite_class(client, seeded):
    body = client.post("/zoning/validate", json={"listing_id": 1}).json()
    assert body["listing_id"] == 1
    assert body["lat"] == INSIDE_LAT and body["lng"] == INSIDE_LNG
    assert body["satellite_land_use"] == "urban"
    assert body["satellite_confidence"] == pytest.approx(0.82)
    assert body["verdict"] == "match"
    assert any("stored classification" in n for n in body["notes"])


def test_validate_match_flag_is_true_only_on_a_full_match(client, seeded):
    """match: True/False/None must mean confirmed / conflicts / cannot say."""
    cases = {
        # urban vs residential (zone_a, innermost) -> fully compatible
        ("urban", INSIDE_LAT, INSIDE_LNG): (1.0, True, "match"),
        # water vs residential, green_space -> only a partial pairing
        ("water", INSIDE_LAT, INSIDE_LNG): (0.5, None, "partial_match"),
        # water vs industrial -> a genuine conflict
        ("water", 10.815, 107.075): (0.0, False, "mismatch"),
    }
    for (land_use, lat, lng), (score, match, verdict) in cases.items():
        body = client.post(
            "/zoning/validate",
            json={"lat": lat, "lng": lng, "satellite_land_use": land_use},
        ).json()
        assert body["match_score"] == score, (land_use, body)
        assert body["match"] is match, (land_use, body)
        assert body["verdict"] == verdict, (land_use, body)


def test_validate_is_not_assessable_without_zoning_or_class(client, seeded):
    no_zone = client.post(
        "/zoning/validate",
        json={
            "lat": OUTSIDE_LAT,
            "lng": OUTSIDE_LNG,
            "satellite_land_use": "urban",
        },
    ).json()
    assert no_zone["verdict"] == "no_zoning_data"
    # Not assessable must be null, never 0.0 — 0.0 reads as "conflict".
    assert no_zone["match_score"] is None and no_zone["match"] is None

    no_class = client.post(
        "/zoning/validate", json={"lat": INSIDE_LAT, "lng": INSIDE_LNG}
    ).json()
    assert no_class["verdict"] == "no_satellite_class"
    assert no_class["match_score"] is None and no_class["match"] is None


def test_validate_rejects_bad_input(client, seeded):
    # Neither a listing nor a point.
    assert client.post("/zoning/validate", json={}).status_code == 422
    # Half a point.
    assert (
        client.post("/zoning/validate", json={"lat": INSIDE_LAT}).status_code == 422
    )
    # Out-of-range coordinates.
    assert (
        client.post(
            "/zoning/validate", json={"lat": 200.0, "lng": 106.85}
        ).status_code
        == 422
    )
    # A satellite class the classifier cannot emit.
    assert (
        client.post(
            "/zoning/validate",
            json={
                "lat": INSIDE_LAT,
                "lng": INSIDE_LNG,
                "satellite_land_use": "swamp",
            },
        ).status_code
        == 422
    )
    # A listing that does not exist.
    assert (
        client.post("/zoning/validate", json={"listing_id": 999999}).status_code
        == 404
    )


# ---------------------------------------------------------------------
# production-path guards
# ---------------------------------------------------------------------


def test_postgis_sql_is_used_when_the_dialect_is_postgresql():
    """The PostGIS branch is unreachable here, so pin its SQL by inspection.

    Without this, the production spatial path could be deleted or corrupted and
    every test above would still pass on the SQLite fallback.
    """
    from app.routes import zoning as zoning_module

    point_sql = zoning_module.CONTAINS_POINT_SQL
    listing_sql = zoning_module.INTERSECTS_LISTING_SQL

    assert "ST_Contains(z.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))" in (
        " ".join(point_sql.split())
    )
    assert "ST_Intersects( z.geom, ST_SetSRID(ST_MakePoint(l.lng, l.lat), 4326) )" in (
        " ".join(listing_sql.split())
    )

    for sql in (point_sql, listing_sql):
        assert "ST_Area(z.geom::geography)" in sql
        assert "ST_AsGeoJSON(z.geom)" in sql
        # ST_MakePoint alone yields SRID 0, which does not compare against a
        # 4326 column — PostGIS raises rather than mis-answering. Every point
        # construction must therefore be wrapped in ST_SetSRID.
        assert sql.count("ST_MakePoint") == sql.count("ST_SetSRID(ST_MakePoint")
        # PostGIS is (x, y) = (lng, lat); the API is (lat, lng). The lng
        # argument must come first or every query silently answers elsewhere.
        assert "ST_MakePoint(:lat" not in sql and "ST_MakePoint(l.lat" not in sql


def test_routes_are_registered_on_the_app():
    paths = {route.path for route in app.routes}
    assert {
        "/zoning/zones",
        "/zoning/zones/{project_id}",
        "/zoning/zones/intersect/point",
        "/zoning/zones/intersect/property/{listing_id}",
        "/zoning/stats",
        "/zoning/validate",
    } <= paths


def test_openapi_schema_includes_zoning():
    schema = app.openapi()
    assert "/zoning/zones" in schema["paths"]
    assert schema["paths"]["/zoning/validate"]["post"]["tags"] == ["zoning"]


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a PostGIS database to exercise the real path.",
)
def test_against_real_postgis():
    """Core spatial assertions against a live PostGIS instance.

    Skipped by default. This is the only test in the file that touches the
    production SQL; everything else runs on the documented SQLite fallback.
    """
    from fastapi.testclient import TestClient
    from geoalchemy2.elements import WKTElement

    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    session = sessionmaker(bind=engine)()
    project_id = "pytest_zoning_routes_tmp"
    try:
        session.query(PlanningZone).filter(
            PlanningZone.project_id == project_id
        ).delete()
        session.add(
            PlanningZone(
                project_id=project_id,
                project_name="pytest fixture zone",
                name="pytest",
                zone_category="residential",
                sub_categories=[],
                data_confidence=0.95,
                validation_status="ingested",
                geom=WKTElement(ZONE_A_WKT, srid=4326),
            )
        )
        session.commit()

        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)

        detail = client.get(f"/zoning/zones/{project_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["spatial_backend"] == "postgis"
        assert json.loads(json.dumps(detail.json()["geometry"]))["type"] == "Polygon"

        hit = client.get(
            "/zoning/zones/intersect/point",
            params={"lat": INSIDE_LAT, "lng": INSIDE_LNG},
        ).json()
        assert project_id in [z["project_id"] for z in hit["zones"]]

        miss = client.get(
            "/zoning/zones/intersect/point",
            params={"lat": OUTSIDE_LAT, "lng": OUTSIDE_LNG},
        ).json()
        assert project_id not in [z["project_id"] for z in miss["zones"]]

        stats = client.get("/zoning/stats").json()
        assert stats["has_data"] is True and stats["total_zones"] >= 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.query(PlanningZone).filter(
            PlanningZone.project_id == project_id
        ).delete()
        session.commit()
        session.close()
        engine.dispose()
