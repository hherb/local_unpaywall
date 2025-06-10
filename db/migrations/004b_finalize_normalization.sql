-- Migration 004b: Finalize Database Normalization
-- ================================================
-- 
-- This script finalizes the database normalization by dropping the old TEXT columns
-- and completing the location_type conversion. Run this ONLY after verifying that
-- migration 004 completed successfully and all data has been properly migrated.
--
-- WARNING: This script will permanently delete the old TEXT columns. Make sure you
-- have verified the migration worked correctly before running this script.
--
-- To verify before running this script:
-- 1. Check that lookup tables are populated:
--    SELECT COUNT(*) FROM unpaywall.license;
--    SELECT COUNT(*) FROM unpaywall.oa_status;
--    SELECT COUNT(*) FROM unpaywall.host_type;
--    SELECT COUNT(*) FROM unpaywall.work_type;
--
-- 2. Check that foreign key columns are populated:
--    SELECT COUNT(*) FROM unpaywall.doi_urls WHERE license_id IS NOT NULL;
--    SELECT COUNT(*) FROM unpaywall.doi_urls WHERE oa_status_id IS NOT NULL;
--    SELECT COUNT(*) FROM unpaywall.doi_urls WHERE host_type_id IS NOT NULL;
--    SELECT COUNT(*) FROM unpaywall.doi_urls WHERE work_type_id IS NOT NULL;
--
-- 3. Verify data integrity with sample queries:
--    SELECT d.doi, l.value as license, o.value as oa_status, h.value as host_type, w.value as work_type
--    FROM unpaywall.doi_urls d
--    LEFT JOIN unpaywall.license l ON d.license_id = l.id
--    LEFT JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
--    LEFT JOIN unpaywall.host_type h ON d.host_type_id = h.id
--    LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id
--    LIMIT 10;

-- Step 1: Drop old TEXT columns
-- These columns are no longer needed as data is now stored in lookup tables
ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS license;
ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS oa_status;
ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS host_type;
ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS work_type;

-- Step 2: Finalize location_type conversion
-- Drop old location_type column and rename the new CHAR(1) column
ALTER TABLE unpaywall.doi_urls DROP COLUMN IF EXISTS location_type;
ALTER TABLE unpaywall.doi_urls RENAME COLUMN location_type_new TO location_type;

-- Add NOT NULL constraint and check constraint for location_type
ALTER TABLE unpaywall.doi_urls ALTER COLUMN location_type SET NOT NULL;
ALTER TABLE unpaywall.doi_urls ADD CONSTRAINT chk_location_type 
CHECK (location_type IN ('p', 'a', 'b'));

-- Step 3: Create index for the new location_type column
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_location_type_new 
ON unpaywall.doi_urls(location_type);

-- Step 4: Drop old indexes that referenced the old TEXT columns
-- Note: PostgreSQL will automatically drop indexes when columns are dropped,
-- but we explicitly drop any remaining ones for clarity
DROP INDEX IF EXISTS idx_unpaywall_doi_urls_oa_status;
DROP INDEX IF EXISTS idx_unpaywall_doi_urls_host_type;
DROP INDEX IF EXISTS idx_unpaywall_doi_urls_work_type;

-- Step 5: Update any views that might reference the old columns
-- Create a view for backward compatibility that reconstructs the original format
CREATE OR REPLACE VIEW unpaywall.doi_urls_denormalized AS
SELECT 
    d.id,
    d.doi,
    d.url,
    d.pdf_url,
    d.openalex_id,
    d.title,
    d.publication_year,
    CASE d.location_type 
        WHEN 'p' THEN 'primary'
        WHEN 'a' THEN 'alternate'
        WHEN 'b' THEN 'best_oa'
        ELSE 'primary'
    END as location_type,
    d.version,
    l.value as license,
    h.value as host_type,
    o.value as oa_status,
    d.is_oa,
    w.value as work_type,
    d.is_retracted,
    d.url_quality_score,
    d.last_verified,
    d.created_at,
    d.updated_at,
    -- Include the normalized IDs for efficient joins
    d.license_id,
    d.oa_status_id,
    d.host_type_id,
    d.work_type_id
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
LEFT JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
LEFT JOIN unpaywall.host_type h ON d.host_type_id = h.id
LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id;

-- Grant permissions on the view
GRANT SELECT ON unpaywall.doi_urls_denormalized TO PUBLIC;

-- Add comment to the view
COMMENT ON VIEW unpaywall.doi_urls_denormalized IS 
'Denormalized view of doi_urls table that reconstructs original TEXT columns for backward compatibility';

-- Step 6: Update the public compatibility view if it exists
-- This maintains backward compatibility for applications still using the public schema
DROP VIEW IF EXISTS public.doi_urls;
CREATE VIEW public.doi_urls AS SELECT * FROM unpaywall.doi_urls_denormalized;
GRANT SELECT ON public.doi_urls TO PUBLIC;

-- Step 7: Record finalization completion
INSERT INTO unpaywall.schema_migrations (migration_id, description)
VALUES ('004b_finalize_normalization', 'Finalized database normalization by dropping old TEXT columns and completing location_type conversion')
ON CONFLICT (migration_id) DO NOTHING;

-- Step 8: Analyze tables for query planner optimization
ANALYZE unpaywall.doi_urls;
ANALYZE unpaywall.license;
ANALYZE unpaywall.oa_status;
ANALYZE unpaywall.host_type;
ANALYZE unpaywall.work_type;

-- Step 9: Display storage savings summary
-- This query will show the storage impact of the normalization
DO $$
DECLARE
    table_size_mb NUMERIC;
    total_rows BIGINT;
BEGIN
    -- Get table size and row count
    SELECT 
        pg_size_pretty(pg_total_relation_size('unpaywall.doi_urls'))::TEXT,
        COUNT(*)
    INTO table_size_mb, total_rows
    FROM unpaywall.doi_urls;
    
    RAISE NOTICE 'Database normalization completed successfully!';
    RAISE NOTICE 'Current table size: %', table_size_mb;
    RAISE NOTICE 'Total rows: %', total_rows;
    RAISE NOTICE 'Lookup tables created with foreign key references';
    RAISE NOTICE 'Location type converted to CHAR(1)';
    RAISE NOTICE 'Estimated storage savings: 70-160 bytes per row';
    RAISE NOTICE 'Backward compatibility view created: unpaywall.doi_urls_denormalized';
END $$;
