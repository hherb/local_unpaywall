# DOI URL Importer Resume Functionality

## Overview

The DOI URL importer now includes robust resume functionality that allows interrupted imports to be continued from where they left off, avoiding the need to reprocess already imported data.

## Features

### Import Progress Tracking
- Each import is assigned a unique import ID
- Progress is tracked in the `import_progress` table
- File integrity is verified using SHA-256 hashes
- Batch-level progress tracking for fine-grained resume capability

### Resume Capabilities
- Automatic detection of incomplete imports
- File change detection to prevent data corruption
- Row-level resume (skips already processed rows)
- Progress validation and verification

### Safety Features
- File hash verification to detect changes
- User confirmation when file has changed
- Graceful handling of interrupted imports
- Comprehensive error tracking and logging

## Database Schema

### import_progress Table

```sql
CREATE TABLE import_progress (
    import_id TEXT PRIMARY KEY,
    csv_file_path TEXT NOT NULL,
    csv_file_hash TEXT NOT NULL,
    total_rows INTEGER NOT NULL,
    processed_rows INTEGER DEFAULT 0,
    last_batch_id INTEGER DEFAULT 0,
    status TEXT DEFAULT 'in_progress',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fields:**
- `import_id`: Unique identifier for each import session
- `csv_file_path`: Full path to the CSV file being imported
- `csv_file_hash`: SHA-256 hash of the CSV file for change detection
- `total_rows`: Total number of rows in the CSV file (excluding header)
- `processed_rows`: Number of rows successfully processed
- `last_batch_id`: ID of the last successfully processed batch
- `status`: Import status ('in_progress', 'completed', 'failed', 'cancelled')
- `start_time`: When the import started
- `end_time`: When the import completed (NULL if still running)
- `error_message`: Error details if import failed

## Usage

### Basic Import (No Resume)
```bash
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --db-name biomedical \
    --db-user myuser \
    --db-password mypass
```

### Resume Interrupted Import
```bash
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --db-name biomedical \
    --db-user myuser \
    --db-password mypass \
    --resume
```

### List Import History
```bash
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --db-name biomedical \
    --db-user myuser \
    --db-password mypass \
    --list-imports
```

## Resume Process Flow

1. **File Verification**: Calculate SHA-256 hash of CSV file
2. **Progress Check**: Look for incomplete imports of the same file
3. **Hash Comparison**: Verify file hasn't changed since last import
4. **User Confirmation**: If file changed, ask user whether to continue
5. **Resume Point**: Skip to the last successfully processed row
6. **Progress Tracking**: Update progress after each successful batch

## File Change Handling

When resuming, if the CSV file has changed:

```
CSV file has changed since last import (hash mismatch)
Previous hash: abc123...
Current hash: def456...
File has changed. Continue with new import? (y/N):
```

**Options:**
- **Y**: Cancel old import and start fresh
- **N**: Exit without importing

## Monitoring Progress

### During Import
The importer shows detailed progress information:
```
Processing batch 45 with 10000 rows (total processed: 450000, current row: 450000)
Batch 45 result: +9876 rows in database, 9876 reported inserted, 124 updated
```

### Import History
Use `--list-imports` to see recent import history:
```
Recent import history (last 10 imports):
----------------------------------------------------------------------------------------------------
ID: doi_urls_1703123456_abc12345
  File: /path/to/doi_urls.csv
  Status: completed
  Progress: 1000000/1000000 (100.0%)
  Started: 2023-12-21 10:30:00
  Ended: 2023-12-21 12:45:00

ID: doi_urls_1703120000_def67890
  File: /path/to/doi_urls.csv
  Status: failed
  Progress: 750000/1000000 (75.0%)
  Started: 2023-12-21 08:00:00
  Ended: 2023-12-21 09:30:00
  Error: Database connection lost
```

## Error Handling

### Common Scenarios

**Database Connection Lost**
- Import marked as 'failed' with error message
- Can be resumed with `--resume` flag
- Will continue from last successful batch

**File Modified During Import**
- Detected on next resume attempt
- User prompted to confirm action
- Old import marked as 'cancelled'

**Disk Space Issues**
- Import fails gracefully
- Progress preserved for resume
- Error logged with details

## Best Practices

### Large File Imports
1. Use `--resume` flag for files > 1GB
2. Monitor disk space during import
3. Use appropriate batch sizes (default: 10,000)
4. Run during low-traffic periods

### Recovery Procedures
1. Check import history: `--list-imports`
2. Verify file integrity if import failed
3. Resume with `--resume` flag
4. Monitor logs for detailed error information

### Performance Optimization
- Increase batch size for faster processing: `--batch-size 50000`
- Ensure adequate database connection pool
- Monitor PostgreSQL performance during import

## Troubleshooting

### Resume Not Working
1. Check if `import_progress` table exists
2. Verify database permissions
3. Check file path consistency
4. Review error logs

### File Hash Mismatch
1. Verify file hasn't been modified
2. Check file encoding consistency
3. Ensure file is completely downloaded
4. Use `--list-imports` to see previous hash

### Performance Issues
1. Increase `work_mem` in PostgreSQL
2. Temporarily disable autovacuum
3. Use smaller batch sizes if memory constrained
4. Monitor database locks and connections

## Integration with Existing Workflow

The resume functionality integrates seamlessly with existing import workflows:

1. **Automated Scripts**: Add `--resume` flag to cron jobs
2. **CI/CD Pipelines**: Handle interruptions gracefully
3. **Manual Operations**: Easy recovery from user interruptions
4. **Monitoring**: Track import progress via database queries

## Database Maintenance

### Cleanup Old Import Records
```sql
-- Remove completed imports older than 30 days
DELETE FROM import_progress 
WHERE status = 'completed' 
AND end_time < NOW() - INTERVAL '30 days';

-- Remove failed imports older than 7 days
DELETE FROM import_progress 
WHERE status = 'failed' 
AND start_time < NOW() - INTERVAL '7 days';
```

### Monitor Active Imports
```sql
-- Check currently running imports
SELECT import_id, csv_file_path, processed_rows, total_rows,
       ROUND(processed_rows::float / total_rows * 100, 2) as progress_pct,
       start_time
FROM import_progress 
WHERE status = 'in_progress'
ORDER BY start_time DESC;
```
