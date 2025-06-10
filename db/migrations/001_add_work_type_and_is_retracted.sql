-- Migration 001: Add work_type and is_retracted columns to doi_urls table
-- This migration integrates the metadata fields from doi_metadata into the main table

-- Add new columns to doi_urls table
ALTER TABLE doi_urls 
ADD COLUMN IF NOT EXISTS work_type TEXT,
ADD COLUMN IF NOT EXISTS is_retracted BOOLEAN DEFAULT FALSE;

-- Create indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_doi_urls_work_type ON doi_urls(work_type);
CREATE INDEX IF NOT EXISTS idx_doi_urls_is_retracted ON doi_urls(is_retracted);

-- If doi_metadata table exists, migrate data to doi_urls
-- This is a safe operation that will only run if the table exists
DO $$
BEGIN
    -- Check if doi_metadata table exists
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'doi_metadata') THEN
        -- Update doi_urls with data from doi_metadata where available
        UPDATE doi_urls 
        SET 
            work_type = dm.work_type,
            is_retracted = dm.is_retracted,
            updated_at = CURRENT_TIMESTAMP
        FROM doi_metadata dm 
        WHERE doi_urls.doi = dm.doi 
        AND (doi_urls.work_type IS NULL OR doi_urls.is_retracted IS NULL);
        
        RAISE NOTICE 'Migrated data from doi_metadata to doi_urls';
    ELSE
        RAISE NOTICE 'doi_metadata table does not exist, skipping data migration';
    END IF;
END $$;

-- Optional: Drop the doi_metadata table after migration
-- Uncomment the following lines if you want to remove the table immediately
-- WARNING: This will permanently delete the doi_metadata table and all its data
/*
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'doi_metadata') THEN
        DROP TABLE doi_metadata CASCADE;
        RAISE NOTICE 'Dropped doi_metadata table';
    END IF;
END $$;
*/
