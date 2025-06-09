# Normalized Database Structure

This document describes the storage-optimized, normalized database structure for the unpaywall system.

## Overview

The normalized database structure is designed for maximum storage efficiency with large datasets (250+ million rows). It uses lookup tables for redundant data and optimized data types to significantly reduce storage requirements.

## Storage Savings

- **Per row**: 70-160 bytes saved through normalization
- **For 250M rows**: 17-40 GB total storage reduction
- **Key optimizations**:
  - TEXT columns → INTEGER foreign keys (4 bytes each)
  - `location_type` TEXT → CHAR(1) (1 byte)
  - Eliminates redundant text storage

## Database Structure

### Main Table: `unpaywall.doi_urls`

```sql
CREATE TABLE unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,
    title TEXT,
    publication_year INTEGER,
    location_type CHAR(1) NOT NULL,       -- 'p', 'a', 'b'
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_unpaywall_doi_url UNIQUE(doi, url),
    CONSTRAINT chk_location_type CHECK (location_type IN ('p', 'a', 'b'))
);
```

### Lookup Tables

- `unpaywall.license` - License types (cc-by, cc0, etc.)
- `unpaywall.oa_status` - Open access status (gold, green, closed, etc.)
- `unpaywall.host_type` - Host types (journal, repository, preprint_server, etc.)
- `unpaywall.work_type` - Work types (journal-article, book-chapter, preprint, etc.)

### Location Type Mapping

- `'p'` = primary
- `'a'` = alternate  
- `'b'` = best_oa

## Getting Started

### 1. Create the Database Schema

```bash
# Create normalized schema from scratch
python db/create_db.py

# Or with explicit credentials
python db/create_db.py --db-host localhost --db-name unpaywall --db-user myuser --db-password mypass
```

### 2. Test the Setup

```bash
# Run the test script to verify everything works
python test_normalized_db.py
```

### 3. Use the Helper Module

```python
from db.normalized_helpers import NormalizedHelper

# Initialize helper
helper = NormalizedHelper(db_config)

# Insert data (text values automatically converted to foreign keys)
helper.insert_doi_url_record({
    'doi': '10.1234/example',
    'url': 'https://example.com/paper',
    'license': 'cc-by',
    'oa_status': 'gold',
    'host_type': 'journal',
    'work_type': 'journal-article',
    'location_type': 'primary'
})
```

## Querying the Normalized Database

### Simple Queries (No Joins Needed)

```sql
-- Find URLs for a DOI
SELECT doi, url, pdf_url FROM unpaywall.doi_urls 
WHERE doi = '10.1234/example';

-- Filter by location type
SELECT doi, url FROM unpaywall.doi_urls 
WHERE location_type = 'p';  -- primary locations
```

### Queries with Lookup Tables

```sql
-- Find open access articles by license
SELECT d.doi, d.url, l.value as license
FROM unpaywall.doi_urls d
JOIN unpaywall.license l ON d.license_id = l.id
WHERE d.is_oa = TRUE AND l.value = 'cc-by';

-- Statistics by work type
SELECT w.value as work_type, COUNT(*) as count
FROM unpaywall.doi_urls d
JOIN unpaywall.work_type w ON d.work_type_id = w.id
GROUP BY w.value
ORDER BY count DESC;
```

## Performance Benefits

1. **Storage Efficiency**: 70-160 bytes saved per row
2. **Cache Performance**: More rows fit in memory
3. **Index Efficiency**: Smaller indexes, faster lookups
4. **Query Performance**: Integer comparisons faster than text
5. **Data Consistency**: Centralized value management

## Migration from Old Structure

If you have an existing database with the old TEXT-based structure, see the migration scripts in `db/migrations/` for conversion procedures.

## Helper Functions

The `db.normalized_helpers` module provides utilities for:

- Converting text values to foreign key IDs
- Normalizing location types
- Inserting records with automatic conversion
- Caching lookup values for performance

## Maintenance

### Adding New Lookup Values

```sql
-- Add new license type
INSERT INTO unpaywall.license (value) VALUES ('cc-by-nc');

-- Use in main table
UPDATE unpaywall.doi_urls 
SET license_id = (SELECT id FROM unpaywall.license WHERE value = 'cc-by-nc')
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

## Documentation

- **Database Schema**: `LLM_docs/database_schema_to_003.md`
- **Migration Guide**: `manual/schema_migration_004.md`
- **API Reference**: See docstrings in `db/normalized_helpers.py`

## Support

For questions or issues with the normalized database structure:

1. Check the test script: `python test_normalized_db.py`
2. Review the documentation in `LLM_docs/`
3. Examine the helper module: `db/normalized_helpers.py`
