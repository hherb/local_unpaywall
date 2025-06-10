# Schema Migration 003: Introduction of unpaywall Namespace

## Overview

This migration introduces database namespaces by creating an "unpaywall" schema and moving all tables from the public schema to the unpaywall schema. This change supports integration with larger database systems where multiple applications share the same database.

## Changes Made

### 1. Schema Creation

**New schema created:**
```sql
CREATE SCHEMA IF NOT EXISTS unpaywall;
```

**Tables moved to unpaywall schema:**
- `public.doi_urls` → `unpaywall.doi_urls`
- `public.import_progress` → `unpaywall.import_progress`
- `public.schema_migrations` → `unpaywall.schema_migrations` (migration tracking)

### 2. Index and Constraint Updates

**All indexes renamed with unpaywall prefix:**
- `idx_doi_urls_doi` → `idx_unpaywall_doi_urls_doi`
- `idx_doi_urls_url` → `idx_unpaywall_doi_urls_url`
- `idx_import_progress_file_path` → `idx_unpaywall_import_progress_file_path`
- And all other indexes...

**Constraint renamed:**
- `unique_doi_url` → `unique_unpaywall_doi_url`

### 3. Backward Compatibility

**Compatibility views created in public schema:**
```sql
CREATE OR REPLACE VIEW public.doi_urls AS
SELECT * FROM unpaywall.doi_urls;

CREATE OR REPLACE VIEW public.import_progress AS
SELECT * FROM unpaywall.import_progress;
```

These views ensure existing code continues to work without modification.

### 4. Application Updates

**doi_url_importer.py updated:**
- All table references now use `unpaywall.` prefix
- Schema creation includes unpaywall schema setup
- All SQL queries updated to use qualified table names

## Migration Process

### Automatic Migration

Run the migration script:
```bash
python db/run_migration.py --db-name your_db --db-user user --db-password pass --migration 003
```

The migration will:
1. Create the unpaywall schema
2. Move existing tables from public to unpaywall schema
3. Recreate all indexes and constraints
4. Create compatibility views
5. Set appropriate permissions

### Manual Migration

If you prefer to run the migration manually:

```sql
-- Create schema
CREATE SCHEMA IF NOT EXISTS unpaywall;

-- Move tables (if they exist in public schema)
ALTER TABLE public.doi_urls SET SCHEMA unpaywall;
ALTER TABLE public.import_progress SET SCHEMA unpaywall;

-- Create tables if they don't exist
CREATE TABLE IF NOT EXISTS unpaywall.doi_urls (
    -- ... (full table definition)
);

CREATE TABLE IF NOT EXISTS unpaywall.import_progress (
    -- ... (full table definition)
);

CREATE TABLE IF NOT EXISTS unpaywall.schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi ON unpaywall.doi_urls(doi);
-- ... (all other indexes)

-- Add constraints
ALTER TABLE unpaywall.doi_urls ADD CONSTRAINT unique_unpaywall_doi_url UNIQUE(doi, url);

-- Create compatibility views
CREATE OR REPLACE VIEW public.doi_urls AS SELECT * FROM unpaywall.doi_urls;
CREATE OR REPLACE VIEW public.import_progress AS SELECT * FROM unpaywall.import_progress;

-- Set permissions
GRANT USAGE ON SCHEMA unpaywall TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.doi_urls TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.import_progress TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.schema_migrations TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE unpaywall.doi_urls_id_seq TO PUBLIC;
```

## Benefits

1. **Namespace Organization**: Clear separation of unpaywall-related tables
2. **Multi-Application Support**: Database can host multiple applications without naming conflicts
3. **Backward Compatibility**: Existing code continues to work via views
4. **Future Scalability**: Easy to add other schemas (crossref, pubmed, etc.)
5. **Permission Management**: Fine-grained control over schema access
6. **Self-Contained**: All unpaywall functionality including migration tracking is within the unpaywall schema

## Verification

After migration, verify the changes:

```sql
-- Check schema exists
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'unpaywall';

-- Check tables are in correct schema
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name IN ('doi_urls', 'import_progress', 'schema_migrations')
ORDER BY table_schema, table_name;

-- Check indexes were created
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'unpaywall'
ORDER BY tablename, indexname;

-- Check constraints
SELECT conname, conrelid::regclass 
FROM pg_constraint 
WHERE conname LIKE '%unpaywall%';

-- Check compatibility views exist
SELECT table_schema, table_name, view_definition 
FROM information_schema.views 
WHERE table_name IN ('doi_urls', 'import_progress')
AND table_schema = 'public';

-- Test data access through both methods
SELECT COUNT(*) FROM unpaywall.doi_urls;
SELECT COUNT(*) FROM public.doi_urls;  -- Should return same count
```

## Application Migration

### Immediate (Optional)
Applications can immediately start using the new schema:

```python
# New approach (recommended)
cursor.execute("SELECT * FROM unpaywall.doi_urls WHERE doi = %s", (doi,))
```

### Gradual Migration
Applications can continue using unqualified names:

```python
# Still works via compatibility views
cursor.execute("SELECT * FROM doi_urls WHERE doi = %s", (doi,))
```

### Search Path Alternative
Set search_path to include unpaywall schema:

```sql
SET search_path = unpaywall, public;
```

This allows unqualified table names to find tables in the unpaywall schema first.

## Cleanup (Future)

After all applications are updated to use the new schema:

1. **Drop compatibility views:**
   ```sql
   DROP VIEW IF EXISTS public.doi_urls CASCADE;
   DROP VIEW IF EXISTS public.import_progress CASCADE;
   ```

2. **Update application configurations** to use qualified table names

3. **Remove public schema from search_path** if desired

## Rollback (Emergency)

If rollback is needed:

```sql
-- Move tables back to public schema
ALTER TABLE unpaywall.doi_urls SET SCHEMA public;
ALTER TABLE unpaywall.import_progress SET SCHEMA public;

-- Drop unpaywall schema
DROP SCHEMA unpaywall CASCADE;

-- Recreate indexes with original names
CREATE INDEX idx_doi_urls_doi ON doi_urls(doi);
-- ... (recreate all indexes)

-- Recreate original constraint
ALTER TABLE doi_urls ADD CONSTRAINT unique_doi_url UNIQUE(doi, url);
```

## Testing

Test the migration with a small dataset:

```bash
# Test import with new schema
python doi_url_importer.py --csv-file test_data.csv --db-name test_db

# Verify data is in unpaywall schema
psql -d test_db -c "SELECT COUNT(*) FROM unpaywall.doi_urls;"

# Verify compatibility views work
psql -d test_db -c "SELECT COUNT(*) FROM public.doi_urls;"
```

## Impact Assessment

- **Storage**: No impact on storage requirements
- **Performance**: Minimal impact; qualified names may be slightly faster
- **Compatibility**: Full backward compatibility maintained via views
- **Maintenance**: Improved organization and easier multi-application management

## Next Steps

1. Run migration 003 on development environment
2. Test all applications with new schema
3. Update applications to use qualified table names (optional)
4. Run migration on production environment
5. Monitor for any issues
6. Plan future schema additions (crossref, pubmed, etc.)

This migration provides a solid foundation for organizing the database as the system grows and integrates with additional data sources.
