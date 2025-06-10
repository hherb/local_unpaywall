-- Migration 003: Create unpaywall schema and move tables
-- This migration introduces namespaces by creating an "unpaywall" schema
-- and moving all tables from the public schema to the unpaywall schema

-- Step 1: Create the unpaywall schema
CREATE SCHEMA IF NOT EXISTS unpaywall;

-- Step 2: Check if tables exist in public schema and move them
DO $$
DECLARE
    table_exists_public BOOLEAN;
    import_table_exists_public BOOLEAN;
BEGIN
    -- Check if doi_urls table exists in public schema
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'doi_urls'
    ) INTO table_exists_public;
    
    -- Check if import_progress table exists in public schema
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'import_progress'
    ) INTO import_table_exists_public;
    
    -- Move doi_urls table if it exists in public schema
    IF table_exists_public THEN
        RAISE NOTICE 'Moving doi_urls table from public to unpaywall schema';
        ALTER TABLE public.doi_urls SET SCHEMA unpaywall;
    ELSE
        RAISE NOTICE 'doi_urls table not found in public schema, will create in unpaywall schema';
    END IF;
    
    -- Move import_progress table if it exists in public schema
    IF import_table_exists_public THEN
        RAISE NOTICE 'Moving import_progress table from public to unpaywall schema';
        ALTER TABLE public.import_progress SET SCHEMA unpaywall;
    ELSE
        RAISE NOTICE 'import_progress table not found in public schema, will create in unpaywall schema';
    END IF;
END $$;

-- Step 3: Create tables in unpaywall schema if they don't exist
CREATE TABLE IF NOT EXISTS unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,
    title TEXT,
    publication_year INTEGER,
    location_type TEXT NOT NULL,
    version TEXT,
    license TEXT,
    host_type TEXT,
    oa_status TEXT,
    is_oa BOOLEAN DEFAULT FALSE,
    work_type TEXT,
    is_retracted BOOLEAN DEFAULT FALSE,
    url_quality_score INTEGER DEFAULT 50,
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unpaywall.import_progress (
    import_id TEXT PRIMARY KEY,
    csv_file_path TEXT NOT NULL,
    csv_file_hash TEXT NOT NULL,
    total_rows INTEGER NOT NULL,
    processed_rows INTEGER DEFAULT 0,
    last_batch_id INTEGER DEFAULT 0,
    status TEXT DEFAULT 'in_progress',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unpaywall.schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Step 4: Create indexes for unpaywall.doi_urls
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi ON unpaywall.doi_urls(doi);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_url ON unpaywall.doi_urls(url);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_pdf_url ON unpaywall.doi_urls(pdf_url) WHERE pdf_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi_location_type ON unpaywall.doi_urls(doi, location_type);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_oa_status ON unpaywall.doi_urls(oa_status) WHERE is_oa = TRUE;
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_host_type ON unpaywall.doi_urls(host_type);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_publication_year ON unpaywall.doi_urls(publication_year);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_work_type ON unpaywall.doi_urls(work_type);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_is_retracted ON unpaywall.doi_urls(is_retracted);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_openalex_work_id ON unpaywall.doi_urls(openalex_id);

-- Step 5: Create indexes for unpaywall.import_progress
CREATE INDEX IF NOT EXISTS idx_unpaywall_import_progress_file_path ON unpaywall.import_progress(csv_file_path);
CREATE INDEX IF NOT EXISTS idx_unpaywall_import_progress_status ON unpaywall.import_progress(status);

-- Step 6: Add unique constraint to unpaywall.doi_urls
DO $$ 
BEGIN
    BEGIN
        ALTER TABLE unpaywall.doi_urls ADD CONSTRAINT unique_unpaywall_doi_url UNIQUE(doi, url);
        RAISE NOTICE 'Added unique constraint to unpaywall.doi_urls';
    EXCEPTION
        WHEN duplicate_table THEN
            RAISE NOTICE 'Unique constraint already exists on unpaywall.doi_urls';
    END;
END $$;

-- Step 7: Migrate existing schema_migrations data if it exists
DO $$
BEGIN
    -- Check if schema_migrations table exists in public schema
    IF EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'schema_migrations'
    ) THEN
        -- Copy existing migration records to unpaywall schema
        INSERT INTO unpaywall.schema_migrations (migration_id, applied_at, description)
        SELECT migration_id, applied_at, description
        FROM public.schema_migrations
        ON CONFLICT (migration_id) DO NOTHING;

        RAISE NOTICE 'Migrated existing schema_migrations data to unpaywall schema';
    ELSE
        RAISE NOTICE 'No existing schema_migrations table found in public schema';
    END IF;
