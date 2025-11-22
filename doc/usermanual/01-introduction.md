# Introduction to Local Unpaywall

## What is Local Unpaywall?

Local Unpaywall is a system for creating your own local database of open access publication URLs. It processes data from [OpenAlex](https://openalex.org/), a free and open catalog of the world's scholarly works, to extract and store mappings between DOIs (Digital Object Identifiers) and their corresponding open access URLs.

Think of it as building your own "Unpaywall" service that runs entirely on your infrastructure.

## Why Use Local Unpaywall?

### Speed and Reliability
- **No API rate limits**: Query millions of DOIs without throttling
- **Instant responses**: Local database queries in milliseconds
- **No network dependency**: Works offline once data is loaded
- **Always available**: No reliance on external service uptime

### Privacy and Control
- **Your data stays local**: No queries sent to external services
- **Complete control**: Customize filtering, storage, and access
- **Audit capability**: Track all lookups and usage

### Cost Effectiveness
- **No subscription fees**: One-time setup, no ongoing costs
- **Efficient storage**: Normalized schema minimizes disk usage
- **Scalable**: Handle any volume of queries

### Research Applications
- **Bibliometric analysis**: Analyze open access trends
- **Bulk processing**: Process millions of DOIs in batch
- **Custom filtering**: Filter by year, license, repository type
- **Integration ready**: Connect to your existing systems

## What Can You Do With It?

### 1. Find Open Access URLs
Given a DOI, instantly find all available open access URLs:
```sql
SELECT url, pdf_url FROM unpaywall.doi_urls
WHERE doi = '10.1038/nature12373';
```

### 2. Analyze Open Access Coverage
Generate statistics about open access availability:
```sql
SELECT publication_year, COUNT(*) as total,
       COUNT(CASE WHEN is_oa THEN 1 END) as open_access
FROM unpaywall.doi_urls
GROUP BY publication_year
ORDER BY publication_year DESC;
```

### 3. Download Full-Text PDFs
Automatically download PDFs for your research:
```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./papers/"
```

### 4. Build Custom Applications
Use the database as a backend for:
- Library discovery systems
- Research data management
- Open access monitoring dashboards
- Citation analysis tools

## How Does It Work?

Local Unpaywall operates in three main stages:

### Stage 1: Extract
The **OpenAlex URL Extractor** processes OpenAlex snapshot files:
- Reads compressed JSONL files directly (no decompression needed)
- Extracts DOI, URL, PDF URL, and metadata for each work
- Applies filters (year range, OA status, work type)
- Tracks progress for resume capability
- Outputs to CSV, JSON, or TSV format

### Stage 2: Import
The **DOI-URL Importer** loads extracted data into PostgreSQL:
- Processes data in memory-efficient batches
- Normalizes data into lookup tables for storage efficiency
- Handles duplicates with intelligent upsert logic
- Supports resume from interrupted imports

### Stage 3: Query
Once imported, you can:
- Query the database directly with SQL
- Integrate with your applications via PostgreSQL drivers
- Download PDFs using the PDF Fetcher utility

## Data Overview

### What Data is Stored?

For each DOI-URL pair, Local Unpaywall stores:

| Field | Description | Example |
|-------|-------------|---------|
| doi | Digital Object Identifier | 10.1038/nature12373 |
| url | Open access URL | https://europepmc.org/... |
| pdf_url | Direct PDF link | https://europepmc.org/...pdf |
| title | Publication title | "Crystal structure of..." |
| publication_year | Year published | 2013 |
| license | License type | cc-by |
| oa_status | Open access status | gold, green, bronze |
| host_type | Where hosted | publisher, repository |
| work_type | Publication type | journal-article |
| is_oa | Is open access | true/false |
| is_retracted | Is retracted | true/false |

### Data Sources

All data comes from [OpenAlex](https://openalex.org/), which aggregates information from:
- Crossref (DOIs and metadata)
- Unpaywall (open access locations)
- PubMed (biomedical literature)
- ORCID (author information)
- Many other scholarly sources

### Data Volume

A full OpenAlex works snapshot contains:
- **250+ million** scholarly works
- **384 GB** compressed data
- Multiple URLs per work (primary, alternate, best_oa)

You can process the full dataset or filter to a subset based on your needs.

## System Requirements Overview

To run Local Unpaywall, you'll need:
- **Python 3.12+**
- **PostgreSQL 13+**
- **Disk space**: 500GB+ for full dataset (less with filtering)
- **RAM**: 4GB minimum, 8GB+ recommended

See [Installation](02-installation.md) for detailed requirements.

## Next Steps

Ready to get started? Continue to:

1. [Installation](02-installation.md) - Set up your system
2. [Configuration](03-configuration.md) - Configure database and environment
3. [Extracting URLs](04-extracting-urls.md) - Process OpenAlex data
