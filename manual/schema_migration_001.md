# Schema Migration 001: Integration of work_type and is_retracted

## Overview

This migration integrates the `work_type` and `is_retracted` fields from the previously unused `doi_metadata` table directly into the main `doi_urls` table. This simplifies the schema and eliminates redundant data storage.

## Changes Made

### 1. Schema Updates

**Added columns to `doi_urls` table:**
- `work_type TEXT` - The type of work (e.g., 'journal-article', 'book-chapter', 'preprint')
- `is_retracted BOOLEAN DEFAULT FALSE` - Whether the work has been retracted

**Added indexes:**
- `idx_doi_urls_work_type` - For efficient filtering by work type
- `idx_doi_urls_is_retracted` - For efficient filtering of retracted works

### 2. Data Extraction Updates

**OpenAlex Extractor (`openalex_unpaywall_extractor.py`):**
- Now extracts `work.get('type')` as `work_type`
- Now extracts `work.get('is_retracted')` as `is_retracted`
- Updated CSV/TSV output to include these fields
- Updated field documentation

**DOI URL Importer (`doi_url_importer.py`):**
- Updated table creation to include new columns
- Updated row validation to handle new fields
- Updated all INSERT statements to include new columns
- Removed `doi_metadata` table creation
- Removed `update_doi_metadata()` method

### 3. Removed Components

**Eliminated `doi_metadata` table:**
- No longer created in schema
- No longer populated during import
- Migration script can optionally drop existing table

## Migration Process

### Automatic Migration

The migration script `db/migrations/001_add_work_type_and_is_retracted.sql` will:

1. Add the new columns to existing `doi_urls` tables
2. Create appropriate indexes
3. Migrate any existing data from `doi_metadata` table if present
4. Optionally drop the `doi_metadata` table (commented out by default)

### Manual Migration Steps

If you prefer to run the migration manually:

```sql
-- Add new columns
ALTER TABLE doi_urls 
ADD COLUMN IF NOT EXISTS work_type TEXT,
ADD COLUMN IF NOT EXISTS is_retracted BOOLEAN DEFAULT FALSE;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_doi_urls_work_type ON doi_urls(work_type);
CREATE INDEX IF NOT EXISTS idx_doi_urls_is_retracted ON doi_urls(is_retracted);

-- If you have existing doi_metadata table, migrate data
UPDATE doi_urls 
SET 
    work_type = dm.work_type,
    is_retracted = dm.is_retracted,
    updated_at = CURRENT_TIMESTAMP
FROM doi_metadata dm 
WHERE doi_urls.doi = dm.doi;

-- Optionally drop the old table
-- DROP TABLE IF EXISTS doi_metadata CASCADE;
```

## Benefits

1. **Simplified Schema**: Single table instead of two related tables
2. **Better Performance**: No need for JOINs to access work metadata
3. **Reduced Storage**: Eliminates duplicate data (doi, openalex_id, title, publication_year)
4. **Easier Queries**: All data available in one table
5. **Cleaner Code**: Removes unused metadata table management code

## Example Queries

### Filter by work type
```sql
SELECT doi, url, title, work_type 
FROM doi_urls 
WHERE work_type = 'journal-article' 
AND is_oa = TRUE;
```

### Exclude retracted works
```sql
SELECT doi, url, pdf_url 
FROM doi_urls 
WHERE is_retracted = FALSE 
AND pdf_url IS NOT NULL;
```

### Statistics by work type
```sql
SELECT work_type, 
       COUNT(*) as total_urls,
       COUNT(CASE WHEN is_oa THEN 1 END) as open_access_urls,
       COUNT(CASE WHEN pdf_url IS NOT NULL THEN 1 END) as pdf_urls
FROM doi_urls 
WHERE work_type IS NOT NULL
GROUP BY work_type 
ORDER BY total_urls DESC;
```

## Backward Compatibility

- Existing queries that don't reference the new columns will continue to work
- The migration is additive and doesn't remove existing data
- New CSV exports will include the additional columns
- Old CSV files without these columns can still be imported (fields will be NULL)

## Testing

After migration, verify the changes:

```sql
-- Check new columns exist
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'doi_urls' 
AND column_name IN ('work_type', 'is_retracted');

-- Check indexes were created
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'doi_urls' 
AND indexname LIKE '%work_type%' OR indexname LIKE '%retracted%';

-- Sample data check
SELECT work_type, is_retracted, COUNT(*) 
FROM doi_urls 
GROUP BY work_type, is_retracted 
ORDER BY COUNT(*) DESC 
LIMIT 10;
```