END $$;

-- Step 8: Create compatibility views in public schema for backward compatibility
-- These views allow existing code to continue working while transitioning to the new schema

CREATE OR REPLACE VIEW public.doi_urls AS
SELECT * FROM unpaywall.doi_urls;

CREATE OR REPLACE VIEW public.import_progress AS
SELECT * FROM unpaywall.import_progress;

-- Step 9: Grant appropriate permissions
-- Grant usage on the schema
GRANT USAGE ON SCHEMA unpaywall TO PUBLIC;

-- Grant permissions on tables
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.doi_urls TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.import_progress TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.schema_migrations TO PUBLIC;

-- Grant permissions on sequences
GRANT USAGE, SELECT ON SEQUENCE unpaywall.doi_urls_id_seq TO PUBLIC;

-- Step 10: Update search_path to include unpaywall schema
-- This allows unqualified table names to find tables in the unpaywall schema
-- Note: This affects the current session only. For permanent changes,
-- update postgresql.conf or set it per database/user

-- Show current search_path
DO $$
DECLARE
    current_path TEXT;
BEGIN
    SHOW search_path INTO current_path;
    RAISE NOTICE 'Current search_path: %', current_path;

    -- Add unpaywall to search_path if not already present
    IF position('unpaywall' in current_path) = 0 THEN
        SET search_path = unpaywall, public;
        RAISE NOTICE 'Updated search_path to include unpaywall schema';
    ELSE
        RAISE NOTICE 'unpaywall schema already in search_path';
    END IF;
END $$;

-- Step 11: Show migration statistics
DO $$
DECLARE
    doi_urls_count INTEGER;
    import_progress_count INTEGER;
    schema_migrations_count INTEGER;
BEGIN
    -- Count records in new schema
    SELECT COUNT(*) INTO doi_urls_count FROM unpaywall.doi_urls;
    SELECT COUNT(*) INTO import_progress_count FROM unpaywall.import_progress;
    SELECT COUNT(*) INTO schema_migrations_count FROM unpaywall.schema_migrations;

    RAISE NOTICE 'Migration 003 completed successfully';
    RAISE NOTICE 'unpaywall.doi_urls contains % records', doi_urls_count;
    RAISE NOTICE 'unpaywall.import_progress contains % records', import_progress_count;
    RAISE NOTICE 'unpaywall.schema_migrations contains % records', schema_migrations_count;
    RAISE NOTICE 'Compatibility views created in public schema';
    RAISE NOTICE 'All indexes and constraints have been recreated';
    RAISE NOTICE 'Unpaywall functionality is now completely self-contained';
END $$;

-- Note: After verifying the migration works correctly and updating application code,
-- you can drop the compatibility views with:
-- DROP VIEW IF EXISTS public.doi_urls CASCADE;
-- DROP VIEW IF EXISTS public.import_progress CASCADE;
--
-- The unpaywall functionality is now completely self-contained within the unpaywall schema:
-- - unpaywall.doi_urls
-- - unpaywall.import_progress
-- - unpaywall.schema_migrations
-- All indexes, constraints, and migration tracking are within the unpaywall namespace.
