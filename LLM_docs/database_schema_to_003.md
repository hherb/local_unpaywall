# Database Schema Documentation - Normalized Structure

## Overview

This document describes the normalized database schema for the unpaywall system. The schema is designed for storage efficiency with large datasets (250+ million rows) by using lookup tables for redundant data and optimized data types.

## Schema Organization

### Namespace: `unpaywall`

All tables related to the unpaywall functionality are contained within the `unpaywall` schema:
- `unpaywall.doi_urls` - Main DOI-URL mapping table (normalized)
- `unpaywall.license` - License lookup table
- `unpaywall.oa_status` - Open access status lookup table
- `unpaywall.host_type` - Host type lookup table
- `unpaywall.work_type` - Work type lookup table
- `unpaywall.import_progress` - Import tracking and resume functionality

### Storage Optimization

The normalized structure provides significant storage savings:
- **Per row savings**: 70-160 bytes through foreign key references
- **For 250M rows**: 17-40 GB total storage reduction
- **location_type**: Optimized from TEXT to CHAR(1)
- **Lookup tables**: Eliminate redundant text storage

## Table Definitions

### Lookup Tables

```sql
-- License lookup table
CREATE TABLE unpaywall.license (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Open access status lookup table
CREATE TABLE unpaywall.oa_status (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Host type lookup table
CREATE TABLE unpaywall.host_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Work type lookup table
CREATE TABLE unpaywall.work_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### unpaywall.doi_urls

Main table for storing DOI to URL mappings with normalized foreign key references.

```sql
CREATE TABLE unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,                    -- DOI identifier (normalized, lowercase)
    url TEXT NOT NULL,                    -- Full text URL
    pdf_url TEXT,                         -- Direct PDF URL (if available)
    openalex_id BIGINT,                   -- OpenAlex work ID (numeric part only)
    title TEXT,                           -- Publication title
    publication_year INTEGER,             -- Publication year
    location_type CHAR(1) NOT NULL,       -- 'p'=primary, 'a'=alternate, 'b'=best_oa
    version TEXT,                         -- Version info (published, accepted, etc.)
    license_id INTEGER REFERENCES unpaywall.license(id),     -- License foreign key
    host_type_id INTEGER REFERENCES unpaywall.host_type(id), -- Host type foreign key
    oa_status_id INTEGER REFERENCES unpaywall.oa_status(id), -- OA status foreign key
    is_oa BOOLEAN DEFAULT FALSE,          -- Open access flag
    work_type_id INTEGER REFERENCES unpaywall.work_type(id), -- Work type foreign key
    is_retracted BOOLEAN DEFAULT FALSE,   -- Retraction status
    url_quality_score INTEGER DEFAULT 50, -- Quality score (0-100)
    last_verified TIMESTAMP,             -- Last verification timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_unpaywall_doi_url UNIQUE(doi, url),
    CONSTRAINT chk_location_type CHECK (location_type IN ('p', 'a', 'b'))
);
```

#### Indexes

```sql
-- Primary access patterns
CREATE INDEX idx_unpaywall_doi_urls_doi ON unpaywall.doi_urls(doi);
CREATE INDEX idx_unpaywall_doi_urls_url ON unpaywall.doi_urls(url);

-- PDF access optimization
CREATE INDEX idx_unpaywall_doi_urls_pdf_url ON unpaywall.doi_urls(pdf_url)
    WHERE pdf_url IS NOT NULL;

-- Combined lookups
CREATE INDEX idx_unpaywall_doi_urls_doi_location_type ON unpaywall.doi_urls(doi, location_type);

-- Foreign key indexes for efficient joins
CREATE INDEX idx_unpaywall_doi_urls_license_id ON unpaywall.doi_urls(license_id);
CREATE INDEX idx_unpaywall_doi_urls_oa_status_id ON unpaywall.doi_urls(oa_status_id);
CREATE INDEX idx_unpaywall_doi_urls_host_type_id ON unpaywall.doi_urls(host_type_id);
CREATE INDEX idx_unpaywall_doi_urls_work_type_id ON unpaywall.doi_urls(work_type_id);

