BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS data_class VARCHAR(20) NOT NULL DEFAULT 'observed',
    ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS observed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS source_confidence DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS raw_payload JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_listings_data_class'
    ) THEN
        ALTER TABLE listings
        ADD CONSTRAINT chk_listings_data_class
        CHECK (data_class IN ('observed', 'derived', 'synthetic'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_listings_validation_status'
    ) THEN
        ALTER TABLE listings
        ADD CONSTRAINT chk_listings_validation_status
        CHECK (validation_status IN ('pending', 'accepted', 'rejected'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_listings_source_confidence'
    ) THEN
        ALTER TABLE listings
        ADD CONSTRAINT chk_listings_source_confidence
        CHECK (
            source_confidence IS NULL OR
            source_confidence BETWEEN 0.0 AND 1.0
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_listings_validation
ON listings(validation_status);

CREATE INDEX IF NOT EXISTS idx_listings_data_class
ON listings(data_class);

CREATE INDEX IF NOT EXISTS idx_listings_observed
ON listings(observed_at DESC);

INSERT INTO schema_migrations(version, description)
VALUES ('002', 'Listing provenance, validation and data-class governance')
ON CONFLICT (version) DO NOTHING;

COMMIT;
