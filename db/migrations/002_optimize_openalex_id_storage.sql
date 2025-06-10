-- Migration 002: Optimize OpenAlex ID storage
-- Convert openalex_id from TEXT (full URL) to BIGINT (numeric part only)
-- This saves ~27 bytes per record and improves query performance

-- Step 1: Add new column for numeric OpenAlex ID
ALTER TABLE doi_urls 
ADD COLUMN IF NOT EXISTS openalex_work_id BIGINT;

-- Step 2: Create function to extract numeric part from OpenAlex URL
CREATE OR REPLACE FUNCTION extract_openalex_work_id(openalex_url TEXT) 
RETURNS BIGINT AS $$
BEGIN
    -- Extract numeric part from URLs like "https://openalex.org/W1982051859"
    IF openalex_url IS NULL OR openalex_url = '' THEN
        RETURN NULL;
    END IF;
    
    -- Handle both full URLs and just the W-prefixed IDs
    IF openalex_url LIKE 'https://openalex.org/W%' THEN
        -- Extract number after "https://openalex.org/W"
        RETURN SUBSTRING(openalex_url FROM 'https://openalex\.org/W(\d+)')::BIGINT;
    ELSIF openalex_url LIKE 'W%' THEN
        -- Extract number after "W"
        RETURN SUBSTRING(openalex_url FROM 'W(\d+)')::BIGINT;
    ELSE
        -- Try to extract any numeric part
        RETURN REGEXP_REPLACE(openalex_url, '[^0-9]', '', 'g')::BIGINT;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- Return NULL if conversion fails
        RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 3: Populate new column with extracted numeric IDs
UPDATE doi_urls 
SET openalex_work_id = extract_openalex_work_id(openalex_id)
WHERE openalex_id IS NOT NULL 
AND openalex_work_id IS NULL;

-- Step 4: Create index on new column
CREATE INDEX IF NOT EXISTS idx_doi_urls_openalex_work_id ON doi_urls(openalex_work_id);

-- Step 5: Create function to reconstruct full OpenAlex URL from numeric ID
CREATE OR REPLACE FUNCTION openalex_work_url(work_id BIGINT) 
RETURNS TEXT AS $$
BEGIN
    IF work_id IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN 'https://openalex.org/W' || work_id::TEXT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 6: Create view for backward compatibility
CREATE OR REPLACE VIEW doi_urls_with_full_openalex_id AS
SELECT 
    id,
    doi,
    url,
    pdf_url,
    openalex_work_url(openalex_work_id) as openalex_id,  -- Reconstructed full URL
    openalex_work_id,  -- New numeric field
    title,
    publication_year,
    location_type,
    version,
    license,
    host_type,
    oa_status,
    is_oa,
    work_type,
    is_retracted,
    url_quality_score,
    last_verified,
    created_at,
    updated_at
FROM doi_urls;

-- Step 7: Show migration statistics
DO $$
DECLARE
    total_records INTEGER;
    records_with_openalex INTEGER;
    records_converted INTEGER;
    old_size_estimate BIGINT;
    new_size_estimate BIGINT;
    savings_estimate BIGINT;
BEGIN
    -- Count records
    SELECT COUNT(*) INTO total_records FROM doi_urls;
    SELECT COUNT(*) INTO records_with_openalex FROM doi_urls WHERE openalex_id IS NOT NULL;
    SELECT COUNT(*) INTO records_converted FROM doi_urls WHERE openalex_work_id IS NOT NULL;
    
    -- Estimate storage savings (approximate)
    old_size_estimate := records_with_openalex * 35;  -- ~35 bytes per TEXT field
    new_size_estimate := records_converted * 8;       -- 8 bytes per BIGINT
    savings_estimate := old_size_estimate - new_size_estimate;
    
    RAISE NOTICE 'OpenAlex ID Migration Statistics:';
    RAISE NOTICE '  Total records: %', total_records;
    RAISE NOTICE '  Records with OpenAlex ID: %', records_with_openalex;
    RAISE NOTICE '  Records successfully converted: %', records_converted;
    RAISE NOTICE '  Estimated storage savings: % bytes (% KB)', savings_estimate, savings_estimate / 1024;
    
    IF records_converted < records_with_openalex THEN
        RAISE NOTICE 'WARNING: % records could not be converted', records_with_openalex - records_converted;
    END IF;
END $$;

-- Note: The old openalex_id column is kept for now to ensure backward compatibility
-- After verifying the migration works correctly, you can drop it with:
-- ALTER TABLE doi_urls DROP COLUMN openalex_id;

-- Note: To make the new column the primary openalex identifier, you would:
-- 1. Update application code to use openalex_work_id instead of openalex_id
-- 2. Drop the compatibility view
-- 3. Drop the old openalex_id column
-- 4. Rename openalex_work_id to openalex_id if desired
