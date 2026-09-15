"""Zoning API — official Vietnamese urban-planning zones.

Data served here is *authoritative reference data* (``data_confidence`` 0.95,
DVHC-validated), not model output. It is therefore the reference side of every
satellite-vs-zoning comparison, never the side under suspicion.

Spatial backend
---------------
Production runs on PostgreSQL + PostGIS: every spatial predicate and every area
figure is computed by ``ST_Contains`` / ``ST_Intersects`` / ``ST_Area`` inside
the database, with geometry pinned to EPSG:4326 via ``ST_SetSRID``.

``PlanningZone.geom`` declares ``.with_variant(Text(), "sqlite")`` (see
``app/models/zoning.py``), so on SQLite the column holds plain WKT and no
PostGIS function exists. Rather than let those endpoints 500 — or, worse,
silently return an empty list that reads like "no zones here" — this module
detects the dialect and evaluates the same predicates with Shapely, and areas
with a geodesic (WGS84) calculation that matches ``ST_Area(geom::geography)``
semantics. The SQLite path is a development/test convenience: it loads
candidate rows into memory and is not intended for production volumes. Every
response carries ``spatial_backend`` so a caller can tell which one answered.

Coordinate ordering
-------------------
Every public parameter is ``(lat, lng)`` because that is what humans and map
UIs use. PostGIS and Shapely both take ``(x, y) = (lng, lat)``. The swap
happens exactly once, at the boundary, in ``_point_params`` / ``_shapely_point``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.listings import Listing
from app.models.zoning import PlanningZone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zoning", tags=["zoning"])

SRID = 4326

#: Upper bound on rows scanned in memory by the SQLite fallback. Exceeding it
#: is reported to the caller rather than silently truncating a spatial answer.
_FALLBACK_SCAN_LIMIT = 20_000


# =====================================================================
# satellite land-use <-> zoning compatibility
# =====================================================================

#: Satellite classes (see ``app/routes/satellite.py``) mapped to the zoning
#: categories produced by ``worker/tasks/ingest_zoning_data.py``. A full match
#: scores 1.0.
COMPATIBLE_ZONING: dict[str, set[str]] = {
    "urban": {
        "residential", "residential_low", "residential_high", "commercial",
        "industrial", "public_service", "administrative", "education",
        "healthcare", "religious", "heritage", "tourism", "military",
        "transport", "infrastructure", "cemetery",
    },
    "agricultural": {"agricultural"},
    "water": {"water"},
    "forest": {"forestry"},
    "vacant": {"agricultural", "green_space"},
}

#: Defensible-but-not-clean pairings; score 0.5. A park classified "vacant" is
#: not a zoning violation, it is a classifier being coarse.
PARTIAL_ZONING: dict[str, set[str]] = {
    "urban": {"green_space", "agricultural"},
    "agricultural": {"green_space", "forestry"},
    "water": {"green_space", "agricultural"},
    "forest": {"green_space", "agricultural"},
    "vacant": {
        "forestry", "water", "transport", "infrastructure", "cemetery",
        "military",
    },
}

SatelliteLandUse = Literal["urban", "agricultural", "water", "forest", "vacant"]


# =====================================================================
# response models
# =====================================================================


class ZoneSummary(BaseModel):
    id: int
    project_id: str
    project_name: str | None = None
    name: str | None = None
    zone_type: str | None = None
    zone_category: str | None = None
    administrative_code: str | None = None
    data_confidence: float | None = None
    validation_status: str | None = None
    area_sqm: float | None = None
    has_geometry: bool = False
    ingestion_date: str | None = None


class ZoneDetail(ZoneSummary):
    description: str | None = None
    source_url: str | None = None
    sub_categories: list[dict[str, Any]] = Field(default_factory=list)
    geometry: dict[str, Any] | None = None
    bbox: list[float] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ZoneListResponse(BaseModel):
    total: int
    count: int
    limit: int
    offset: int
    spatial_backend: str
    zones: list[ZoneSummary] = Field(default_factory=list)


class PointQueryResponse(BaseModel):
    lat: float
    lng: float
    count: int
    spatial_backend: str
    zones: list[ZoneDetail] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PropertyZoneResponse(BaseModel):
    listing_id: int
    lat: float
    lng: float
    count: int
    spatial_backend: str
    zones: list[ZoneDetail] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CategoryStat(BaseModel):
    zone_category: str
    zone_count: int
    total_area_sqm: float | None = None
    avg_confidence: float | None = None


class ZoningStatsResponse(BaseModel):
    has_data: bool
    total_zones: int
    zones_with_geometry: int
    zones_without_geometry: int
    total_area_sqm: float | None = None
    distinct_categories: int
    categories: list[CategoryStat] = Field(default_factory=list)
    validation_status: dict[str, int] = Field(default_factory=dict)
    confidence: dict[str, float | None] = Field(default_factory=dict)
    administrative_codes: list[str] = Field(default_factory=list)
    latest_ingestion_date: str | None = None
    spatial_backend: str
    notes: list[str] = Field(default_factory=list)


class ZoningValidationRequest(BaseModel):
    """Either ``listing_id`` or both ``lat``/``lng`` must be supplied."""

    listing_id: int | None = Field(None, ge=1)
    lat: float | None = Field(None, ge=-90.0, le=90.0)
    lng: float | None = Field(None, ge=-180.0, le=180.0)
    satellite_land_use: SatelliteLandUse | None = None
    satellite_confidence: float | None = Field(None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _require_a_location(self) -> "ZoningValidationRequest":
        has_point = self.lat is not None and self.lng is not None
        if self.listing_id is None and not has_point:
            raise ValueError(
                "Supply either listing_id, or both lat and lng."
            )
        if not has_point and (self.lat is not None or self.lng is not None):
            raise ValueError("lat and lng must be supplied together.")
        return self


class ZoningValidationResponse(BaseModel):
    listing_id: int | None = None
    lat: float
    lng: float
    satellite_land_use: str | None = None
    satellite_confidence: float | None = None
    zoning_categories: list[str] = Field(default_factory=list)
    primary_zone_category: str | None = None
    zone_project_ids: list[str] = Field(default_factory=list)
    zones_found: int = 0
    match: bool | None = None
    match_score: float | None = None
    zoning_confidence: float | None = None
    spatial_backend: str
    verdict: str
    explanation: str
    notes: list[str] = Field(default_factory=list)


# =====================================================================
# dialect handling
# =====================================================================


def _dialect(db: Session) -> str:
    try:
        return db.get_bind().dialect.name
    except Exception:  # pragma: no cover - only if the session has no bind
        return "unknown"


def _is_postgis(db: Session) -> bool:
    return _dialect(db) == "postgresql"


def _backend_name(db: Session) -> str:
    return "postgis" if _is_postgis(db) else f"{_dialect(db)}-shapely-fallback"


def _point_params(lat: float, lng: float) -> dict[str, float]:
    """PostGIS takes (x, y) = (lng, lat). The swap lives here and nowhere else."""
    return {"lng": lng, "lat": lat}


#: ``ST_SetSRID`` is mandatory: ``ST_MakePoint`` produces SRID 0, and comparing
#: SRID 0 against a 4326 column raises rather than silently mis-answering.
_POINT_4326 = f"ST_SetSRID(ST_MakePoint(:lng, :lat), {SRID})"


def _shapely_point(lat: float, lng: float):
    from shapely.geometry import Point

    return Point(lng, lat)


def _load_wkt(value: Any):
    """Parse a geometry read back from a non-PostGIS column (plain WKT)."""
    if value is None:
        return None
    try:
        from shapely import wkt

        return wkt.loads(str(value))
    except Exception:
        logger.debug("Unparseable geometry in planning_zones", exc_info=True)
        return None


def _geodesic_area_sqm(geometry: Any) -> float | None:
    """Area on the WGS84 ellipsoid — the same quantity as ``ST_Area(::geography)``."""
    if geometry is None or geometry.is_empty:
        return None
    try:
        from pyproj import Geod

        area, _perimeter = Geod(ellps="WGS84").geometry_area_perimeter(geometry)
        return abs(float(area))
    except Exception:
        logger.debug("Geodesic area computation failed", exc_info=True)
        return None


def _execute(db: Session, sql, params: dict[str, Any] | None = None):
    """Run a statement, converting a driver failure into a clean 500.

    Without the rollback the session stays poisoned for the rest of the
    request and every later statement fails with an unrelated message.
    """
    try:
        return db.execute(sql, params or {})
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Zoning query failed")
        raise HTTPException(status_code=500, detail="Zoning query failed")


# =====================================================================
# row -> response
# =====================================================================


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _sub_categories(value: Any) -> list[dict[str, Any]]:
    """JSONB arrives decoded on psycopg2, as a string on the SQLite JSON variant."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _summary_from_mapping(row) -> ZoneSummary:
    return ZoneSummary(
        id=row["id"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        name=row["name"],
        zone_type=row["zone_type"],
        zone_category=row["zone_category"],
        administrative_code=row["administrative_code"],
        data_confidence=row["data_confidence"],
        validation_status=row["validation_status"],
        area_sqm=(
            float(row["area_sqm"]) if row.get("area_sqm") is not None else None
        ),
        has_geometry=bool(row.get("has_geometry")),
        ingestion_date=_isoformat(row["ingestion_date"]),
    )


def _detail_from_mapping(row) -> ZoneDetail:
    geojson = row.get("geojson")
    geometry = json.loads(geojson) if geojson else None
    return ZoneDetail(
        **_summary_from_mapping(row).model_dump(),
        description=row.get("description"),
        source_url=row.get("source_url"),
        sub_categories=_sub_categories(row.get("sub_categories")),
        geometry=geometry,
        bbox=(
            [float(v) for v in row["bbox"]] if row.get("bbox") else None
        ),
        created_at=_isoformat(row.get("created_at")),
        updated_at=_isoformat(row.get("updated_at")),
    )


def _summary_from_orm(zone: PlanningZone, geometry: Any) -> ZoneSummary:
    return ZoneSummary(
        id=zone.id,
        project_id=zone.project_id,
        project_name=zone.project_name,
        name=zone.name,
        zone_type=zone.zone_type,
        zone_category=zone.zone_category,
        administrative_code=zone.administrative_code,
        data_confidence=zone.data_confidence,
        validation_status=zone.validation_status,
        area_sqm=_geodesic_area_sqm(geometry),
        has_geometry=geometry is not None,
        ingestion_date=_isoformat(zone.ingestion_date),
    )


def _detail_from_orm(zone: PlanningZone, geometry: Any) -> ZoneDetail:
    from shapely.geometry import mapping

    return ZoneDetail(
        **_summary_from_orm(zone, geometry).model_dump(),
        description=zone.description,
        source_url=zone.source_url,
        sub_categories=_sub_categories(zone.sub_categories),
        geometry=mapping(geometry) if geometry is not None else None,
        bbox=[float(v) for v in geometry.bounds] if geometry is not None else None,
        created_at=_isoformat(zone.created_at),
        updated_at=_isoformat(zone.updated_at),
    )


_SELECT_COLUMNS = """
    z.id, z.project_id, z.project_name, z.name, z.zone_type, z.description,
    z.zone_category, z.sub_categories, z.administrative_code,
    z.data_confidence, z.validation_status, z.source_url,
    z.ingestion_date, z.created_at, z.updated_at,
    (z.geom IS NOT NULL) AS has_geometry,
    ST_Area(z.geom::geography) AS area_sqm
"""

_SELECT_COLUMNS_WITH_GEOM = _SELECT_COLUMNS + """,
    ST_AsGeoJSON(z.geom) AS geojson,
    ARRAY[
        ST_XMin(z.geom::box2d), ST_YMin(z.geom::box2d),
        ST_XMax(z.geom::box2d), ST_YMax(z.geom::box2d)
    ] AS bbox
"""

#: The exact statements sent to PostGIS. Held as module constants so tests can
#: assert on the *final* SQL rather than on pre-interpolation source text.
CONTAINS_POINT_SQL = f"""
    SELECT {_SELECT_COLUMNS_WITH_GEOM}
    FROM planning_zones z
    WHERE z.geom IS NOT NULL
      AND ST_Contains(z.geom, {_POINT_4326})
    ORDER BY ST_Area(z.geom::geography) ASC
    LIMIT :limit
"""

#: A listing is a point, so intersection and containment coincide; the join
#: keeps the coordinate transfer inside the database instead of round-tripping
#: it through Python, where the (lat, lng) -> (x, y) swap could be reintroduced.
INTERSECTS_LISTING_SQL = f"""
    SELECT {_SELECT_COLUMNS_WITH_GEOM}
    FROM planning_zones z
    JOIN listings l ON l.id = :listing_id
    WHERE z.geom IS NOT NULL
      AND l.lat IS NOT NULL AND l.lng IS NOT NULL
      AND ST_Intersects(
              z.geom, ST_SetSRID(ST_MakePoint(l.lng, l.lat), {SRID})
          )
    ORDER BY ST_Area(z.geom::geography) ASC
    LIMIT :limit
"""


# =====================================================================
# 1. list zones
# =====================================================================


@router.get("/zones", response_model=ZoneListResponse)
def list_zones(
    category: str | None = Query(
        None, max_length=100,
        description="Filter on normalised zone_category, e.g. 'residential'.",
    ),
    status: str | None = Query(
        None, max_length=50, description="Filter on validation_status."
    ),
    administrative_code: str | None = Query(None, max_length=50),
    zone_type: str | None = Query(None, max_length=100),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ZoneListResponse:
    """Paginated zone list. Geometry is omitted here — see ``/zones/{project_id}``."""
    filters = ["z.data_confidence >= :min_conf"]
    params: dict[str, Any] = {
        "min_conf": min_confidence, "limit": limit, "offset": offset,
    }
    if category is not None:
        filters.append("z.zone_category = :category")
        params["category"] = category
    if status is not None:
        filters.append("z.validation_status = :status")
        params["status"] = status
    if administrative_code is not None:
        filters.append("z.administrative_code = :admin_code")
        params["admin_code"] = administrative_code
    if zone_type is not None:
        filters.append("z.zone_type = :zone_type")
        params["zone_type"] = zone_type
    where = " AND ".join(filters)

    if _is_postgis(db):
        total = int(
            _execute(
                db,
                text(f"SELECT COUNT(*) FROM planning_zones z WHERE {where}"),
                {k: v for k, v in params.items() if k not in ("limit", "offset")},
            ).scalar()
            or 0
        )
        rows = (
            _execute(
                db,
                text(
                    f"""
                    SELECT {_SELECT_COLUMNS}
                    FROM planning_zones z
                    WHERE {where}
                    ORDER BY z.project_id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
        zones = [_summary_from_mapping(row) for row in rows]
    else:
        query = db.query(PlanningZone).filter(
            PlanningZone.data_confidence >= min_confidence
        )
        if category is not None:
            query = query.filter(PlanningZone.zone_category == category)
        if status is not None:
            query = query.filter(PlanningZone.validation_status == status)
        if administrative_code is not None:
            query = query.filter(
                PlanningZone.administrative_code == administrative_code
            )
        if zone_type is not None:
            query = query.filter(PlanningZone.zone_type == zone_type)

        total = query.count()
        records = (
            query.order_by(PlanningZone.project_id)
            .limit(limit)
            .offset(offset)
            .all()
        )
        zones = [
            _summary_from_orm(zone, _load_wkt(zone.geom)) for zone in records
        ]

    return ZoneListResponse(
        total=total,
        count=len(zones),
        limit=limit,
        offset=offset,
        spatial_backend=_backend_name(db),
        zones=zones,
    )


# =====================================================================
# 3/4. spatial intersection
#
# Declared BEFORE /zones/{project_id}: FastAPI resolves routes in declaration
# order, and a literal path must win over a path parameter that could swallow it.
# =====================================================================


def _listing_location(db: Session, listing_id: int):
    """The five listing columns this router actually reads.

    Deliberately not ``db.query(Listing)``: that would also select
    ``listings.geom``, transferring a POINT blob on every request for a value
    no zoning endpoint uses. The zone polygons are the geometry that matters
    here, and they come from ``planning_zones``.
    """
    return (
        db.query(
            Listing.id,
            Listing.lat,
            Listing.lng,
            Listing.satellite_land_use,
            Listing.satellite_confidence,
        )
        .filter(Listing.id == listing_id)
        .first()
    )


def _zones_containing_point(
    db: Session, lat: float, lng: float, limit: int
) -> tuple[list[ZoneDetail], list[str]]:
    notes: list[str] = []

    if _is_postgis(db):
        params = _point_params(lat, lng)
        params["limit"] = limit
        rows = (
            _execute(db, text(CONTAINS_POINT_SQL), params).mappings().all()
        )
        return [_detail_from_mapping(row) for row in rows], notes

    return _shapely_zones_at_point(db, lat, lng, limit, notes)


def _shapely_zones_at_point(
    db: Session, lat: float, lng: float, limit: int, notes: list[str]
) -> tuple[list[ZoneDetail], list[str]]:
    """``ST_Contains`` evaluated in Python, for dialects without PostGIS."""
    point = _shapely_point(lat, lng)
    candidates = (
        db.query(PlanningZone)
        .filter(PlanningZone.geom.isnot(None))
        .limit(_FALLBACK_SCAN_LIMIT)
        .all()
    )
    if len(candidates) >= _FALLBACK_SCAN_LIMIT:
        notes.append(
            f"Fallback scan hit its {_FALLBACK_SCAN_LIMIT}-row limit; the "
            "result may be incomplete. Run against PostGIS."
        )
    hits = []
    for zone in candidates:
        geometry = _load_wkt(zone.geom)
        if geometry is None or not geometry.contains(point):
            continue
        hits.append((_geodesic_area_sqm(geometry) or 0.0, zone, geometry))
    hits.sort(key=lambda item: item[0])
    return (
        [_detail_from_orm(zone, geometry) for _area, zone, geometry in hits[:limit]],
        notes,
    )


@router.get("/zones/intersect/point", response_model=PointQueryResponse)
def find_zones_at_point(
    lat: float = Query(
        ..., ge=-90.0, le=90.0, description="Latitude, WGS84 (EPSG:4326)."
    ),
    lng: float = Query(
        ..., ge=-180.0, le=180.0, description="Longitude, WGS84 (EPSG:4326)."
    ),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PointQueryResponse:
    """Every planning zone whose polygon contains the given point.

    Out-of-range coordinates are rejected with 422 by the bounds above; they
    are never clamped, because a clamped coordinate answers a question the
    caller did not ask. Overlapping zones (a detailed plan inside a subdivision
    plan) are all returned, smallest first — the most specific zone leads.
    """
    zones, notes = _zones_containing_point(db, lat, lng, limit)
    if not zones:
        notes.append("No planning zone covers this point.")
    return PointQueryResponse(
        lat=lat, lng=lng, count=len(zones),
        spatial_backend=_backend_name(db), zones=zones, notes=notes,
    )


@router.get(
    "/zones/intersect/property/{listing_id}", response_model=PropertyZoneResponse
)
def find_zones_for_property(
    listing_id: int = Path(..., ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PropertyZoneResponse:
    """Planning zones intersecting a listing's location.

    The listing must exist (404 otherwise) — an unknown listing is a different
    answer from a known listing with no zoning, and collapsing the two would
    let a typo read as "this property is unzoned".
    """
    listing = _listing_location(db, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.lat is None or listing.lng is None:
        raise HTTPException(
            status_code=422, detail="Listing has no coordinates"
        )

    notes: list[str] = []
    if _is_postgis(db):
        rows = (
            _execute(
                db,
                text(INTERSECTS_LISTING_SQL),
                {"listing_id": listing_id, "limit": limit},
            )
            .mappings()
            .all()
        )
        zones = [_detail_from_mapping(row) for row in rows]
    else:
        zones, notes = _shapely_zones_at_point(
            db, float(listing.lat), float(listing.lng), limit, notes
        )

    if not zones:
        notes.append("No planning zone covers this property.")
    return PropertyZoneResponse(
        listing_id=listing_id,
        lat=float(listing.lat),
        lng=float(listing.lng),
        count=len(zones),
        spatial_backend=_backend_name(db),
        zones=zones,
        notes=notes,
    )


# =====================================================================
# 5. statistics
# =====================================================================


@router.get("/stats", response_model=ZoningStatsResponse)
def get_zoning_stats(db: Session = Depends(get_db)) -> ZoningStatsResponse:
    """Aggregate zoning statistics. Correct — and explicit — when empty."""
    notes: list[str] = []

    if _is_postgis(db):
        totals = (
            _execute(
                db,
                text(
                    """
                    SELECT COUNT(*)                                   AS total,
                           COUNT(geom)                                AS with_geom,
                           COALESCE(SUM(ST_Area(geom::geography)), 0) AS area,
                           AVG(data_confidence)                       AS avg_conf,
                           MIN(data_confidence)                       AS min_conf,
                           MAX(data_confidence)                       AS max_conf,
                           MAX(ingestion_date)                        AS latest
                    FROM planning_zones
                    """
                ),
            )
            .mappings()
            .first()
        )
        total = int(totals["total"] or 0)
        with_geom = int(totals["with_geom"] or 0)
        total_area = float(totals["area"] or 0.0) if total else None
        avg_conf, min_conf, max_conf = (
            totals["avg_conf"], totals["min_conf"], totals["max_conf"]
        )
        latest = _isoformat(totals["latest"])

        categories = [
            CategoryStat(
                zone_category=row["zone_category"] or "unclassified",
                zone_count=int(row["zone_count"]),
                total_area_sqm=float(row["area"] or 0.0),
                avg_confidence=(
                    round(float(row["avg_conf"]), 4)
                    if row["avg_conf"] is not None
                    else None
                ),
            )
            for row in _execute(
                db,
                text(
                    """
                    SELECT zone_category,
                           COUNT(*)                                   AS zone_count,
                           COALESCE(SUM(ST_Area(geom::geography)), 0) AS area,
                           AVG(data_confidence)                       AS avg_conf
                    FROM planning_zones
                    GROUP BY zone_category
                    ORDER BY zone_count DESC, zone_category
                    """
                ),
            )
            .mappings()
            .all()
        ]

        status_counts = {
            (row[0] or "unknown"): int(row[1])
            for row in _execute(
                db,
                text(
                    "SELECT validation_status, COUNT(*) FROM planning_zones "
                    "GROUP BY validation_status"
                ),
            ).all()
        }
        admin_codes = [
            row[0]
            for row in _execute(
                db,
                text(
                    "SELECT DISTINCT administrative_code FROM planning_zones "
                    "WHERE administrative_code IS NOT NULL "
                    "ORDER BY administrative_code"
                ),
            ).all()
        ]
    else:
        records = db.query(PlanningZone).limit(_FALLBACK_SCAN_LIMIT).all()
        if len(records) >= _FALLBACK_SCAN_LIMIT:
            notes.append(
                f"Fallback scan hit its {_FALLBACK_SCAN_LIMIT}-row limit; "
                "statistics may be incomplete. Run against PostGIS."
            )
        total = len(records)
        with_geom = 0
        total_area = 0.0
        per_category: dict[str, dict[str, Any]] = {}
        status_counts = {}
        confidences: list[float] = []
        admin_code_set: set[str] = set()
        latest_dt = None

        for zone in records:
            geometry = _load_wkt(zone.geom)
            area = _geodesic_area_sqm(geometry) or 0.0
            if geometry is not None:
                with_geom += 1
            total_area += area

            key = zone.zone_category or "unclassified"
            bucket = per_category.setdefault(
                key, {"zone_count": 0, "area": 0.0, "conf": []}
            )
            bucket["zone_count"] += 1
            bucket["area"] += area
            if zone.data_confidence is not None:
                bucket["conf"].append(float(zone.data_confidence))
                confidences.append(float(zone.data_confidence))

            state = zone.validation_status or "unknown"
            status_counts[state] = status_counts.get(state, 0) + 1
            if zone.administrative_code:
                admin_code_set.add(zone.administrative_code)
            if zone.ingestion_date is not None and (
                latest_dt is None or zone.ingestion_date > latest_dt
            ):
                latest_dt = zone.ingestion_date

        categories = sorted(
            (
                CategoryStat(
                    zone_category=key,
                    zone_count=bucket["zone_count"],
                    total_area_sqm=bucket["area"],
                    avg_confidence=(
                        round(sum(bucket["conf"]) / len(bucket["conf"]), 4)
                        if bucket["conf"]
                        else None
                    ),
                )
                for key, bucket in per_category.items()
            ),
            key=lambda c: (-c.zone_count, c.zone_category),
        )
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        min_conf = min(confidences) if confidences else None
        max_conf = max(confidences) if confidences else None
        admin_codes = sorted(admin_code_set)
        latest = _isoformat(latest_dt)
        total_area = total_area if total else None
        notes.append(
            "Areas are geodesic (WGS84) approximations computed outside the "
            "database; PostGIS ST_Area(::geography) is authoritative."
        )

    if total == 0:
        notes.append(
            "No planning zones have been ingested. Run "
            "worker/tasks/ingest_zoning_data.py."
        )
    elif with_geom < total:
        notes.append(
            f"{total - with_geom} of {total} zones have no geometry and are "
            "invisible to every spatial query."
        )

    return ZoningStatsResponse(
        has_data=total > 0,
        total_zones=total,
        zones_with_geometry=with_geom,
        zones_without_geometry=total - with_geom,
        total_area_sqm=total_area,
        distinct_categories=len(categories),
        categories=categories,
        validation_status=status_counts,
        confidence={
            "avg": round(float(avg_conf), 4) if avg_conf is not None else None,
            "min": float(min_conf) if min_conf is not None else None,
            "max": float(max_conf) if max_conf is not None else None,
        },
        administrative_codes=admin_codes,
        latest_ingestion_date=latest,
        spatial_backend=_backend_name(db),
        notes=notes,
    )


# =====================================================================
# 2. zone detail (declared last: `{project_id}` is the catch-all)
# =====================================================================


@router.get("/zones/{project_id}", response_model=ZoneDetail)
def get_zone(
    project_id: str = Path(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
) -> ZoneDetail:
    """One zone, with its boundary as GeoJSON (EPSG:4326, lng/lat order)."""
    if _is_postgis(db):
        row = (
            _execute(
                db,
                text(
                    f"""
                    SELECT {_SELECT_COLUMNS_WITH_GEOM}
                    FROM planning_zones z
                    WHERE z.project_id = :project_id
                    """
                ),
                {"project_id": project_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Planning zone not found")
        return _detail_from_mapping(row)

    zone = (
        db.query(PlanningZone)
        .filter(PlanningZone.project_id == project_id)
        .first()
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="Planning zone not found")
    return _detail_from_orm(zone, _load_wkt(zone.geom))


# =====================================================================
# 6. property <-> zoning validation
# =====================================================================


def _score_match(
    satellite_class: str | None, zoning_categories: Iterable[str]
) -> tuple[float | None, bool | None]:
    """Best score across every zone covering the point, and a strict verdict.

    ``match`` is True only at a full 1.0. A 0.5 partial pairing returns None —
    "cannot say" — because a boolean True there would be read downstream as
    zoning *confirming* the classifier, which a loose pairing does not do.
    Callers that want the softer signal read ``match_score``.

    ``match_score`` of None means "not assessable" (no satellite class, or no
    zone), deliberately distinct from 0.0 ("assessed, and it conflicts").
    """
    categories = [c for c in zoning_categories if c]
    if not satellite_class or not categories:
        return None, None

    compatible = COMPATIBLE_ZONING.get(satellite_class, set())
    partial = PARTIAL_ZONING.get(satellite_class, set())

    best = 0.0
    for category in categories:
        if category in compatible:
            best = 1.0
            break
        if category in partial:
            best = max(best, 0.5)
        elif category == "unclassified":
            # An unclassified zone is an absence of evidence, not a conflict.
            best = max(best, 0.5)
    return best, True if best == 1.0 else (False if best == 0.0 else None)


@router.post("/validate", response_model=ZoningValidationResponse)
def validate_property_zoning(
    payload: ZoningValidationRequest,
    db: Session = Depends(get_db),
) -> ZoningValidationResponse:
    """Compare a satellite land-use classification against official zoning.

    Read-only by design. Zoning is the authoritative side (confidence 0.95) and
    the satellite class is model output, so a mismatch is evidence about the
    *classifier* — or a genuine land-use change — and neither conclusion may be
    written back automatically. The caller decides what a mismatch means.
    """
    notes: list[str] = []
    listing_id = payload.listing_id
    satellite_class = payload.satellite_land_use
    satellite_conf = payload.satellite_confidence

    if listing_id is not None:
        listing = _listing_location(db, listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        if payload.lat is not None and payload.lng is not None:
            lat, lng = payload.lat, payload.lng
            notes.append(
                "Explicit lat/lng overrode the listing's stored coordinates."
            )
        elif listing.lat is None or listing.lng is None:
            raise HTTPException(
                status_code=422, detail="Listing has no coordinates"
            )
        else:
            lat, lng = float(listing.lat), float(listing.lng)

        if satellite_class is None and listing.satellite_land_use:
            satellite_class = listing.satellite_land_use
            satellite_conf = (
                satellite_conf
                if satellite_conf is not None
                else listing.satellite_confidence
            )
            notes.append(
                "Satellite class taken from the listing's stored classification."
            )
    else:
        lat, lng = float(payload.lat), float(payload.lng)  # type: ignore[arg-type]

    zones, spatial_notes = _zones_containing_point(db, lat, lng, limit=20)
    notes.extend(spatial_notes)

    categories = [z.zone_category for z in zones if z.zone_category]
    zoning_conf = (
        max((z.data_confidence or 0.0) for z in zones) if zones else None
    )
    score, match = _score_match(satellite_class, categories)

    if not zones:
        verdict = "no_zoning_data"
        explanation = (
            "No official planning zone covers this location, so the "
            "satellite classification cannot be checked against zoning."
        )
    elif satellite_class is None:
        verdict = "no_satellite_class"
        explanation = (
            "Zoning is known here, but no satellite land-use classification "
            "was supplied or stored, so there is nothing to compare."
        )
    elif score == 1.0:
        verdict = "match"
        explanation = (
            f"Satellite class '{satellite_class}' is consistent with zoning "
            f"category '{_primary(categories)}'."
        )
    elif score == 0.5:
        verdict = "partial_match"
        explanation = (
            f"Satellite class '{satellite_class}' is only loosely consistent "
            f"with zoning category '{_primary(categories)}'. Treat as "
            "inconclusive rather than as a violation."
        )
    else:
        verdict = "mismatch"
        explanation = (
            f"Satellite class '{satellite_class}' conflicts with zoning "
            f"category '{_primary(categories)}'. This is either an "
            "unpermitted land-use change or a classifier error; it is not, on "
            "its own, proof of either."
        )

    return ZoningValidationResponse(
        listing_id=listing_id,
        lat=lat,
        lng=lng,
        satellite_land_use=satellite_class,
        satellite_confidence=satellite_conf,
        zoning_categories=sorted(set(categories)),
        primary_zone_category=_primary(categories),
        zone_project_ids=[z.project_id for z in zones],
        zones_found=len(zones),
        match=match,
        match_score=score,
        zoning_confidence=zoning_conf,
        spatial_backend=_backend_name(db),
        verdict=verdict,
        explanation=explanation,
        notes=notes,
    )


def _primary(categories: list[str]) -> str | None:
    """The most specific zone's category — zones arrive smallest-area first."""
    return categories[0] if categories else None
