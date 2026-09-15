"""Ingestion pipeline for Vietnamese urban planning (zoning) data.

Source records come from the national planning portal
(quyhoach.xaydung.gov.vn) exports, one JSON object per planning project:

    {
      "id": "c4",
      "fullName": "Quy hoạch phân khu tỷ lệ 1/5000 ...",
      "type": "QHXD_PK",
      "dvhc": ["26380", "26374", "731"],
      "geometries": "[[[lng, lat], [lng, lat], ...]]",   # JSON-encoded string
      "nameMap": "{\"Đất ở thấp tầng\": {\"id\": \"OTT\", ...}}",  # JSON string
      ...
    }

The pipeline normalises the Vietnamese land-use vocabulary into DatAI
categories, converts the `[lng, lat]` ring arrays into EPSG:4326 polygons and
upserts them into `planning_zones` (migrations 004 + 005).

CLI:
    PYTHONPATH=backend python worker/tasks/ingest_zoning_data.py \
        data/zoning_raw/dong_nai_2024.json "Dong Nai" 0.95
"""

from __future__ import annotations

import json
import logging
import os
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import Polygon, mapping
from shapely.validation import make_valid

# `PYTHONPATH=backend` puts `app` on the path.
from app.models import PlanningZone  # noqa: E402

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Land-use vocabulary
# --------------------------------------------------------------------------

#: Vietnamese land-use terms -> normalised DatAI categories. Keys are matched
#: case-insensitively and diacritic-insensitively against a *substring* of the
#: source label, so "Khu cây xanh - Công viên - Cấp đô thị" resolves to
#: `green_space` via "cay xanh".
LAND_USE_MAP: Dict[str, str] = {
    # Residential
    "dat o thap tang": "residential_low",
    "dat o cao tang": "residential_high",
    "dat o": "residential",
    "nha o": "residential",
    "dan cu": "residential",
    # Commercial / services
    "dat thuong mai": "commercial",
    "thuong mai": "commercial",
    "dich vu": "commercial",
    "khu trung tam cong cong": "public_service",
    "cong cong": "public_service",
    "hanh chinh": "administrative",
    # Industrial
    "dat cong nghiep": "industrial",
    "cong nghiep": "industrial",
    "kho tang": "industrial",
    "tieu thu cong nghiep": "industrial",
    # Green / water
    "cay xanh": "green_space",
    "cong vien": "green_space",
    "the duc the thao": "green_space",
    "song ngoi": "water",
    "ao ho": "water",
    "mat nuoc": "water",
    "kenh": "water",
    # Agriculture
    "dat nong nghiep": "agricultural",
    "nong nghiep": "agricultural",
    "lua": "agricultural",
    "trong cay": "agricultural",
    "lam nghiep": "forestry",
    "rung": "forestry",
    # Infrastructure / transport
    "duong giao thong": "transport",
    "giao thong": "transport",
    "bai do xe": "transport",
    "ben xe": "transport",
    "ha tang ky thuat": "infrastructure",
    "dau moi ha tang": "infrastructure",
    "nghia trang": "cemetery",
    # Social infrastructure
    "dat giao duc": "education",
    "giao duc": "education",
    "truong": "education",
    "dat y te": "healthcare",
    "y te": "healthcare",
    "benh vien": "healthcare",
    "dat ton giao": "religious",
    "ton giao": "religious",
    "di tich": "heritage",
    "du lich": "tourism",
    "quoc phong": "military",
    "an ninh": "military",
}

#: Longest keys first so "dat o thap tang" wins over "dat o".
_LAND_USE_KEYS = sorted(LAND_USE_MAP, key=len, reverse=True)

UNKNOWN_CATEGORY = "unclassified"

#: Vietnamese project-type codes -> readable zone_type values.
ZONE_TYPE_MAP: Dict[str, str] = {
    "QHXD_PK": "subdivision_plan",
    "QHXD_CT": "detailed_plan",
    "QHXD_C": "general_plan",
    "QHSDD": "land_use_plan",
    "QHT": "master_plan",
}


