# Configuration Guide

This guide covers all configuration options for Local Unpaywall.

## Environment Configuration

### The .env File

Local Unpaywall uses a `.env` file for configuration. This file should be placed in the project root directory.

### Basic Configuration

Create a `.env` file with your database settings:

```bash
# Database Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unpaywall
POSTGRES_USER=unpaywall_user
POSTGRES_PASSWORD=your_secure_password
```

### Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `POSTGRES_HOST` | Database server hostname | localhost | Yes |
| `POSTGRES_PORT` | Database server port | 5432 | No |
| `POSTGRES_DB` | Database name | - | Yes |
| `POSTGRES_USER` | Database username | - | Yes |
| `POSTGRES_PASSWORD` | Database password | - | Yes |

### Security Best Practices

1. **Never commit `.env` to version control**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use strong passwords**
   ```bash
   # Generate a secure password
   openssl rand -base64 32
   ```

3. **Restrict file permissions**
   ```bash
   chmod 600 .env
   ```

## Database Configuration

### PostgreSQL Settings for Large Imports

For optimal performance when importing millions of records, tune your PostgreSQL configuration.

Edit `postgresql.conf` (usually in `/etc/postgresql/15/main/` on Linux):

```ini
# Memory Settings
shared_buffers = 4GB              # 25% of available RAM
effective_cache_size = 12GB       # 75% of available RAM
work_mem = 256MB                  # For sorting operations
maintenance_work_mem = 1GB        # For CREATE INDEX, VACUUM

# Write Performance
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB

# Parallelism
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
```

After editing, restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### Connection Pooling (Optional)

For high-concurrency applications, consider using PgBouncer:

```bash
# Install PgBouncer
sudo apt install pgbouncer

# Configure /etc/pgbouncer/pgbouncer.ini
[databases]
unpaywall = host=localhost dbname=unpaywall

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
```

## Disk Space Planning

### Estimating Space Requirements

| Dataset | Compressed | CSV Output | Database |
|---------|------------|------------|----------|
| Full OpenAlex | 384 GB | ~100 GB | ~150 GB |
| OA Only | - | ~40 GB | ~60 GB |
| Last 5 Years | - | ~20 GB | ~30 GB |
| Last Year | - | ~5 GB | ~8 GB |

### Recommended Directory Structure

```
/data/
├── openalex-snapshot/     # Downloaded snapshot (384GB)
│   └── data/
│       └── works/
├── output/                 # Extracted CSV files
│   ├── doi_urls.csv
│   └── doi_urls.tracking.db
└── pdfs/                   # Downloaded PDFs (variable)
```

### Managing Disk Space

```bash
# Check current disk usage
df -h

# Check directory sizes
du -sh /data/openalex-snapshot/
du -sh /data/output/

# Clean up old tracking databases
rm -f /data/output/*.tracking.db.backup
```

## Logging Configuration

### Default Logging

Scripts automatically create log files in the project directory:
- `openalex_url_extraction.log` - Extractor logs
- `doi_url_import.log` - Importer logs

### Customizing Log Level

Set the log level via environment variable:
```bash
export LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

Or in Python:
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Log Rotation

For long-running operations, set up log rotation:

```bash
# /etc/logrotate.d/local_unpaywall
/path/to/local_unpaywall/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## Network Configuration

### Firewall Rules

If your database is on a separate server, open the PostgreSQL port:

```bash
# UFW (Ubuntu)
sudo ufw allow from 192.168.1.0/24 to any port 5432

# firewalld (Fedora/RHEL)
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="5432" protocol="tcp" accept'
sudo firewall-cmd --reload
```

### PostgreSQL Remote Access

Edit `pg_hba.conf` to allow remote connections:

```
# IPv4 local connections:
host    unpaywall    unpaywall_user    192.168.1.0/24    scram-sha-256
```

Edit `postgresql.conf`:
```ini
listen_addresses = '*'  # Or specific IP
```

## Batch Processing Configuration

### Tuning Batch Sizes

Adjust batch sizes based on your system's memory:

| RAM | Recommended Batch Size |
|-----|----------------------|
| 4 GB | 5,000 |
| 8 GB | 10,000 |
| 16 GB | 25,000 |
| 32 GB+ | 50,000 |

Command-line configuration:
```bash
python doi_url_importer.py --csv-file urls.csv --batch-size 25000
```

### Parallel Processing

The extractor supports parallel file processing:
```bash
# Use multiple workers (default: 1)
python openalex_unpaywall_extractor.py --max-workers 4
```

> **Note**: Parallel processing may cause issues with file tracking. Sequential processing (max-workers=1) is recommended for reliability.

## Verification

### Test Your Configuration

```bash
# Test database connection
python -c "
from db.create_db import DatabaseCreator
creator = DatabaseCreator.from_env_or_args()
print('Testing connection...')
if creator.test_connection():
    print('SUCCESS: Database connection working')
else:
    print('FAILED: Could not connect to database')
"
```

### Check Database Schema

```bash
psql -h localhost -U unpaywall_user -d unpaywall -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'unpaywall';
"
```

Expected output:
```
   table_name
-----------------
 license
 oa_status
 host_type
 work_type
 doi_urls
 import_progress
```

## Next Steps

With configuration complete, proceed to:
- [Extracting URLs](04-extracting-urls.md) - Download and process OpenAlex data
