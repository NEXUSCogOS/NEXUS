-- Migration 004: Create planning_zones base table
-- Applies: 2026-08-15
-- Reversible: Yes (DROP TABLE planning_zones)
--
-- The zoning integration plan assumed planning_zones already existed, but no
-- migration or model in this repo ever created it. This migration establishes
-- the original schema so that 005_extend_planning_zones.sql (ALTER TABLE only)
-- can apply cleanly against a fresh database.

BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS planning_zones (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    zone_type VARCHAR(100),
    description TEXT,
    geom GEOMETRY(POLYGON, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_planning_zones_geom ON planning_zones USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_planning_zones_zone_type ON planning_zones(zone_type);

COMMIT;
