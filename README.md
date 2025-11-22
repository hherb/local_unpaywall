# Local Unpaywall

A high-performance system for creating a local mirror of open access publication URLs from OpenAlex snapshots. Designed to handle massive datasets (250M+ records, 400GB+ compressed) with memory-efficient processing, resume capability, and robust error handling.

![Paywall Breaker Sketch](assets/paywallbreaker_sketch_small.png)

## Key Features

- **Scalable**: Process 250M+ DOI-URL records from OpenAlex snapshots
- **Memory-Efficient**: Generator-based processing with constant memory usage
- **Fault-Tolerant**: SHA-256 hash-based progress tracking enables safe resume
- **Storage-Optimized**: Normalized database schema saves 17-40GB on full dataset
- **Flexible**: Filter by year, OA status, work type; output to CSV/JSON/TSV

## Quick Start

```bash
# Install dependencies
pip install psycopg2-binary tqdm requests python-dotenv

# Configure database (.env file)
echo "POSTGRES_HOST=localhost
POSTGRES_DB=unpaywall
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypass" > .env

# Create database schema
python db/create_db.py

# Extract URLs from OpenAlex snapshot
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output urls.csv \
    --oa-only --resume

# Import to PostgreSQL
python doi_url_importer.py --csv-file urls.csv --resume

# Query your data
psql -d unpaywall -c "SELECT url FROM unpaywall.doi_urls WHERE doi = '10.1038/nature12373'"
```

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

## Architecture

```
OpenAlex Snapshot (384GB)
         │
         ▼
┌─────────────────────────────────┐
│ openalex_unpaywall_extractor.py │  ← Stream compressed JSONL
│ + FileTracker (SQLite)          │  ← Resume capability
└─────────────────────────────────┘
         │
         ▼
    CSV/JSON/TSV
         │
         ▼
┌─────────────────────────────────┐
│ doi_url_importer.py             │  ← Batch processing
│ + CSVBatchProcessor             │  ← Memory-efficient
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ PostgreSQL                      │
│ (Normalized Schema)             │  ← 17-40GB storage savings
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ pdf_fetcher.py                  │  ← Download full-text PDFs
└─────────────────────────────────┘
```

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Get started in 5 minutes |
| [DEVELOPERS.md](DEVELOPERS.md) | Complete API reference |
| [NORMALIZED_DATABASE.md](NORMALIZED_DATABASE.md) | Database schema details |

## Core Components

### 1. OpenAlex URL Extractor

Extracts DOI-URL pairs from OpenAlex snapshot files.

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir /path/to/openalex \
    --output urls.csv \
    --format csv \
    --oa-only \
    --year-from 2020 \
    --exclude-retracted \
    --resume
```

**Features**:
- Processes compressed JSONL directly (no decompression needed)
- Extracts multiple URLs per DOI with metadata
- SQLite-based progress tracking with hash verification
- Filters: year range, OA status, work type, retraction status

### 2. DOI-URL Importer

Imports extracted data into PostgreSQL with normalized schema.

```bash
python doi_url_importer.py \
    --csv-file urls.csv \
    --batch-size 25000 \
    --resume
```

**Features**:
- Batch processing with configurable batch sizes
- Lookup table caching for high-performance inserts
- Upsert handling (ON CONFLICT DO UPDATE)
- Resume from interruption with file integrity checking
- Supports `.env` file for database credentials

### 3. PDF Fetcher

Downloads PDFs with progress tracking and resume capability.

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/"
```

```python
from pdf_fetcher import PDFFetcher

fetcher = PDFFetcher()
success, msg = fetcher.download_pdf(url, "./pdfs/", "paper.pdf")
```

**Features**:
- HTTP range requests for resume
- PDF header validation
- Progress bars with tqdm

### 4. Helper Modules

#### File Tracker (`helpers/file_tracker.py`)

SQLite-based tracking for incremental processing.

