# Maintenance Guide

This guide covers routine maintenance tasks to keep your Local Unpaywall installation running smoothly.

## Regular Maintenance Tasks

### Daily Tasks

#### Check Log Files

```bash
# Check for errors in recent logs
grep -i error openalex_url_extraction.log | tail -20
grep -i error doi_url_import.log | tail -20

# Check log file sizes
ls -lh *.log
```

#### Monitor Disk Space

```bash
# Overall disk usage
df -h

# Database size
psql -U unpaywall_user -d unpaywall -c "
SELECT pg_size_pretty(pg_database_size('unpaywall'));
"
```

### Weekly Tasks

#### Database Statistics Update

```bash
psql -U unpaywall_user -d unpaywall -c "
ANALYZE unpaywall.doi_urls;
ANALYZE unpaywall.license;
ANALYZE unpaywall.oa_status;
ANALYZE unpaywall.host_type;
ANALYZE unpaywall.work_type;
"
```

#### Check Table Bloat

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_dead_tup as dead_rows,
    n_live_tup as live_rows,
    CASE WHEN n_live_tup > 0
        THEN round(100.0 * n_dead_tup / n_live_tup, 1)
        ELSE 0
    END as dead_percentage
FROM pg_stat_user_tables
WHERE schemaname = 'unpaywall'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

#### Rotate Log Files

```bash
# Compress old logs
gzip -9 *.log.1 2>/dev/null

# Or use logrotate (create /etc/logrotate.d/local_unpaywall)
```

### Monthly Tasks

#### Vacuum Database

```bash
psql -U unpaywall_user -d unpaywall -c "
VACUUM ANALYZE unpaywall.doi_urls;
"
```

#### Check Index Health

```sql
SELECT
    indexrelname as index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    idx_scan as number_of_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'unpaywall'
ORDER BY pg_relation_size(indexrelid) DESC;
```

#### Backup Database

```bash
# Full backup
pg_dump -U unpaywall_user -d unpaywall -F c -f backup_$(date +%Y%m%d).dump

# Compressed backup
pg_dump -U unpaywall_user -d unpaywall | gzip > backup_$(date +%Y%m%d).sql.gz
```

## Updating Data

### Incremental Updates

When new OpenAlex data is available:

```bash
# 1. Download new data
aws s3 sync "s3://openalex/data/works/updated_date=2024-11-01" \
    "./openalex-snapshot/data/works/updated_date=2024-11-01" \
    --no-sign-request

# 2. Extract new URLs (resume will skip already-processed files)
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --oa-only \
    --resume

# 3. Import new data (upsert handles duplicates)
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --resume
```

### Full Refresh

For a complete data refresh:

```bash
# 1. Backup existing data
pg_dump -U unpaywall_user -d unpaywall -t 'unpaywall.*' -F c -f backup_before_refresh.dump

# 2. Truncate tables
psql -U unpaywall_user -d unpaywall -c "
TRUNCATE unpaywall.doi_urls CASCADE;
TRUNCATE unpaywall.import_progress;
"

# 3. Remove tracking databases
rm -f *.tracking.db

# 4. Re-download fresh snapshot
aws s3 sync "s3://openalex/data/works" "./openalex-snapshot/data/works" \
    --no-sign-request --delete

# 5. Extract and import
python openalex_unpaywall_extractor.py --snapshot-dir ./openalex-snapshot --output doi_urls.csv --oa-only
python doi_url_importer.py --csv-file doi_urls.csv
```

## Backup and Recovery

### Backup Strategy

#### Daily Incremental Backups

```bash
#!/bin/bash
# daily_backup.sh
BACKUP_DIR="/backups/unpaywall"
DATE=$(date +%Y%m%d)

# Backup database
pg_dump -U unpaywall_user -d unpaywall -F c -f $BACKUP_DIR/db_$DATE.dump

# Keep only last 7 days
find $BACKUP_DIR -name "db_*.dump" -mtime +7 -delete
```

#### Weekly Full Backups

```bash
#!/bin/bash
# weekly_backup.sh
BACKUP_DIR="/backups/unpaywall/weekly"
DATE=$(date +%Y%m%d)

# Full database backup
pg_dump -U unpaywall_user -d unpaywall -F c -f $BACKUP_DIR/full_$DATE.dump

# Backup configuration
cp .env $BACKUP_DIR/env_$DATE

# Keep only last 4 weeks
find $BACKUP_DIR -name "full_*.dump" -mtime +28 -delete
```

### Recovery Procedures

#### Restore from Backup

