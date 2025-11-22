# Importing Data into PostgreSQL

This guide covers importing extracted DOI-URL data into your PostgreSQL database.

## Overview

The import process:
1. Reads the CSV file in memory-efficient batches
2. Normalizes data into lookup tables
3. Inserts records with duplicate handling
4. Tracks progress for resume capability

## Basic Import

### Using .env Configuration

If you have a `.env` file configured:

```bash
python doi_url_importer.py --csv-file doi_urls.csv --resume
```

### Using Command-Line Arguments

```bash
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --db-host localhost \
    --db-name unpaywall \
    --db-user unpaywall_user \
    --db-password your_password \
    --resume
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--csv-file` | Path to CSV file | Required |
| `--db-host` | Database hostname | .env or localhost |
| `--db-port` | Database port | 5432 |
| `--db-name` | Database name | .env value |
| `--db-user` | Database username | .env value |
| `--db-password` | Database password | .env value |
| `--batch-size` | Rows per batch | 10000 |
| `--create-tables` | Create tables if missing | True |
| `--resume` | Resume interrupted import | False |

## Import Strategies

### Standard Import

For most cases, use the default settings:
```bash
python doi_url_importer.py --csv-file doi_urls.csv --resume
```

### High-Performance Import

For large datasets (millions of rows):

```bash
# Use larger batch size
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --batch-size 50000 \
    --resume
```

### Memory-Constrained Import

For systems with limited RAM:

```bash
# Use smaller batch size
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --batch-size 5000 \
    --resume
```

## Pre-Import Optimization

For very large imports (50M+ rows), optimize PostgreSQL first:

### Disable Autovacuum Temporarily

```sql
-- Connect to your database
psql -U unpaywall_user -d unpaywall

-- Disable autovacuum for the import
ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = false);
```

### Increase Memory Settings

```sql
-- Temporarily increase work memory
SET work_mem = '256MB';
SET maintenance_work_mem = '1GB';
```

## Monitoring Import Progress

### Progress Display

The importer shows real-time progress:
```
Importing CSV data: 78%|███████▊  | 780K/1M [05:23<01:15, 2.41Krows/s]
```

### Log File

Monitor the log file:
```bash
tail -f doi_url_import.log
```

Example log output:
```
2024-11-22 11:00:15 - INFO - Starting import from doi_urls.csv
2024-11-22 11:00:15 - INFO - CSV file has 1,234,567 rows
2024-11-22 11:00:16 - INFO - Preloading lookup table caches...
2024-11-22 11:00:17 - INFO - Loaded 45 license values
2024-11-22 11:00:17 - INFO - Loaded 5 oa_status values
2024-11-22 11:00:17 - INFO - Processing batch 1 (rows 1-10000)
```

### Check Row Count

```sql
-- Check how many rows have been imported
SELECT COUNT(*) FROM unpaywall.doi_urls;

-- Check import rate (run multiple times)
SELECT COUNT(*) as rows, NOW() as time FROM unpaywall.doi_urls;
```

## Resume Interrupted Imports

If the import is interrupted, simply re-run with `--resume`:

```bash
python doi_url_importer.py --csv-file doi_urls.csv --resume
```

The importer will:
1. Check the import progress table
2. Verify file integrity (hash check)
3. Skip already-imported rows
4. Continue from the last checkpoint

### Check Resume Status

```sql
SELECT * FROM unpaywall.import_progress
ORDER BY updated_at DESC
LIMIT 5;
```

### Force Fresh Import

To start over from scratch:

```sql
-- Clear existing data
TRUNCATE unpaywall.doi_urls CASCADE;
TRUNCATE unpaywall.import_progress;
```

Then run without `--resume`:
```bash
python doi_url_importer.py --csv-file doi_urls.csv
```

## Post-Import Tasks

### Re-enable Autovacuum

```sql
ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = true);
```

### Analyze Tables

Update PostgreSQL statistics for optimal query planning:

