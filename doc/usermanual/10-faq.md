# Frequently Asked Questions

## General Questions

### What is Local Unpaywall?

Local Unpaywall is a system for creating your own local database of open access publication URLs. It processes data from OpenAlex to extract DOI-URL mappings, allowing you to quickly find open access versions of scholarly articles.

### How is this different from the Unpaywall service?

| Feature | Unpaywall | Local Unpaywall |
|---------|-----------|-----------------|
| API Rate Limits | Yes (100K/day) | None |
| Response Time | Network latency | Local (milliseconds) |
| Privacy | Queries logged | Fully local |
| Availability | Requires internet | Works offline |
| Cost | Free tier + paid | One-time setup |
| Customization | Limited | Full control |

### Is this legal?

Yes. Local Unpaywall uses publicly available data from OpenAlex, which is released under a CC0 public domain dedication. The URLs it stores point to legally available open access content.

### How current is the data?

The data is as current as your last OpenAlex snapshot download. OpenAlex updates daily, but you control when to update your local copy. Most users update monthly or quarterly.

### How much disk space do I need?

| Use Case | Compressed Data | Database |
|----------|-----------------|----------|
| Full dataset | ~400 GB | ~150 GB |
| OA only | ~100 GB | ~50 GB |
| Last 5 years | ~100 GB | ~40 GB |
| Last year | ~25 GB | ~10 GB |

## Installation Questions

### What are the minimum system requirements?

- Python 3.12+
- PostgreSQL 13+
- 4 GB RAM (8 GB+ recommended)
- 50 GB disk space (minimum useful dataset)

### Can I run this on Windows?

Yes, but Linux or macOS is recommended. On Windows, use WSL2 (Windows Subsystem for Linux) for best results.

### Can I use MySQL instead of PostgreSQL?

No, the system is designed specifically for PostgreSQL. The normalized schema uses PostgreSQL-specific features for optimal performance.

### Do I need root/admin access?

Not necessarily. You need:
- Permission to install Python packages (or use virtual environments)
- Access to a PostgreSQL database (can be remote)
- Write access to a data directory

## Data Questions

### How many records are in OpenAlex?

As of 2024, OpenAlex contains over 250 million scholarly works. Not all have open access URLs; approximately 40% have at least one OA location.

### What types of publications are included?

- Journal articles
- Conference papers
- Books and book chapters
- Preprints
- Dissertations
- Datasets
- And more...

### Are retracted papers included?

Yes, by default. You can exclude them with the `--exclude-retracted` flag during extraction, or filter them out in queries:

```sql
SELECT * FROM unpaywall.doi_urls WHERE is_retracted = FALSE;
```

### What open access types are tracked?

| Status | Description |
|--------|-------------|
| gold | Published OA with license |
| green | Repository copy |
| bronze | Free to read, no license |
| hybrid | OA article in subscription journal |
| closed | Not open access |

### Why are there multiple URLs for one DOI?

A single article may have multiple open access copies:
- Publisher version (gold OA)
- Preprint server (e.g., arXiv)
- Institutional repository
- PubMed Central

All versions are stored with their metadata.

## Usage Questions

### How do I find the best URL for a DOI?

```sql
SELECT url, pdf_url
FROM unpaywall.doi_urls
WHERE doi = '10.1038/nature12373'
ORDER BY url_quality_score DESC
LIMIT 1;
```

### Can I search by article title?

Yes, but it's slower than DOI lookup:

```sql
SELECT doi, title, url
FROM unpaywall.doi_urls
WHERE title ILIKE '%machine learning%'
LIMIT 100;
```

For faster title search, create a full-text index (see [Querying Data](07-querying-data.md)).

### How do I export data to Excel?

```bash
# Export to CSV (Excel-compatible)
psql -U unpaywall_user -d unpaywall -c "\copy (SELECT doi, url, title FROM unpaywall.doi_urls LIMIT 10000) TO 'export.csv' CSV HEADER"
```

### Can I integrate with my library system?

Yes. The PostgreSQL database can be accessed from any programming language. Common integrations:
- REST API wrapper
- Direct database queries
- Scheduled exports to other systems

