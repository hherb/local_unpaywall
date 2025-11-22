# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with Local Unpaywall.

## Quick Diagnostics

### System Check Script

Run this script to check your system status:

```bash
#!/bin/bash
echo "=== Local Unpaywall Diagnostics ==="

echo -e "\n--- Python Version ---"
python3 --version

echo -e "\n--- PostgreSQL Status ---"
pg_isready -h localhost

echo -e "\n--- Disk Space ---"
df -h | grep -E '^/dev|Filesystem'

echo -e "\n--- Database Connection ---"
psql -h localhost -U unpaywall_user -d unpaywall -c "SELECT 1 as connected;" 2>&1

echo -e "\n--- Table Row Count ---"
psql -h localhost -U unpaywall_user -d unpaywall -c "SELECT COUNT(*) as rows FROM unpaywall.doi_urls;" 2>&1

echo -e "\n--- Recent Errors ---"
grep -i error *.log 2>/dev/null | tail -5 || echo "No log files found"
```

## Installation Issues

### Python Version Error

**Error:**
```
SyntaxError: invalid syntax
```
or
```
ModuleNotFoundError: No module named 'typing'
```

**Cause:** Python version is too old.

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.12+ if needed
# Ubuntu/Debian
sudo apt install python3.12

# macOS
brew install python@3.12
```

### psycopg2 Installation Fails

**Error:**
```
Error: pg_config executable not found
```

**Solution:**
```bash
# Ubuntu/Debian
sudo apt install libpq-dev python3-dev

# Fedora/RHEL
sudo dnf install postgresql-devel python3-devel

# macOS
brew install postgresql

# Then reinstall
pip install psycopg2-binary
```

### Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'tqdm'
```

**Solution:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Install missing module
pip install tqdm

# Or install all dependencies
pip install psycopg2-binary tqdm requests python-dotenv
```

## Database Connection Issues

### Connection Refused

**Error:**
```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Causes & Solutions:**

1. **PostgreSQL not running:**
   ```bash
   # Check status
   sudo systemctl status postgresql

   # Start if not running
   sudo systemctl start postgresql
   ```

2. **Wrong port:**
   ```bash
   # Check PostgreSQL port
   sudo ss -tlnp | grep postgres

   # Update .env with correct port
   POSTGRES_PORT=5432
   ```

3. **Wrong host:**
   ```bash
   # Try localhost vs 127.0.0.1
   POSTGRES_HOST=127.0.0.1
   ```

### Authentication Failed

**Error:**
```
psycopg2.OperationalError: password authentication failed for user "unpaywall_user"
```

**Solution:**
```bash
# Reset password
sudo -u postgres psql -c "ALTER USER unpaywall_user PASSWORD 'new_password';"

# Update .env
POSTGRES_PASSWORD=new_password
```

### Permission Denied

**Error:**
```
psycopg2.ProgrammingError: permission denied for schema unpaywall
```

**Solution:**
```sql
-- As postgres user
GRANT ALL ON SCHEMA unpaywall TO unpaywall_user;
GRANT ALL ON ALL TABLES IN SCHEMA unpaywall TO unpaywall_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA unpaywall TO unpaywall_user;
```

### Database Does Not Exist

**Error:**
```
psycopg2.OperationalError: database "unpaywall" does not exist
```

**Solution:**
```bash
# Create database
sudo -u postgres createdb -O unpaywall_user unpaywall

# Or via psql
sudo -u postgres psql -c "CREATE DATABASE unpaywall OWNER unpaywall_user;"
```

## Extraction Issues

### Snapshot Directory Not Found

**Error:**
```
FileNotFoundError: Snapshot directory not found: ./openalex-snapshot
```

**Solution:**
```bash
# Check if directory exists
ls -la ./openalex-snapshot/

# Download OpenAlex data if missing
aws s3 sync "s3://openalex/data/works" "./openalex-snapshot/data/works" --no-sign-request
```

### No Files to Process

**Error:**
```
No JSONL files found in snapshot directory
```

**Solution:**
```bash
# Check directory structure
find ./openalex-snapshot -name "*.gz" | head -5

# Correct structure should be:
# openalex-snapshot/data/works/updated_date=YYYY-MM-DD/part_XXX.gz
```

### Memory Error During Extraction

**Error:**
```
MemoryError
```

**Solution:**
The extractor uses streaming and should have minimal memory usage. If this occurs:
```bash
# Check available memory
free -h

# Close other applications
# Restart the extraction
python openalex_unpaywall_extractor.py --snapshot-dir ./openalex-snapshot --output urls.csv --resume
```

### Permission Denied on Output File

**Error:**
```
PermissionError: [Errno 13] Permission denied: 'urls.csv'
```

**Solution:**
```bash
# Check file permissions
ls -la urls.csv

# Remove file if owned by another user
sudo rm urls.csv

# Or change ownership
sudo chown $USER:$USER urls.csv
```