```sql
ANALYZE unpaywall.doi_urls;
ANALYZE unpaywall.license;
ANALYZE unpaywall.oa_status;
ANALYZE unpaywall.host_type;
ANALYZE unpaywall.work_type;
```

### Verify Import

```sql
-- Total rows imported
SELECT COUNT(*) as total_rows FROM unpaywall.doi_urls;

-- Rows by open access status
SELECT o.value as oa_status, COUNT(*) as count
FROM unpaywall.doi_urls d
JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
GROUP BY o.value
ORDER BY count DESC;

-- Rows by year
SELECT publication_year, COUNT(*) as count
FROM unpaywall.doi_urls
WHERE publication_year IS NOT NULL
GROUP BY publication_year
ORDER BY publication_year DESC
LIMIT 10;
```

### Check Database Size

```sql
-- Table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size('unpaywall.' || tablename)) as size
FROM pg_tables
WHERE schemaname = 'unpaywall'
ORDER BY pg_total_relation_size('unpaywall.' || tablename) DESC;

-- Total database size
SELECT pg_size_pretty(pg_database_size('unpaywall'));
```

## Understanding the Import Process

### Data Normalization

The importer converts text values to foreign key IDs:

| CSV Column | Database Column | Lookup Table |
|------------|-----------------|--------------|
| license | license_id | unpaywall.license |
| oa_status | oa_status_id | unpaywall.oa_status |
| host_type | host_type_id | unpaywall.host_type |
| work_type | work_type_id | unpaywall.work_type |
| location_type | location_type | (CHAR(1): p/a/b) |

### Duplicate Handling

When a duplicate DOI+URL combination is encountered:
- The existing row is updated with new values
- `updated_at` timestamp is refreshed
- Existing PDF URLs are preserved if new one is empty

### Lookup Table Caching

The importer caches lookup table values to minimize database queries:
- Caches are preloaded before import starts
- New values are added on-the-fly
- Cache reduces queries by 99%+

## Troubleshooting Import

### "Connection refused" Error

```
Error: psycopg2.OperationalError: connection refused
```

**Solution**: Check PostgreSQL is running:
```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### "Permission denied" Error

```
Error: permission denied for schema unpaywall
```

**Solution**: Grant privileges:
```sql
GRANT ALL ON SCHEMA unpaywall TO unpaywall_user;
GRANT ALL ON ALL TABLES IN SCHEMA unpaywall TO unpaywall_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA unpaywall TO unpaywall_user;
```

### Slow Import Performance

**Possible causes and solutions**:

1. **Small batch size**: Increase `--batch-size`
2. **Autovacuum running**: Temporarily disable it
3. **Insufficient memory**: Increase PostgreSQL `work_mem`
4. **Slow disk**: Use SSD if possible

### Out of Disk Space

```
Error: could not extend file: No space left on device
```

**Solution**:
```bash
# Check disk usage
df -h

# Clean up old logs
rm -f *.log.old

# Consider moving PostgreSQL data directory
```

## Performance Benchmarks

Typical import speeds on modern hardware:

| Hardware | Batch Size | Speed |
|----------|------------|-------|
| SSD, 8GB RAM | 10,000 | ~2,000 rows/sec |
| SSD, 16GB RAM | 25,000 | ~4,000 rows/sec |
| NVMe, 32GB RAM | 50,000 | ~8,000 rows/sec |

### Estimated Import Times

| Rows | Speed | Time |
|------|-------|------|
| 1 million | 3,000/sec | ~6 minutes |
| 10 million | 3,000/sec | ~1 hour |
| 100 million | 3,000/sec | ~10 hours |
| 250 million | 3,000/sec | ~24 hours |

## Next Steps

With data imported, proceed to:
- [Downloading PDFs](06-downloading-pdfs.md) - Fetch full-text articles
- [Querying Data](07-querying-data.md) - Find and use your data
