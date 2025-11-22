# Querying Your Data

This guide covers how to find and use the data in your Local Unpaywall database.

## Connecting to the Database

### Using psql

```bash
psql -h localhost -U unpaywall_user -d unpaywall
```

### Using Python

```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="unpaywall",
    user="unpaywall_user",
    password="your_password"
)
cursor = conn.cursor()
```

### Using a GUI Tool

Popular options:
- **pgAdmin** - Official PostgreSQL admin tool
- **DBeaver** - Universal database tool
- **DataGrip** - JetBrains database IDE

## Basic Queries

### Find URLs for a DOI

```sql
SELECT url, pdf_url
FROM unpaywall.doi_urls
WHERE doi = '10.1038/nature12373';
```

### Find All Information for a DOI

```sql
SELECT
    d.doi,
    d.url,
    d.pdf_url,
    d.title,
    d.publication_year,
    l.value AS license,
    o.value AS oa_status,
    h.value AS host_type,
    w.value AS work_type,
    d.is_oa,
    d.is_retracted
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
LEFT JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
LEFT JOIN unpaywall.host_type h ON d.host_type_id = h.id
LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id
WHERE d.doi = '10.1038/nature12373';
```

### Search by Title

```sql
SELECT doi, title, url
FROM unpaywall.doi_urls
WHERE title ILIKE '%crystal structure%'
LIMIT 20;
```

### Find Multiple DOIs

```sql
SELECT doi, url, pdf_url
FROM unpaywall.doi_urls
WHERE doi IN (
    '10.1038/nature12373',
    '10.1126/science.1234567',
    '10.1371/journal.pone.0123456'
);
```

## Filtering Queries

### By Open Access Status

```sql
-- Gold OA only
SELECT d.doi, d.url, d.title
FROM unpaywall.doi_urls d
JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
WHERE o.value = 'gold'
LIMIT 100;

-- Any open access
SELECT doi, url, title
FROM unpaywall.doi_urls
WHERE is_oa = TRUE
LIMIT 100;
```

### By Publication Year

```sql
-- Articles from 2023
SELECT doi, url, title
FROM unpaywall.doi_urls
WHERE publication_year = 2023
LIMIT 100;

-- Articles from last 5 years
SELECT doi, url, title
FROM unpaywall.doi_urls
WHERE publication_year >= 2019
LIMIT 100;
```

### By License

```sql
-- CC-BY licensed articles
SELECT d.doi, d.url, d.title
FROM unpaywall.doi_urls d
JOIN unpaywall.license l ON d.license_id = l.id
WHERE l.value = 'cc-by'
LIMIT 100;

-- Any Creative Commons license
SELECT d.doi, d.url, l.value AS license
FROM unpaywall.doi_urls d
JOIN unpaywall.license l ON d.license_id = l.id
WHERE l.value LIKE 'cc-%'
LIMIT 100;
```

### By Work Type

```sql
-- Journal articles only
SELECT d.doi, d.url, d.title
FROM unpaywall.doi_urls d
JOIN unpaywall.work_type w ON d.work_type_id = w.id
WHERE w.value = 'journal-article'
LIMIT 100;

-- Preprints
SELECT d.doi, d.url, d.title
FROM unpaywall.doi_urls d
JOIN unpaywall.work_type w ON d.work_type_id = w.id
WHERE w.value = 'preprint'
LIMIT 100;
```

### By Host Type

```sql
-- Repository copies only
SELECT d.doi, d.url, d.title
FROM unpaywall.doi_urls d
JOIN unpaywall.host_type h ON d.host_type_id = h.id
WHERE h.value = 'repository'
LIMIT 100;
```

### Excluding Retracted Articles

```sql
SELECT doi, url, title
FROM unpaywall.doi_urls
WHERE is_retracted = FALSE
AND is_oa = TRUE
LIMIT 100;
```

## Statistical Queries

### Count Records

```sql
-- Total records
SELECT COUNT(*) FROM unpaywall.doi_urls;

-- Unique DOIs
SELECT COUNT(DISTINCT doi) FROM unpaywall.doi_urls;

-- Open access records
SELECT COUNT(*) FROM unpaywall.doi_urls WHERE is_oa = TRUE;
```

### Records by Year

```sql
SELECT
    publication_year,
    COUNT(*) AS total,
    COUNT(CASE WHEN is_oa THEN 1 END) AS open_access,
    ROUND(100.0 * COUNT(CASE WHEN is_oa THEN 1 END) / COUNT(*), 1) AS oa_percentage
FROM unpaywall.doi_urls
WHERE publication_year IS NOT NULL
AND publication_year >= 2010
GROUP BY publication_year
ORDER BY publication_year DESC;
```

### Records by OA Status

```sql
SELECT
    o.value AS oa_status,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS percentage
FROM unpaywall.doi_urls d
JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
GROUP BY o.value
ORDER BY count DESC;
```

### Records by License

```sql
SELECT
    COALESCE(l.value, 'Unknown') AS license,
    COUNT(*) AS count
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
GROUP BY l.value
ORDER BY count DESC
LIMIT 20;
```

### Records by Work Type

```sql
SELECT
    COALESCE(w.value, 'Unknown') AS work_type,
    COUNT(*) AS count
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id
GROUP BY w.value
ORDER BY count DESC;
```

### PDF Availability