def _strip_diacritics(value: str) -> str:
    """Fold Vietnamese diacritics (and đ/Đ) down to plain ASCII lowercase."""
    value = value.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).lower().strip()


def normalize_land_use_category(vietnamese_name: str) -> str:
    """Map a Vietnamese land-use label to a normalised DatAI category.

    Matching is diacritic- and case-insensitive and uses the longest matching
    keyword, so decorated labels ("Khu cây xanh cách ly") still resolve.
    Returns ``"unclassified"`` when nothing matches or input is empty.
    """
    if not vietnamese_name or not isinstance(vietnamese_name, str):
        return UNKNOWN_CATEGORY

    normalized = _strip_diacritics(vietnamese_name)
    if not normalized:
        return UNKNOWN_CATEGORY

    # Earliest match wins, longest key breaking ties. The head of a Vietnamese
    # land-use label carries its primary meaning ("Khu cây xanh - giao thông"
    # is a green buffer, not a road), while the longest-key tiebreak keeps
    # "Đất ở thấp tầng" from collapsing into the generic "đất ở".
    best: Optional[Tuple[int, int, str]] = None
    for key in _LAND_USE_KEYS:
        position = normalized.find(key)
        if position < 0:
            continue
        candidate = (position, -len(key), key)
        if best is None or candidate < best:
            best = candidate

    if best is not None:
        return LAND_USE_MAP[best[2]]

    logger.debug("Unmapped land-use label: %r", vietnamese_name)
    return UNKNOWN_CATEGORY


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def parse_geometries(geom_string: Any) -> Optional[Polygon]:
    """Parse a source ``geometries`` value into a shapely :class:`Polygon`.

    The source encodes rings as ``[[[lng, lat], ...], ...]`` — the first ring
    is the exterior, any further rings are holes. The value arrives either as
    a JSON-encoded string or as an already-decoded list.

    Returns ``None`` (never raises) when the value is missing, malformed, or
    has fewer than 3 distinct coordinates.
    """
    if geom_string is None:
        return None

    if isinstance(geom_string, str):
        text = geom_string.strip()
        if not text:
            return None
        try:
            rings = json.loads(text)
        except (ValueError, TypeError) as exc:
            logger.warning("Unparseable geometry JSON: %s", exc)
            return None
    elif isinstance(geom_string, (list, tuple)):
        rings = geom_string
    else:
        logger.warning("Unsupported geometry type: %s", type(geom_string))
        return None

    if not isinstance(rings, (list, tuple)) or not rings:
        return None

    # Tolerate a bare ring: [[lng, lat], [lng, lat], ...]
    first = rings[0]
    if (
        isinstance(first, (list, tuple))
        and len(first) == 2
        and all(isinstance(c, (int, float)) for c in first)
    ):
        rings = [rings]

    def _coords(ring: Any) -> List[Tuple[float, float]]:
        out: List[Tuple[float, float]] = []
        if not isinstance(ring, (list, tuple)):
            return out
        for point in ring:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            lng, lat = point[0], point[1]
            if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
                continue
            if isinstance(lng, bool) or isinstance(lat, bool):
                continue
            out.append((float(lng), float(lat)))
        return out

    exterior = _coords(rings[0])
    if len(set(exterior)) < 3:
        logger.warning("Geometry has fewer than 3 distinct coordinates; skipping")
        return None

    holes = [c for c in (_coords(r) for r in rings[1:]) if len(set(c)) >= 3]

    try:
        polygon = Polygon(exterior, holes)
    except (ValueError, TypeError) as exc:
        logger.warning("Could not build polygon: %s", exc)
        return None

    if polygon.is_empty:
        return None

    if not polygon.is_valid:
        repaired = make_valid(polygon)
        # make_valid may return a collection; keep the largest polygon part so
        # the result still fits a GEOMETRY(POLYGON, 4326) column.
        polygon = _largest_polygon(repaired)
        if polygon is None:
            logger.warning("Geometry could not be repaired into a polygon")
            return None

    return polygon


def _largest_polygon(geometry: Any) -> Optional[Polygon]:
    if geometry is None or geometry.is_empty:
        return None
    if isinstance(geometry, Polygon):
        return geometry
    parts = [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]
    if not parts:
        return None
    return max(parts, key=lambda g: g.area)