### Tracking Database Locked

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
```bash
# Another process may be using the tracking database
# Find and kill it
ps aux | grep openalex

# Or remove the lock
rm urls.tracking.db-journal

# If persistent, remove and restart
rm urls.tracking.db
python openalex_unpaywall_extractor.py --resume
```

## Import Issues

### CSV File Not Found

**Error:**
```
FileNotFoundError: CSV file not found: urls.csv
```

**Solution:**
```bash
# Check file exists
ls -la urls.csv

# Check you're in the correct directory
pwd
```

### Malformed CSV

**Error:**
```
csv.Error: line contains NUL
```

**Solution:**
```bash
# Remove NUL characters
sed -i 's/\x0//g' urls.csv

# Or recreate the CSV
rm urls.csv
python openalex_unpaywall_extractor.py --snapshot-dir ./openalex-snapshot --output urls.csv
```

### Duplicate Key Error

**Error:**
```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
```

**Solution:**
This shouldn't happen with normal operation (the importer uses ON CONFLICT). If it does:
```sql
-- Check for duplicates
SELECT doi, url, COUNT(*)
FROM unpaywall.doi_urls
GROUP BY doi, url
HAVING COUNT(*) > 1;
```

### Import Running Slowly

**Possible causes:**

1. **Small batch size:** Increase with `--batch-size 50000`
2. **Autovacuum running:** Temporarily disable:
   ```sql
   ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = false);
   ```
3. **Slow disk:** Use SSD if possible
4. **Insufficient memory:** Increase PostgreSQL `work_mem`

### Out of Disk Space

**Error:**
```
psycopg2.errors.DiskFull: could not extend file
```

**Solution:**
```bash
# Check disk space
df -h

# Clear old files
rm -f *.log.old *.csv.bak

# Move PostgreSQL data to larger disk if needed
```

## Query Issues

### Slow Query Performance

**Problem:** Queries taking too long

**Solutions:**

1. **Update statistics:**
   ```sql
   ANALYZE unpaywall.doi_urls;
   ```

2. **Check query plan:**
   ```sql
   EXPLAIN ANALYZE SELECT * FROM unpaywall.doi_urls WHERE doi = '10.1038/xxx';
   ```

3. **Ensure indexes exist:**
   ```sql
   SELECT indexname FROM pg_indexes WHERE tablename = 'doi_urls';
   ```

4. **Rebuild indexes:**
   ```sql
   REINDEX TABLE unpaywall.doi_urls;
   ```

### No Results Returned

**Problem:** Query returns empty results when data should exist

**Solutions:**

1. **Check DOI format:**
   ```sql
   -- DOIs are stored without 'https://doi.org/' prefix
   SELECT * FROM unpaywall.doi_urls WHERE doi = '10.1038/nature12373';  -- Correct
   SELECT * FROM unpaywall.doi_urls WHERE doi = 'https://doi.org/10.1038/nature12373';  -- Wrong
   ```

2. **Check case sensitivity:**
   ```sql
   -- DOIs are typically lowercase
   SELECT * FROM unpaywall.doi_urls WHERE LOWER(doi) = LOWER('10.1038/Nature12373');
   ```

3. **Verify data was imported:**
   ```sql
   SELECT COUNT(*) FROM unpaywall.doi_urls;
   ```

## PDF Download Issues

### Connection Timeout

**Error:**
```
requests.exceptions.ConnectTimeout
```

**Solution:**
```bash
# Increase timeout
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" --timeout 120
```

### SSL Certificate Error

**Error:**
```
requests.exceptions.SSLError: certificate verify failed
```

**Solution:**
```python
# In Python code (not recommended for production)
fetcher = PDFFetcher()
fetcher.session.verify = False  # Disable SSL verification
```

Better solution: Update certificates:
```bash
# Ubuntu/Debian
sudo apt install ca-certificates
sudo update-ca-certificates

# macOS
brew install ca-certificates
```

### 403 Forbidden

**Error:**
```
requests.exceptions.HTTPError: 403 Forbidden
```

**Causes:**
- Publisher blocking automated downloads
- IP rate limited

**Solutions:**
1. Add delays between downloads
2. Use a different User-Agent
3. Access through institutional proxy

### Downloaded File Not a PDF

**Error:**
```
Downloaded file is not a valid PDF
```

**Cause:** URL returned HTML (login page) instead of PDF

**Solution:**
```bash
# Skip invalid URLs and log them
# The PDF fetcher already validates content
```

## Getting More Help

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
python openalex_unpaywall_extractor.py --resume
```

### Collect Diagnostic Information

When reporting issues, include:

```bash
# System information
uname -a
python3 --version
psql --version

# Database status
psql -U unpaywall_user -d unpaywall -c "SELECT version();"
psql -U unpaywall_user -d unpaywall -c "SELECT COUNT(*) FROM unpaywall.doi_urls;"

# Recent log entries
tail -100 *.log
```

### Report Issues

Report bugs at: https://github.com/hherb/local_unpaywall/issues

Include:
1. Steps to reproduce
2. Error messages (full stack trace)
3. System information
4. Log file excerpts