```python
from helpers.file_tracker import FileTracker

tracker = FileTracker("progress.db")
if tracker.needs_processing("file.gz"):
    process_file("file.gz")
    tracker.mark_completed("file.gz", {'records': 50000})
```

#### CSV Utilities (`helpers/csv_utils.py`)

Memory-efficient batch processing for large CSV files.

```python
from helpers.csv_utils import process_csv_in_batches

for batch in process_csv_in_batches("large.csv", batch_size=10000):
    insert_batch(batch)
```

## Database Schema

The system uses a normalized PostgreSQL schema optimized for storage efficiency:

```sql
-- Main table (unpaywall.doi_urls)
CREATE TABLE unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,
    title TEXT,
    publication_year INTEGER,
    location_type CHAR(1) NOT NULL,  -- 'p', 'a', 'b'
    version TEXT,
    license_id INTEGER REFERENCES unpaywall.license(id),
    host_type_id INTEGER REFERENCES unpaywall.host_type(id),
    oa_status_id INTEGER REFERENCES unpaywall.oa_status(id),
    work_type_id INTEGER REFERENCES unpaywall.work_type(id),
    is_oa BOOLEAN DEFAULT FALSE,
    is_retracted BOOLEAN DEFAULT FALSE,
    url_quality_score INTEGER DEFAULT 50,
    UNIQUE(doi, url)
);

-- Lookup tables for storage efficiency
-- unpaywall.license, unpaywall.oa_status, unpaywall.host_type, unpaywall.work_type
```

**Storage Savings**: 70-160 bytes per row → 17-40GB for 250M records

See [NORMALIZED_DATABASE.md](NORMALIZED_DATABASE.md) for complete schema documentation.

## Example Queries

```sql
-- Find all URLs for a DOI
SELECT d.url, d.pdf_url, l.value AS license
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
WHERE d.doi = '10.1038/nature12373';

-- Count open access articles by status
SELECT o.value AS oa_status, COUNT(*) AS count
FROM unpaywall.doi_urls d
JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
WHERE d.is_oa = TRUE
GROUP BY o.value
ORDER BY count DESC;

-- Find CC-BY licensed articles from 2024
SELECT d.doi, d.url, d.title
FROM unpaywall.doi_urls d
JOIN unpaywall.license l ON d.license_id = l.id
WHERE l.value = 'cc-by' AND d.publication_year = 2024
LIMIT 100;
```

## Complete Workflow

### Step 1: Download OpenAlex Snapshot

```bash
# Works section only (~384GB compressed)
aws s3 sync "s3://openalex/data/works" "./openalex-snapshot/data/works" --no-sign-request
```

### Step 2: Configure Database

```bash
# Create .env file
cat > .env << EOF
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unpaywall
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypass
EOF

# Create database and schema
createdb unpaywall
python db/create_db.py
```

### Step 3: Extract and Import

```bash
# Extract DOI-URL pairs (with resume capability)
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --oa-only \
    --exclude-retracted \
    --resume

# Import to PostgreSQL (with resume capability)
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --batch-size 25000 \
    --resume
```

### Step 4: Download PDFs (Optional)

```python
from pdf_fetcher import PDFFetcher
import psycopg2

fetcher = PDFFetcher()
conn = psycopg2.connect("dbname=unpaywall")
cur = conn.cursor()

cur.execute("SELECT doi, pdf_url FROM unpaywall.doi_urls WHERE pdf_url IS NOT NULL LIMIT 100")
for doi, pdf_url in cur:
    filename = f"{doi.replace('/', '_')}.pdf"
    success, msg = fetcher.download_pdf(pdf_url, "./pdfs/", filename)
    print(f"{'OK' if success else 'FAIL'}: {doi}")
```

## Project Structure

