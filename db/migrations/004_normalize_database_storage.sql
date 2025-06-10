-- Migration 004: Normalize Database Storage
-- ==========================================
-- 
-- This migration normalizes the unpaywall.doi_urls table to conserve storage space
-- by creating lookup tables for redundant TEXT data and converting location_type
-- to a more efficient CHAR(1) representation.
--
-- Storage savings expected:
-- - license: ~20-50 bytes per row -> 4 bytes (foreign key)
-- - oa_status: ~10-20 bytes per row -> 4 bytes (foreign key)  
-- - host_type: ~15-30 bytes per row -> 4 bytes (foreign key)
-- - work_type: ~15-40 bytes per row -> 4 bytes (foreign key)
-- - location_type: ~8-15 bytes per row -> 1 byte (CHAR)
--
-- Total estimated savings: ~70-160 bytes per row
-- For 250M rows: ~17-40 GB storage reduction

-- Step 1: Create lookup tables for normalization
CREATE TABLE IF NOT EXISTS unpaywall.license (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unpaywall.oa_status (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unpaywall.host_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unpaywall.work_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add comments to tables
COMMENT ON TABLE unpaywall.license IS 'License information lookup table';
COMMENT ON TABLE unpaywall.oa_status IS 'Open access status lookup table';
COMMENT ON TABLE unpaywall.host_type IS 'Host type lookup table';
COMMENT ON TABLE unpaywall.work_type IS 'Work type lookup table';

-- Step 2: Populate lookup tables with existing unique values
INSERT INTO unpaywall.license (value)
SELECT DISTINCT license
FROM unpaywall.doi_urls 
WHERE license IS NOT NULL 
AND license != ''
ON CONFLICT (value) DO NOTHING;

INSERT INTO unpaywall.oa_status (value)
SELECT DISTINCT oa_status
FROM unpaywall.doi_urls 
WHERE oa_status IS NOT NULL 
AND oa_status != ''
ON CONFLICT (value) DO NOTHING;

INSERT INTO unpaywall.host_type (value)
SELECT DISTINCT host_type
FROM unpaywall.doi_urls 
WHERE host_type IS NOT NULL 
AND host_type != ''
ON CONFLICT (value) DO NOTHING;

INSERT INTO unpaywall.work_type (value)
SELECT DISTINCT work_type
FROM unpaywall.doi_urls 
WHERE work_type IS NOT NULL 
AND work_type != ''
ON CONFLICT (value) DO NOTHING;

-- Step 3: Add foreign key columns to main table
ALTER TABLE unpaywall.doi_urls 
ADD COLUMN IF NOT EXISTS license_id INTEGER;

ALTER TABLE unpaywall.doi_urls 
ADD COLUMN IF NOT EXISTS oa_status_id INTEGER;

ALTER TABLE unpaywall.doi_urls 
ADD COLUMN IF NOT EXISTS host_type_id INTEGER;

ALTER TABLE unpaywall.doi_urls 
ADD COLUMN IF NOT EXISTS work_type_id INTEGER;

-- Step 4: Add foreign key constraints
ALTER TABLE unpaywall.doi_urls 
ADD CONSTRAINT IF NOT EXISTS fk_doi_urls_license_id 
FOREIGN KEY (license_id) REFERENCES unpaywall.license(id);

ALTER TABLE unpaywall.doi_urls 
ADD CONSTRAINT IF NOT EXISTS fk_doi_urls_oa_status_id 
FOREIGN KEY (oa_status_id) REFERENCES unpaywall.oa_status(id);

ALTER TABLE unpaywall.doi_urls 
ADD CONSTRAINT IF NOT EXISTS fk_doi_urls_host_type_id 
FOREIGN KEY (host_type_id) REFERENCES unpaywall.host_type(id);

ALTER TABLE unpaywall.doi_urls 
ADD CONSTRAINT IF NOT EXISTS fk_doi_urls_work_type_id 
FOREIGN KEY (work_type_id) REFERENCES unpaywall.work_type(id);

-- Step 5: Update foreign key columns with data from lookup tables
UPDATE unpaywall.doi_urls 
SET license_id = lookup.id
FROM unpaywall.license lookup
WHERE unpaywall.doi_urls.license = lookup.value
AND unpaywall.doi_urls.license IS NOT NULL
AND unpaywall.doi_urls.license != '';

UPDATE unpaywall.doi_urls 
SET oa_status_id = lookup.id
FROM unpaywall.oa_status lookup
WHERE unpaywall.doi_urls.oa_status = lookup.value
AND unpaywall.doi_urls.oa_status IS NOT NULL
AND unpaywall.doi_urls.oa_status != '';

UPDATE unpaywall.doi_urls 
SET host_type_id = lookup.id
FROM unpaywall.host_type lookup
WHERE unpaywall.doi_urls.host_type = lookup.value
AND unpaywall.doi_urls.host_type IS NOT NULL
AND unpaywall.doi_urls.host_type != '';

UPDATE unpaywall.doi_urls 
SET work_type_id = lookup.id
FROM unpaywall.work_type lookup
WHERE unpaywall.doi_urls.work_type = lookup.value
AND unpaywall.doi_urls.work_type IS NOT NULL
AND unpaywall.doi_urls.work_type != '';

-- Step 6: Normalize location_type to CHAR(1)
-- Add new CHAR(1) column
ALTER TABLE unpaywall.doi_urls 
ADD COLUMN IF NOT EXISTS location_type_new CHAR(1);

-- Update with normalized values: 'primary' -> 'p', 'alternate' -> 'a', 'best_oa' -> 'b'
UPDATE unpaywall.doi_urls 
SET location_type_new = CASE 
    WHEN LOWER(location_type) = 'primary' THEN 'p'
    WHEN LOWER(location_type) = 'alternate' THEN 'a' 
    WHEN LOWER(location_type) = 'best_oa' THEN 'b'
    ELSE 'p'  -- Default to primary for unknown values
END;

-- Step 7: Drop old columns and rename new ones (commented out for safety)
-- Uncomment these lines after verifying the migration worked correctly:

-- DROP old TEXT columns
-- ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS license;
-- ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS oa_status;
-- ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS host_type;
-- ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS work_type;

-- Replace location_type
-- ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS location_type;
-- ALTER TABLE unpaywall.doi_urls RENAME COLUMN location_type_new TO location_type;
-- ALTER TABLE unpaywall.doi_urls ALTER COLUMN location_type SET NOT NULL;
-- ALTER TABLE unpaywall.doi_urls ADD CONSTRAINT chk_location_type CHECK (location_type IN ('p', 'a', 'b'));

-- Step 8: Create indexes for normalized columns
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_license_id ON unpaywall.doi_urls(license_id);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_oa_status_id ON unpaywall.doi_urls(oa_status_id);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_host_type_id ON unpaywall.doi_urls(host_type_id);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_work_type_id ON unpaywall.doi_urls(work_type_id);

-- Step 9: Set permissions for lookup tables
GRANT SELECT ON unpaywall.license TO PUBLIC;
GRANT SELECT ON unpaywall.oa_status TO PUBLIC;
GRANT SELECT ON unpaywall.host_type TO PUBLIC;
GRANT SELECT ON unpaywall.work_type TO PUBLIC;

GRANT INSERT, UPDATE, DELETE ON unpaywall.license TO PUBLIC;
GRANT INSERT, UPDATE, DELETE ON unpaywall.oa_status TO PUBLIC;
GRANT INSERT, UPDATE, DELETE ON unpaywall.host_type TO PUBLIC;
GRANT INSERT, UPDATE, DELETE ON unpaywall.work_type TO PUBLIC;

GRANT USAGE, SELECT ON SEQUENCE unpaywall.license_id_seq TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE unpaywall.oa_status_id_seq TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE unpaywall.host_type_id_seq TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE unpaywall.work_type_id_seq TO PUBLIC;

-- Step 10: Record migration completion
INSERT INTO unpaywall.schema_migrations (migration_id, description)
VALUES ('004_normalize_database_storage', 'Normalize database storage by creating lookup tables and converting location_type to CHAR(1)')
ON CONFLICT (migration_id) DO NOTHING;
