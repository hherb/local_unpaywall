# Schema Migration 002: OpenAlex ID Storage Optimization

## Overview

This migration optimizes the storage of OpenAlex IDs by converting from storing the full URL (`TEXT`) to storing only the numeric part (`BIGINT`). This provides significant storage savings and improved query performance.

## Problem

OpenAlex IDs are currently stored as full URLs like:
- `https://openalex.org/W1982051859`
- `https://openalex.org/W2741809807`

This format:
- Uses ~35 bytes per ID (plus overhead)
- Contains redundant prefix information
- Is slower for indexing and comparisons

## Solution

Store only the numeric part as a `BIGINT`:
- `1982051859`
- `2741809807`

This format:
- Uses only 8 bytes per ID
- **Saves ~27 bytes per record (77% reduction)**
- Faster for indexing and joins
- Can be easily reconstructed to full URL when needed

## Storage Savings Analysis

For a database with 10 million records:
- **Old format**: 10M × 35 bytes = ~350 MB
- **New format**: 10M × 8 bytes = ~80 MB
- **Savings**: ~270 MB (77% reduction)

## Migration Strategy

The migration uses a **dual-column approach** for safety:

1. **Add new column** `openalex_work_id BIGINT`
2. **Populate new column** with extracted numeric IDs
3. **Keep old column** for backward compatibility
4. **Create helper functions** for URL reconstruction
5. **Create compatibility view** for existing queries

## Changes Made

### 1. Database Schema

**New column added:**
```sql
ALTER TABLE doi_urls ADD COLUMN openalex_work_id BIGINT;
```

**Helper functions created:**
```sql
-- Extract numeric ID from URL
extract_openalex_work_id(openalex_url TEXT) RETURNS BIGINT

-- Reconstruct full URL from numeric ID  
openalex_work_url(work_id BIGINT) RETURNS TEXT
```

**Compatibility view:**
```sql
CREATE VIEW doi_urls_with_full_openalex_id AS
SELECT *, openalex_work_url(openalex_work_id) as openalex_id
FROM doi_urls;
```

### 2. Data Extraction Updates

**OpenAlex Extractor:**
- Now extracts numeric part from OpenAlex URLs
- Outputs numeric ID in CSV instead of full URL
- Handles various input formats (full URL, W-prefixed, numeric)

**Database Importer:**
- Converts string input to BIGINT
- Handles backward compatibility with old CSV formats
- Robust error handling for malformed IDs

### 3. New Schema Definition

```sql
CREATE TABLE doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,                   -- Now BIGINT instead of TEXT
    title TEXT,
    publication_year INTEGER,
    -- ... other fields
);
```

## Migration Process

### Automatic Migration

Run the migration script:
```bash
python db/run_migration.py --db-name your_db --db-user user --db-password pass --migration 002
```

The migration will:
1. Add the new `openalex_work_id` column
2. Extract numeric IDs from existing data
3. Create helper functions and views
4. Report conversion statistics

### Manual Migration

```sql
-- Add new column
ALTER TABLE doi_urls ADD COLUMN openalex_work_id BIGINT;

-- Populate with extracted IDs
UPDATE doi_urls 
SET openalex_work_id = extract_openalex_work_id(openalex_id)
WHERE openalex_id IS NOT NULL;

-- Create index
CREATE INDEX idx_doi_urls_openalex_work_id ON doi_urls(openalex_work_id);
```

## Backward Compatibility

### For Existing Queries

The migration maintains full backward compatibility:

```sql
-- Old queries continue to work via the compatibility view
SELECT * FROM doi_urls_with_full_openalex_id 
WHERE openalex_id = 'https://openalex.org/W1982051859';
```

### For Applications

Applications can gradually migrate to use the new format:

```sql
-- New efficient queries using numeric ID
SELECT * FROM doi_urls WHERE openalex_work_id = 1982051859;

-- Reconstruct URL when needed
SELECT openalex_work_url(openalex_work_id) as full_url FROM doi_urls;
```

## Performance Benefits

### Storage Efficiency
- **77% reduction** in OpenAlex ID storage space
- Smaller indexes and faster scans
- Reduced memory usage for queries

### Query Performance
- **Faster equality comparisons** (integer vs string)
- **More efficient joins** on OpenAlex ID
- **Better index performance** (B-tree on integers)

### Example Performance Comparison

```sql
-- Old format (slower)
WHERE openalex_id = 'https://openalex.org/W1982051859'

-- New format (faster)  
WHERE openalex_work_id = 1982051859
```

## Data Validation

The migration includes validation to ensure data integrity:

```sql
-- Check conversion success rate
SELECT 
    COUNT(*) as total_records,
    COUNT(openalex_id) as records_with_old_id,
    COUNT(openalex_work_id) as records_with_new_id,
    COUNT(openalex_work_id) * 100.0 / COUNT(openalex_id) as conversion_rate
FROM doi_urls;
```

## Future Cleanup

After verifying the migration works correctly:

1. **Update application code** to use `openalex_work_id`
2. **Drop compatibility view** when no longer needed
3. **Drop old column** to complete the migration:
   ```sql
   ALTER TABLE doi_urls DROP COLUMN openalex_id;
   ALTER TABLE doi_urls RENAME COLUMN openalex_work_id TO openalex_id;
   ```

## Example Usage

### Extracting Data
```bash
# New CSV output contains numeric IDs
python openalex_unpaywall_extractor.py --snapshot-dir data --output urls.csv
```

### Querying Data
```sql
-- Find works by numeric OpenAlex ID
SELECT * FROM doi_urls WHERE openalex_id = 1982051859;

-- Reconstruct full URL when needed for external APIs
SELECT doi, openalex_work_url(openalex_id) as openalex_url 
FROM doi_urls 
WHERE doi = '10.1038/nature12373';
```

### Statistics
```sql
-- Storage efficiency analysis
SELECT 
    'Old format' as format,
    COUNT(*) * 35 as estimated_bytes,
    pg_size_pretty(COUNT(*) * 35) as estimated_size
FROM doi_urls WHERE openalex_id IS NOT NULL
UNION ALL
SELECT 
    'New format' as format,
    COUNT(*) * 8 as estimated_bytes,
    pg_size_pretty(COUNT(*) * 8) as estimated_size  
FROM doi_urls WHERE openalex_id IS NOT NULL;
```

## Testing

Verify the migration with:
```bash
python test_openalex_id_optimization.py
```

This tests:
- Numeric ID extraction from various formats
- CSV output with numeric IDs
- Database import with conversion
- Query performance improvements