# --------------------------------------------------------------------------
# Category extraction
# --------------------------------------------------------------------------


def extract_zone_category(nameMap_dict: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """Extract the primary category and sub-categories from a ``nameMap``.

    ``nameMap`` maps a Vietnamese land-use label to ``{"id": ..., "color": ...}``.
    The primary category is the most frequent normalised category (ties broken
    by first appearance); sub-categories preserve every entry with its original
    label, source code, colour and normalised category.

    Accepts a dict or a JSON string. Returns ``("unclassified", [])`` when the
    input is missing or unusable.
    """
    if isinstance(nameMap_dict, str):
        text = nameMap_dict.strip()
        if not text:
            return UNKNOWN_CATEGORY, []
        try:
            nameMap_dict = json.loads(text)
        except (ValueError, TypeError) as exc:
            logger.warning("Unparseable nameMap JSON: %s", exc)
            return UNKNOWN_CATEGORY, []

    if not isinstance(nameMap_dict, dict) or not nameMap_dict:
        return UNKNOWN_CATEGORY, []

    sub_categories: List[Dict[str, Any]] = []
    order: List[str] = []
    counts: Dict[str, int] = {}

    for label, meta in nameMap_dict.items():
        if not isinstance(label, str) or not label.strip():
            continue
        meta = meta if isinstance(meta, dict) else {}
        category = normalize_land_use_category(label)
        sub_categories.append(
            {
                "vietnamese_name": label.strip(),
                "code": meta.get("id"),
                "color": meta.get("color"),
                "category": category,
            }
        )
        if category not in counts:
            order.append(category)
        counts[category] = counts.get(category, 0) + 1

    if not sub_categories:
        return UNKNOWN_CATEGORY, []

    # Prefer a real classification over "unclassified" when both are present.
    ranked = [c for c in order if c != UNKNOWN_CATEGORY] or order
    primary = max(ranked, key=lambda c: (counts[c], -order.index(c)))

    return primary, sub_categories


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


def _session_factory():
    """Build a Session bound to DATABASE_URL (or ZONING_DATABASE_URL)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = os.getenv("ZONING_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        engine = create_engine(url, pool_pre_ping=True)
    else:  # fall back to the app's configured engine
        from app.db import engine  # noqa: WPS433
    return sessionmaker(bind=engine)()


def _geom_value(polygon: Optional[Polygon], session) -> Optional[Any]:
    """Render a polygon for the bound dialect (WKT on SQLite, WKTElement on PostGIS)."""
    if polygon is None:
        return None
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        return polygon.wkt
    from geoalchemy2.elements import WKTElement

    return WKTElement(polygon.wkt, srid=4326)


def _administrative_code(record: Dict[str, Any]) -> Optional[str]:
    for key in ("dvhc", "dvhcInside", "dvhcIntersect"):
        codes = record.get(key)
        if isinstance(codes, list) and codes:
            return str(codes[0])
    return None


def ingest_zoning_data(
    json_source_path: str,
    province: str = "Dong Nai",
    confidence: float = 0.95,
    session=None,
) -> Dict[str, Any]:
    """Ingest a raw zoning JSON export into ``planning_zones``.

    Existing rows are matched on ``project_id`` and updated in place, so the
    pipeline is idempotent and safe to re-run as the export grows.

    Returns a summary dict: ``total_records``, ``inserted``, ``updated``,
    ``skipped_no_geometry``, ``errors`` and ``province``.
    """
    with open(json_source_path, "r", encoding="utf-8") as handle:
        records = json.load(handle)

    if isinstance(records, dict):
        records = records.get("data") or records.get("projects") or [records]
    if not isinstance(records, list):
        raise ValueError(f"Unsupported zoning JSON structure in {json_source_path}")

    owns_session = session is None
    session = session or _session_factory()

    summary: Dict[str, Any] = {
        "total_records": len(records),
        "inserted": 0,
        "updated": 0,
        "skipped_no_geometry": 0,
        "errors": [],
        "province": province,
        "source_file": json_source_path,
    }

    try:
        for record in records:
            if not isinstance(record, dict):
                summary["errors"].append("non-object record skipped")
                continue

            project_id = record.get("id")
            if not project_id:
                summary["errors"].append("record without id skipped")
                continue
            project_id = str(project_id)

            try:
                polygon = parse_geometries(record.get("geometries"))
                if polygon is None:
                    summary["skipped_no_geometry"] += 1
                    logger.warning("No usable geometry for project %s", project_id)
                    continue

                category, sub_categories = extract_zone_category(record.get("nameMap"))

                values = {
                    "project_name": record.get("fullName")
                    or record.get("niceName")
                    or project_id,
                    "name": record.get("niceName")
                    or record.get("name")
                    or project_id,
                    "zone_type": ZONE_TYPE_MAP.get(
                        record.get("type"), (record.get("type") or "").lower() or None
                    ),
                    "description": record.get("desc"),
                    "zone_category": category,
                    "sub_categories": sub_categories,
                    "administrative_code": _administrative_code(record),
                    "source_url": record.get("sourceUrl"),
                    "data_confidence": confidence,
                    "validation_status": "ingested",
                    "geom": _geom_value(polygon, session),
                }

                existing = (
                    session.query(PlanningZone)
                    .filter_by(project_id=project_id)
                    .one_or_none()
                )
                if existing is not None:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    summary["updated"] += 1
                else:
                    session.add(PlanningZone(project_id=project_id, **values))
                    summary["inserted"] += 1

                session.flush()
            except Exception as exc:  # noqa: BLE001 - one bad record must not abort the run
                session.rollback()
                logger.exception("Failed to ingest project %s", project_id)
                summary["errors"].append(f"{project_id}: {exc}")

        session.commit()
    finally:
        if owns_session:
            session.close()

    return summary


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def export_to_geojson(output_path: str, session=None) -> Dict[str, Any]:
    """Export every ingested zone to a GeoJSON FeatureCollection.

    Returns the FeatureCollection that was written.
    """
    owns_session = session is None
    session = session or _session_factory()

    try:
        features = []
        for zone in session.query(PlanningZone).order_by(PlanningZone.id).all():
            geometry = _zone_geometry(zone, session)
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "project_id": zone.project_id,
                        "project_name": zone.project_name,
                        "name": zone.name,
                        "zone_type": zone.zone_type,
                        "zone_category": zone.zone_category,
                        "sub_categories": zone.sub_categories,
                        "administrative_code": zone.administrative_code,
                        "data_confidence": zone.data_confidence,
                        "validation_status": zone.validation_status,
                        "source_url": zone.source_url,
                    },
                }
            )
    finally:
        if owns_session:
            session.close()

    collection = {"type": "FeatureCollection", "features": features}

    directory = os.path.dirname(os.path.abspath(output_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(collection, handle, ensure_ascii=False)

    logger.info("Exported %d zones to %s", len(features), output_path)
    return collection


def _jsonify(value: Any) -> Any:
    """Turn shapely's tuple-based coordinate sequences into JSON lists."""
    if isinstance(value, tuple):
        return [_jsonify(v) for v in value]
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    return value


def _zone_geometry(zone: PlanningZone, session) -> Optional[Dict[str, Any]]:
    """Convert a stored geometry back to a GeoJSON geometry dict."""
    raw = zone.geom
    if raw is None:
        return None

    from shapely import wkb, wkt

    try:
        if isinstance(raw, str):
            return _jsonify(mapping(wkt.loads(raw)))
        # GeoAlchemy2 WKBElement from PostGIS
        data = getattr(raw, "desc", None)
        if data is not None:
            return _jsonify(mapping(wkb.loads(data, hex=True)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not decode geometry for %s: %s", zone.project_id, exc)
    return None


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "usage: ingest_zoning_data.py <json_path> [province] [confidence]",
            file=sys.stderr,
        )
        return 2

    json_path = argv[0]
    province = argv[1] if len(argv) > 1 else "Dong Nai"
    confidence = float(argv[2]) if len(argv) > 2 else 0.95

    summary = ingest_zoning_data(json_path, province, confidence)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