```sql
SELECT
    COUNT(*) AS total_records,
    COUNT(pdf_url) AS with_pdf_url,
    ROUND(100.0 * COUNT(pdf_url) / COUNT(*), 1) AS pdf_percentage
FROM unpaywall.doi_urls;
```

## Advanced Queries

### Best URL for Each DOI

```sql
-- Get highest quality URL per DOI
SELECT DISTINCT ON (doi)
    doi, url, pdf_url, url_quality_score
FROM unpaywall.doi_urls
ORDER BY doi, url_quality_score DESC;
```

### DOIs with Multiple URLs

```sql
SELECT
    doi,
    COUNT(*) AS url_count,
    ARRAY_AGG(url) AS urls
FROM unpaywall.doi_urls
GROUP BY doi
HAVING COUNT(*) > 1
LIMIT 100;
```

### Recent Changes

```sql
SELECT doi, url, updated_at
FROM unpaywall.doi_urls
ORDER BY updated_at DESC
LIMIT 100;
```

### Full-Text Search on Titles

```sql
-- Create text search index (run once)
CREATE INDEX idx_doi_urls_title_search
ON unpaywall.doi_urls
USING gin(to_tsvector('english', title));

-- Search titles
SELECT doi, title, url
FROM unpaywall.doi_urls
WHERE to_tsvector('english', title) @@ to_tsquery('english', 'machine & learning')
LIMIT 50;
```

## Exporting Data

### Export to CSV

```sql
-- From psql
\copy (SELECT doi, url, pdf_url FROM unpaywall.doi_urls WHERE is_oa = TRUE LIMIT 10000) TO 'export.csv' WITH CSV HEADER;
```

### Export Using Python

```python
import psycopg2
import csv

conn = psycopg2.connect(...)
cursor = conn.cursor()

cursor.execute("""
    SELECT doi, url, pdf_url, title
    FROM unpaywall.doi_urls
    WHERE is_oa = TRUE
    LIMIT 10000
""")

with open('export.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['doi', 'url', 'pdf_url', 'title'])
    writer.writerows(cursor.fetchall())
```

## Creating Views

### Simplified Query View

```sql
CREATE VIEW unpaywall.doi_urls_expanded AS
SELECT
    d.doi,
    d.url,
    d.pdf_url,
    d.title,
    d.publication_year,
    d.location_type,
    d.version,
    l.value AS license,
    o.value AS oa_status,
    h.value AS host_type,
    w.value AS work_type,
    d.is_oa,
    d.is_retracted,
    d.url_quality_score
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
LEFT JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
LEFT JOIN unpaywall.host_type h ON d.host_type_id = h.id
LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id;

-- Use the view
SELECT * FROM unpaywall.doi_urls_expanded
WHERE doi = '10.1038/nature12373';
```

### Best URL per DOI View

```sql
CREATE VIEW unpaywall.best_urls AS
SELECT DISTINCT ON (doi)
    doi, url, pdf_url, title, publication_year, is_oa
FROM unpaywall.doi_urls
ORDER BY doi, url_quality_score DESC;

-- Use the view
SELECT * FROM unpaywall.best_urls
WHERE doi = '10.1038/nature12373';
```

## Python Integration

### Simple Lookup Function

```python
import psycopg2

def get_open_access_url(doi):
    """Get the best open access URL for a DOI."""
    conn = psycopg2.connect(
        host="localhost",
        database="unpaywall",
        user="unpaywall_user",
        password="your_password"
    )
    cursor = conn.cursor()

    cursor.execute("""
        SELECT url, pdf_url
        FROM unpaywall.doi_urls
        WHERE doi = %s
        ORDER BY url_quality_score DESC
        LIMIT 1
    """, (doi,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {'url': result[0], 'pdf_url': result[1]}
    return None

# Usage
url_info = get_open_access_url('10.1038/nature12373')
if url_info:
    print(f"URL: {url_info['url']}")
    print(f"PDF: {url_info['pdf_url']}")
```

### Batch Lookup

```python
def get_urls_for_dois(dois):
    """Get URLs for multiple DOIs."""
    conn = psycopg2.connect(...)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT doi, url, pdf_url
        FROM unpaywall.doi_urls
        WHERE doi = ANY(%s)
    """, (dois,))

    results = {}
    for doi, url, pdf_url in cursor.fetchall():
        if doi not in results:
            results[doi] = []
        results[doi].append({'url': url, 'pdf_url': pdf_url})

    conn.close()
    return results

# Usage
dois = ['10.1038/nature12373', '10.1126/science.1234567']
results = get_urls_for_dois(dois)
```

## Performance Tips

### Use Indexes

The database includes indexes on commonly queried columns:
- `doi` - for DOI lookups
- `url` - for URL lookups
- `pdf_url` - for PDF URL lookups
- `is_oa` - for open access filtering

### Limit Results

Always use `LIMIT` when exploring data:

```sql
-- Good
SELECT * FROM unpaywall.doi_urls LIMIT 100;

-- Avoid (may return millions of rows)
SELECT * FROM unpaywall.doi_urls;
```

### Use EXPLAIN ANALYZE

Check query performance:

```sql
EXPLAIN ANALYZE
SELECT * FROM unpaywall.doi_urls
WHERE doi = '10.1038/nature12373';
```

## Next Steps

- [Maintenance](08-maintenance.md) - Keep your database healthy
- [Troubleshooting](09-troubleshooting.md) - Solve common problems
