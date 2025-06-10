# Schema Migration 004: Database Normalization for Storage Efficiency

## Overview

Migration 004 normalizes the `unpaywall.doi_urls` table to significantly reduce storage space by creating lookup tables for redundant TEXT data and optimizing the `location_type` column. This migration is particularly important for large datasets (250+ million rows) where storage efficiency is critical.

## Storage Impact

### Before Normalization
- `license`: ~20-50 bytes per row (TEXT)
- `oa_status`: ~10-20 bytes per row (TEXT)  
- `host_type`: ~15-30 bytes per row (TEXT)
- `work_type`: ~15-40 bytes per row (TEXT)
- `location_type`: ~8-15 bytes per row (TEXT)

### After Normalization
- `license_id`: 4 bytes per row (INTEGER foreign key)
- `oa_status_id`: 4 bytes per row (INTEGER foreign key)
- `host_type_id`: 4 bytes per row (INTEGER foreign key)
- `work_type_id`: 4 bytes per row (INTEGER foreign key)
- `location_type`: 1 byte per row (CHAR(1))

### Total Savings
- **Per row**: 70-160 bytes saved
- **For 250M rows**: 17-40 GB storage reduction
- **Additional benefits**: Improved query performance, better data consistency

## Migration Process

### Phase 1: Preparation (Migration 004)
1. Create lookup tables for `license`, `oa_status`, `host_type`, `work_type`
2. Populate lookup tables with existing unique values
3. Add foreign key columns to main table
4. Update foreign key data
5. Create normalized `location_type` column
6. Create indexes for new columns

### Phase 2: Finalization (Migration 004b)
1. Drop old TEXT columns
2. Finalize `location_type` conversion
3. Create backward compatibility view
4. Update permissions and constraints

## New Database Structure

### Lookup Tables

```sql
-- License lookup table
CREATE TABLE unpaywall.license (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Open access status lookup table  
CREATE TABLE unpaywall.oa_status (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Host type lookup table
CREATE TABLE unpaywall.host_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Work type lookup table
CREATE TABLE unpaywall.work_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Updated Main Table

```sql
CREATE TABLE unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,
    title TEXT,
    publication_year INTEGER,
    location_type CHAR(1) NOT NULL,  -- 'p'=primary, 'a'=alternate, 'b'=best_oa
    version TEXT,
    license_id INTEGER REFERENCES unpaywall.license(id),
    host_type_id INTEGER REFERENCES unpaywall.host_type(id),
    oa_status_id INTEGER REFERENCES unpaywall.oa_status(id),
    is_oa BOOLEAN DEFAULT FALSE,
    work_type_id INTEGER REFERENCES unpaywall.work_type(id),
    is_retracted BOOLEAN DEFAULT FALSE,
    url_quality_score INTEGER DEFAULT 50,
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Location Type Mapping

The `location_type` column is converted from TEXT to CHAR(1) with the following mapping:

- `'primary'` → `'p'`
- `'alternate'` → `'a'`
- `'best_oa'` → `'b'`

## Backward Compatibility

### Denormalized View
A view `unpaywall.doi_urls_denormalized` is created to maintain backward compatibility:

```sql
CREATE VIEW unpaywall.doi_urls_denormalized AS
SELECT 
    d.id, d.doi, d.url, d.pdf_url, d.openalex_id, d.title, d.publication_year,
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
    d.updated_at
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
LEFT JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
LEFT JOIN unpaywall.host_type h ON d.host_type_id = h.id
LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id;
```

### Public Schema Compatibility
The `public.doi_urls` view is updated to point to the denormalized view, ensuring existing applications continue to work.

## Running the Migration

### Using the Database Creator Module

```python
from db.create_db import DatabaseCreator

# Create instance with database credentials
creator = DatabaseCreator.from_env_or_args()

# Run normalization
success = creator.normalize_database(verify=True)
if success:
    print("Database normalization completed successfully")
else:
    print("Normalization failed")
```

### Using Command Line

```bash
# Normalize the database
python db/create_db.py --normalize

# Check schema information after normalization
python db/create_db.py --info
```

### Manual Migration

```bash
# Run the migration script
psql -d your_database -f db/migrations/004_normalize_database_storage.sql

# Verify the migration worked correctly
# (check lookup tables, foreign keys, data integrity)

# Finalize the migration
psql -d your_database -f db/migrations/004b_finalize_normalization.sql
```

## Query Examples

### Using Normalized Tables (Efficient)

```sql
-- Find open access articles by license type
SELECT d.doi, d.url, l.value as license
FROM unpaywall.doi_urls d
JOIN unpaywall.license l ON d.license_id = l.id
WHERE l.value = 'cc-by'
AND d.is_oa = TRUE;

-- Statistics by host type
SELECT h.value as host_type, COUNT(*) as count
FROM unpaywall.doi_urls d
JOIN unpaywall.host_type h ON d.host_type_id = h.id
GROUP BY h.value
ORDER BY count DESC;

-- Filter by location type (using CHAR values)
SELECT doi, url FROM unpaywall.doi_urls 
WHERE location_type = 'p';  -- primary locations
```

### Using Backward Compatibility View

```sql
-- This works exactly like before normalization
SELECT doi, url, license, oa_status, host_type, work_type, location_type
FROM unpaywall.doi_urls_denormalized
WHERE oa_status = 'gold'
AND location_type = 'primary';
```

## Performance Considerations

### Advantages
- **Storage**: 70-160 bytes saved per row
- **Cache efficiency**: More rows fit in memory
- **Index performance**: Smaller indexes, faster lookups
- **Data consistency**: Centralized value management

### Query Patterns
- Use normalized tables for new queries (better performance)
- Use denormalized view for backward compatibility
- JOIN with lookup tables when you need the actual text values
- Use foreign key IDs for filtering and grouping when possible

## Maintenance

### Adding New Values
```sql
-- Add new license type
INSERT INTO unpaywall.license (value, description) 
VALUES ('cc-by-sa', 'Creative Commons Attribution-ShareAlike');

-- Use in main table
UPDATE unpaywall.doi_urls 
SET license_id = (SELECT id FROM unpaywall.license WHERE value = 'cc-by-sa')
WHERE some_condition;
```

### Monitoring Storage
```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'unpaywall'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Rollback Considerations

**Warning**: After running migration 004b (finalization), rollback is not possible without a full database backup, as the original TEXT columns are permanently deleted.

Before finalization:
- Verify all data has been correctly migrated
- Test critical queries with the new structure
- Ensure applications work with the denormalized view
- Consider keeping a backup of the pre-migration state

## Integration with Applications

### DOI URL Importer Updates
The importer needs to be updated to work with the normalized structure:

```python
# When inserting new data, resolve text values to IDs
license_id = get_or_create_lookup_id('license', license_value)
oa_status_id = get_or_create_lookup_id('oa_status', oa_status_value)
# etc.

# Convert location_type to CHAR(1)
location_type_char = {'primary': 'p', 'alternate': 'a', 'best_oa': 'b'}.get(location_type, 'p')
```

### Query Updates
Applications should be updated to use the normalized structure for better performance, but can continue using the denormalized view during transition.