-- Other filtering indexes
CREATE INDEX idx_unpaywall_doi_urls_location_type ON unpaywall.doi_urls(location_type);
CREATE INDEX idx_unpaywall_doi_urls_publication_year ON unpaywall.doi_urls(publication_year);
CREATE INDEX idx_unpaywall_doi_urls_is_retracted ON unpaywall.doi_urls(is_retracted);
CREATE INDEX idx_unpaywall_doi_urls_openalex_work_id ON unpaywall.doi_urls(openalex_id);
```

#### Constraints

```sql
-- Prevent duplicate DOI-URL pairs
CONSTRAINT unique_unpaywall_doi_url UNIQUE(doi, url)

-- Ensure valid location type values
CONSTRAINT chk_location_type CHECK (location_type IN ('p', 'a', 'b'))

-- Foreign key constraints
CONSTRAINT fk_doi_urls_license_id FOREIGN KEY (license_id) REFERENCES unpaywall.license(id)
CONSTRAINT fk_doi_urls_oa_status_id FOREIGN KEY (oa_status_id) REFERENCES unpaywall.oa_status(id)
CONSTRAINT fk_doi_urls_host_type_id FOREIGN KEY (host_type_id) REFERENCES unpaywall.host_type(id)
CONSTRAINT fk_doi_urls_work_type_id FOREIGN KEY (work_type_id) REFERENCES unpaywall.work_type(id)
```

### unpaywall.import_progress

Tracks import progress for resume functionality and monitoring.

```sql
CREATE TABLE unpaywall.import_progress (
    import_id TEXT PRIMARY KEY,           -- Unique import identifier
    csv_file_path TEXT NOT NULL,          -- Path to source CSV file
    csv_file_hash TEXT NOT NULL,          -- SHA-256 hash for change detection
    total_rows INTEGER NOT NULL,          -- Total rows in CSV file
    processed_rows INTEGER DEFAULT 0,     -- Rows processed so far
    last_batch_id INTEGER DEFAULT 0,      -- Last completed batch ID
    status TEXT DEFAULT 'in_progress',    -- Status: in_progress, completed, failed, cancelled
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,                   -- Completion timestamp
    error_message TEXT,                   -- Error details if failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Indexes

```sql
CREATE INDEX idx_unpaywall_import_progress_file_path ON unpaywall.import_progress(csv_file_path);
CREATE INDEX idx_unpaywall_import_progress_status ON unpaywall.import_progress(status);
```

### unpaywall.schema_migrations

Tracks applied database migrations for the unpaywall functionality.

```sql
CREATE TABLE unpaywall.schema_migrations (
    migration_id TEXT PRIMARY KEY,        -- Migration identifier (e.g., "003_create_unpaywall_schema")
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When migration was applied
    description TEXT                      -- Human-readable description
);
```

This table is self-contained within the unpaywall schema and tracks only unpaywall-related migrations.

## Migration History

### Migration 001
- Added `work_type` and `is_retracted` columns to main table
- Integrated metadata from separate `doi_metadata` table

### Migration 002  
- Optimized OpenAlex ID storage from TEXT to BIGINT
- Added helper functions for ID conversion
- Significant storage savings (~27 bytes per record)

### Migration 003 (Current)
- Introduced `unpaywall` schema namespace
- Moved all tables from `public` to `unpaywall` schema
- Created compatibility views for backward compatibility
- Updated all indexes and constraints with new naming

## Usage Examples

### Basic Queries (Normalized Structure)

```sql
-- Find URLs for a specific DOI
SELECT url, pdf_url, url_quality_score
FROM unpaywall.doi_urls
WHERE doi = '10.1038/nature12373'
ORDER BY url_quality_score DESC;

-- Find open access articles by license type
SELECT d.doi, d.url, l.value as license
FROM unpaywall.doi_urls d
JOIN unpaywall.license l ON d.license_id = l.id
WHERE d.is_oa = TRUE AND l.value = 'cc-by';

-- Get publication statistics by work type
SELECT w.value as work_type, COUNT(*) as article_count
FROM unpaywall.doi_urls d
JOIN unpaywall.work_type w ON d.work_type_id = w.id
WHERE d.publication_year IS NOT NULL
GROUP BY w.value
ORDER BY article_count DESC;

-- Find articles by host type and location type
SELECT d.doi, d.url, h.value as host_type
FROM unpaywall.doi_urls d
JOIN unpaywall.host_type h ON d.host_type_id = h.id
WHERE h.value = 'journal' AND d.location_type = 'p';  -- primary locations in journals
```

### Quality-Based Queries

```sql
-- Find best quality URLs for DOIs
SELECT DISTINCT ON (doi) doi, url, pdf_url, url_quality_score
FROM unpaywall.doi_urls 
WHERE doi IN ('10.1038/nature12373', '10.1126/science.1234567')
ORDER BY doi, url_quality_score DESC;

-- Find articles with direct PDF access
SELECT doi, url, pdf_url 
FROM unpaywall.doi_urls 
WHERE pdf_url IS NOT NULL 
AND url_quality_score > 70;
```

### Import Monitoring

```sql
-- Check recent import status
SELECT import_id, status, processed_rows, total_rows,
       ROUND(processed_rows::NUMERIC / total_rows * 100, 1) as progress_pct
FROM unpaywall.import_progress 
ORDER BY start_time DESC 
LIMIT 5;

-- Find failed imports
SELECT import_id, csv_file_path, error_message, start_time
FROM unpaywall.import_progress 
WHERE status = 'failed'
ORDER BY start_time DESC;
```

## Permissions

The schema includes appropriate permissions for public access:

```sql
-- Schema access
GRANT USAGE ON SCHEMA unpaywall TO PUBLIC;

-- Table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.doi_urls TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.import_progress TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.schema_migrations TO PUBLIC;

-- Sequence permissions
GRANT USAGE, SELECT ON SEQUENCE unpaywall.doi_urls_id_seq TO PUBLIC;
```

## Future Considerations

1. **View Deprecation**: After confirming all applications use the new schema, the compatibility views can be dropped
2. **Additional Schemas**: Other related functionality can be organized into separate schemas (e.g., `crossref`, `pubmed`)
3. **Partitioning**: Large tables may benefit from partitioning by publication year or DOI prefix
4. **Archival**: Old import progress records can be archived or purged periodically

## Working with the Normalized Structure

### Using the Helper Module

```python
from db.normalized_helpers import NormalizedHelper

# Initialize helper
helper = NormalizedHelper(db_config)

# Insert a record with text values (automatically converted to foreign keys)
helper.insert_doi_url_record({
    'doi': '10.1234/example',
    'url': 'https://example.com/paper',
    'license': 'cc-by',
    'oa_status': 'gold',
    'host_type': 'journal',
    'work_type': 'journal-article',
    'location_type': 'primary'  # automatically converted to 'p'
})

# Get lookup IDs
license_id = helper.get_or_create_lookup_id('license', 'cc-by')
location_char = helper.normalize_location_type('primary')  # returns 'p'
```

### Direct Database Operations

```python
# When inserting data, convert text values to IDs first
with conn.cursor() as cur:
    # Get or create license ID
    cur.execute("INSERT INTO unpaywall.license (value) VALUES (%s) ON CONFLICT (value) DO NOTHING", ('cc-by',))
    cur.execute("SELECT id FROM unpaywall.license WHERE value = %s", ('cc-by',))
    license_id = cur.fetchone()[0]

    # Insert main record with foreign key
    cur.execute("""
        INSERT INTO unpaywall.doi_urls (doi, url, license_id, location_type)
        VALUES (%s, %s, %s, %s)
    """, (doi, url, license_id, 'p'))
```

### Location Type Mapping

- `'primary'` → `'p'`
- `'alternate'` → `'a'`
- `'best_oa'` → `'b'`