```bash
# Drop and recreate database
psql -U postgres -c "DROP DATABASE IF EXISTS unpaywall;"
psql -U postgres -c "CREATE DATABASE unpaywall OWNER unpaywall_user;"

# Restore from backup
pg_restore -U unpaywall_user -d unpaywall backup.dump
```

#### Recover from Corrupted Table

```sql
-- Check for corruption
SELECT * FROM unpaywall.doi_urls LIMIT 1;

-- If corruption detected, restore specific table
pg_restore -U unpaywall_user -d unpaywall -t doi_urls backup.dump
```

## Monitoring

### Database Monitoring Queries

#### Connection Status

```sql
SELECT
    state,
    COUNT(*) as connections
FROM pg_stat_activity
WHERE datname = 'unpaywall'
GROUP BY state;
```

#### Long-Running Queries

```sql
SELECT
    pid,
    now() - query_start as duration,
    query
FROM pg_stat_activity
WHERE datname = 'unpaywall'
AND state != 'idle'
AND query_start < now() - interval '5 minutes'
ORDER BY duration DESC;
```

#### Table Growth Over Time

```sql
-- Run periodically and compare
SELECT
    schemaname,
    tablename,
    n_live_tup as row_count,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_stat_user_tables
WHERE schemaname = 'unpaywall';
```

### Automated Monitoring Script

```python
#!/usr/bin/env python3
"""Monitor Local Unpaywall health."""

import psycopg2
import os

def check_database():
    """Check database health."""
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        database=os.getenv('POSTGRES_DB', 'unpaywall'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )
    cursor = conn.cursor()

    # Check row count
    cursor.execute("SELECT COUNT(*) FROM unpaywall.doi_urls")
    row_count = cursor.fetchone()[0]
    print(f"Total rows: {row_count:,}")

    # Check database size
    cursor.execute("SELECT pg_size_pretty(pg_database_size('unpaywall'))")
    db_size = cursor.fetchone()[0]
    print(f"Database size: {db_size}")

    # Check for dead tuples
    cursor.execute("""
        SELECT n_dead_tup FROM pg_stat_user_tables
        WHERE schemaname = 'unpaywall' AND tablename = 'doi_urls'
    """)
    dead_tuples = cursor.fetchone()[0]
    if dead_tuples > 1000000:
        print(f"WARNING: High dead tuples ({dead_tuples:,}) - consider VACUUM")

    conn.close()

def check_disk_space():
    """Check available disk space."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (1024 ** 3)
    print(f"Free disk space: {free_gb} GB")
    if free_gb < 50:
        print("WARNING: Low disk space!")

if __name__ == '__main__':
    print("=== Local Unpaywall Health Check ===")
    check_database()
    check_disk_space()
```

## Troubleshooting Maintenance Issues

### Database Won't Start

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check logs
sudo tail -50 /var/log/postgresql/postgresql-15-main.log

# Common fix: repair data directory
sudo -u postgres pg_resetwal /var/lib/postgresql/15/main
```

### Slow Queries After Large Import

```sql
-- Rebuild statistics
ANALYZE unpaywall.doi_urls;

-- Rebuild indexes
REINDEX TABLE unpaywall.doi_urls;
```

### Disk Space Running Low

```bash
# Find large files
du -h /var/lib/postgresql/ | sort -rh | head -20

# Remove old WAL files (if not needed)
psql -U postgres -c "SELECT pg_switch_wal();"

# Clear old backups
find /backups -name "*.dump" -mtime +30 -delete
```

### Tracking Database Corrupted

```bash
# Remove corrupted tracking database
rm doi_urls.tracking.db

# Re-run extraction (will reprocess all files)
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --oa-only \
    --resume
```

## Automation with Cron

### Example Crontab

```bash
# Edit crontab
crontab -e

# Add these entries:

# Daily: Analyze tables at 2 AM
0 2 * * * psql -U unpaywall_user -d unpaywall -c "ANALYZE unpaywall.doi_urls;" >> /var/log/unpaywall_cron.log 2>&1

# Weekly: Vacuum on Sunday at 3 AM
0 3 * * 0 psql -U unpaywall_user -d unpaywall -c "VACUUM ANALYZE unpaywall.doi_urls;" >> /var/log/unpaywall_cron.log 2>&1

# Daily: Backup at 4 AM
0 4 * * * /path/to/daily_backup.sh >> /var/log/unpaywall_backup.log 2>&1

# Weekly: Full backup on Saturday at 4 AM
0 4 * * 6 /path/to/weekly_backup.sh >> /var/log/unpaywall_backup.log 2>&1
```

## Next Steps

- [Troubleshooting](09-troubleshooting.md) - Solve common problems
- [FAQ](10-faq.md) - Frequently asked questions