### How do I handle DOIs with special characters?

DOIs may contain characters like `<`, `>`, or non-ASCII characters. Always use parameterized queries:

```python
# Correct - parameterized query
cursor.execute("SELECT * FROM unpaywall.doi_urls WHERE doi = %s", (doi,))

# Wrong - string formatting (SQL injection risk)
cursor.execute(f"SELECT * FROM unpaywall.doi_urls WHERE doi = '{doi}'")
```

## Performance Questions

### How fast are queries?

Single DOI lookups typically complete in under 10 milliseconds. The database includes indexes on commonly queried columns.

### How long does initial setup take?

| Step | Time (typical) |
|------|----------------|
| Download OpenAlex (full) | 4-12 hours |
| Extract URLs | 4-8 hours |
| Import to database | 10-24 hours |
| **Total** | **1-2 days** |

Smaller datasets (OA only, recent years) are much faster.

### Can I run multiple imports in parallel?

Not recommended. The importer uses batch processing with progress tracking. Running multiple instances may cause conflicts.

### Why is my import slow?

Common causes:
1. Small batch size → increase `--batch-size`
2. Autovacuum running → temporarily disable
3. Slow disk → use SSD
4. Insufficient memory → increase PostgreSQL `work_mem`

## Maintenance Questions

### How often should I update the data?

Depends on your needs:
- **Research projects**: Monthly or quarterly
- **Library services**: Monthly
- **Critical applications**: Weekly

### How do I update without losing data?

The importer uses upsert (ON CONFLICT UPDATE), so existing records are updated and new records are added:

```bash
python doi_url_importer.py --csv-file new_urls.csv --resume
```

### Can I delete old data?

Yes:

```sql
-- Delete records older than 5 years
DELETE FROM unpaywall.doi_urls
WHERE publication_year < 2019;

-- Reclaim space
VACUUM FULL unpaywall.doi_urls;
```

### How do I backup my database?

```bash
# Full backup
pg_dump -U unpaywall_user -d unpaywall -F c -f backup.dump

# Restore
pg_restore -U unpaywall_user -d unpaywall backup.dump
```

## Troubleshooting Questions

### Why do I get "connection refused"?

PostgreSQL isn't running or isn't accepting connections. See [Troubleshooting](09-troubleshooting.md#connection-refused).

### Why is my CSV file empty?

Check:
1. OpenAlex snapshot exists and has data
2. Filters aren't too restrictive (try without `--oa-only`)
3. Log file for errors

### Why do some DOIs return no results?

Possible reasons:
1. DOI not in OpenAlex
2. No open access URL available
3. Data was filtered during extraction
4. Typo in DOI format

### How do I reset everything and start over?

```bash
# Remove tracking databases
rm -f *.tracking.db

# Truncate database tables
psql -U unpaywall_user -d unpaywall -c "
TRUNCATE unpaywall.doi_urls CASCADE;
TRUNCATE unpaywall.import_progress;
"

# Remove CSV files
rm -f *.csv

# Start fresh
python openalex_unpaywall_extractor.py --snapshot-dir ./openalex-snapshot --output urls.csv
python doi_url_importer.py --csv-file urls.csv
```

## PDF Download Questions

### Can I download all PDFs automatically?

Technically yes, but:
- It would require terabytes of storage
- Many publishers block bulk downloads
- Be respectful of server resources

Download selectively based on your research needs.

### Why do some PDF downloads fail?

Common reasons:
1. URL requires authentication
2. Publisher blocking automated access
3. Article behind paywall (incorrect OA status)
4. URL no longer valid

### How do I handle paywalled content?

Local Unpaywall only stores URLs to legally free content. If a URL leads to a paywall:
1. The OA status may have changed
2. Try a different URL for the same DOI
3. Check for repository copies

## Getting Help

### Where can I report bugs?

GitHub Issues: https://github.com/hherb/local_unpaywall/issues

### Where can I request features?

GitHub Issues with the "enhancement" label.

### Is there commercial support?

Not currently. This is an open-source project.

### How can I contribute?

See [DEVELOPERS.md](../../DEVELOPERS.md) for contribution guidelines. Pull requests welcome!