```
local_unpaywall/
├── openalex_unpaywall_extractor.py  # Extract DOI-URLs from OpenAlex
├── doi_url_importer.py              # Import to PostgreSQL
├── pdf_fetcher.py                   # Download PDFs
├── normalize_database.py            # Database normalization script
│
├── helpers/
│   ├── __init__.py
│   ├── file_tracker.py              # SQLite progress tracking
│   └── csv_utils.py                 # Memory-efficient CSV processing
│
├── db/
│   ├── create_db.py                 # Schema creation
│   ├── normalized_helpers.py        # Database utilities
│   ├── run_migration.py             # Migration runner
│   └── migrations/                  # SQL migration scripts
│       ├── 001_add_work_type_and_is_retracted.sql
│       ├── 002_optimize_openalex_id_storage.sql
│       ├── 003_create_unpaywall_schema.sql
│       └── 004_normalize_database_storage.sql
│
├── test/                            # Test suite
│   ├── test_file_tracker.py
│   ├── test_csv_utils.py
│   ├── test_pdf_fetcher.py
│   ├── test_normalized_db.py
│   └── test_integration.py
│
├── QUICKSTART.md                    # Quick start guide
├── DEVELOPERS.md                    # Developer reference
├── NORMALIZED_DATABASE.md           # Schema documentation
└── pyproject.toml                   # Project configuration
```

## Dependencies

### Required

- **Python 3.12+**
- **psycopg2-binary**: PostgreSQL adapter
- **tqdm**: Progress bars
- **requests**: HTTP client
- **python-dotenv**: Environment file support

### Optional

- **pytest**: Testing framework
- **AWS CLI**: For downloading OpenAlex snapshots

### Installation

```bash
# Using uv (recommended)
uv sync

# Using pip
pip install psycopg2-binary tqdm requests python-dotenv

# Development dependencies
pip install pytest
```

## Performance Tips

### For Large Imports (100GB+)

```bash
# Use larger batch sizes
python doi_url_importer.py --batch-size 50000 --resume
```

```sql
-- PostgreSQL tuning
SET work_mem = '256MB';
ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = false);
-- Run import...
ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = true);
ANALYZE unpaywall.doi_urls;
```

### For Memory-Constrained Systems

```bash
# Use smaller batch sizes
python doi_url_importer.py --batch-size 5000

# Disable line counting for maximum speed
# (In Python: CSVBatchProcessor(..., enable_line_count=False))
```

## Testing

```bash
# Run all tests
pytest test/ -v

# Run specific tests
pytest test/test_file_tracker.py -v

# With coverage
pytest test/ --cov=. --cov-report=html
```

## Troubleshooting

### Memory Issues

```
Error: MemoryError during CSV processing
```
**Solution**: Reduce batch size with `--batch-size 5000`

### Database Connection Issues

```
Error: psycopg2.OperationalError: could not connect to server
```
**Solution**: Check `.env` file and database availability:
```bash
psql -h localhost -U myuser -d unpaywall -c "SELECT 1;"
```

### Interrupted Processing

```bash
# Check progress
python -c "from helpers.file_tracker import FileTracker; print(FileTracker('urls.tracking.db').get_processing_summary())"

# Resume from where you left off
python openalex_unpaywall_extractor.py --resume
python doi_url_importer.py --resume
```

### Corrupted Tracking Database

```bash
# Remove tracking file to restart
rm urls.tracking.db

# Re-run with resume (will reprocess all files)
python openalex_unpaywall_extractor.py --resume
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Follow PEP 8 style guidelines
5. Submit a pull request

See [DEVELOPERS.md](DEVELOPERS.md) for detailed contribution guidelines.

## License

This project is licensed under the MIT License.

## Acknowledgments

- **[OpenAlex](https://openalex.org/)**: Open scholarly metadata
- **[Unpaywall](https://unpaywall.org/)**: Inspiration for the project
- **PostgreSQL**: Robust database capabilities

---

**Note**: This system is designed for research and educational purposes. Please respect publisher terms of service and copyright when accessing full-text publications.
