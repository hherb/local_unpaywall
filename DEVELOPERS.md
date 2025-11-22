# Developer Reference Manual

Complete API reference and architecture documentation for Local Unpaywall.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Modules](#core-modules)
   - [OpenAlex URL Extractor](#openalex-url-extractor)
   - [DOI-URL Importer](#doi-url-importer)
   - [PDF Fetcher](#pdf-fetcher)
3. [Helper Modules](#helper-modules)
   - [File Tracker](#file-tracker)
   - [CSV Utilities](#csv-utilities)
4. [Database Module](#database-module)
   - [Database Creator](#database-creator)
   - [Normalized Helpers](#normalized-helpers)
5. [Database Schema](#database-schema)
6. [Configuration](#configuration)
7. [Testing](#testing)
8. [Performance Optimization](#performance-optimization)

---

## Architecture Overview

Local Unpaywall is designed as a data pipeline for processing large-scale academic publication metadata from OpenAlex snapshots. The system follows a modular architecture optimized for memory efficiency and fault tolerance.

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ OpenAlex Snapshot (Gzip-compressed JSONL files)             │
│ ~384GB compressed, containing 250M+ works                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ openalex_unpaywall_extractor.py                             │
│ ├── Streams compressed JSONL without full decompression    │
│ ├── Applies filters (year, OA status, work type)           │
│ ├── Tracks progress via SQLite (FileTracker)               │
│ └── Outputs CSV/JSON/TSV                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ doi_url_importer.py                                         │
│ ├── Memory-efficient batch processing (CSVBatchProcessor)  │
│ ├── Lookup table caching for foreign keys                  │
│ ├── Bulk inserts with upsert (ON CONFLICT)                 │
│ └── Resume capability with integrity checking               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL (unpaywall schema)                               │
│ ├── Normalized structure with lookup tables                │
│ ├── Optimized indexes for DOI/URL lookups                  │
│ └── 17-40GB storage savings through normalization           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ pdf_fetcher.py                                              │
│ ├── Downloads PDFs with resume capability                  │
│ ├── HTTP range request support                              │
│ └── PDF content validation                                  │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Memory Efficiency**: Generator-based processing ensures constant memory usage regardless of input size
2. **Fault Tolerance**: SHA-256 hash-based progress tracking enables safe resume after interruptions
3. **Storage Optimization**: Normalized database schema reduces storage by 70-160 bytes per row
4. **Modularity**: Each component can be used independently or as part of the pipeline

---

## Core Modules

### OpenAlex URL Extractor

**File**: `openalex_unpaywall_extractor.py`

Extracts DOI and full-text URL pairs from OpenAlex snapshot data.

#### Class: `OpenAlexURLExtractor`

```python
from openalex_unpaywall_extractor import OpenAlexURLExtractor

extractor = OpenAlexURLExtractor(
    snapshot_dir="/path/to/openalex",
    output_file="urls.csv",
    output_format="csv",  # 'csv', 'json', or 'tsv'
    resume=True
)
```

##### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_dir` | `str` | required | Path to OpenAlex snapshot directory |
| `output_file` | `str` | required | Path for output file |
| `output_format` | `str` | `'csv'` | Output format: 'csv', 'json', or 'tsv' |
| `resume` | `bool` | `False` | Resume from previous incomplete run |

##### Methods

###### `extract_urls(filters: Dict, max_workers: int = 1) -> None`

Main method to extract URLs from all snapshot files.

```python
extractor.extract_urls(
    filters={
        'oa_only': True,           # Only open access works
        'year_from': 2020,         # Publication year >= 2020
        'year_to': 2024,           # Publication year <= 2024
        'types': ['journal-article', 'book-chapter'],  # Work types
        'exclude_retracted': True  # Exclude retracted works
    },
    max_workers=1  # Sequential processing recommended
)
```

**Filter Options**:
- `oa_only` (bool): Only include open access works
- `year_from` (int): Minimum publication year
- `year_to` (int): Maximum publication year
- `types` (List[str]): Work types to include (e.g., 'journal-article', 'preprint')
- `exclude_retracted` (bool): Exclude retracted works

###### `extract_urls_from_work(work: Dict, filters: Dict) -> List[Dict]`

Extract URL records from a single OpenAlex work object.

```python
records = extractor.extract_urls_from_work(work_data, filters)
# Returns list of dicts with: doi, url, pdf_url, title, etc.
```

##### Output Schema

The extractor produces records with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `doi` | string | DOI identifier (e.g., "10.1038/nature12373") |
| `openalex_id` | string | OpenAlex work ID (e.g., "W2123456789") |
| `title` | string | Publication title |
| `publication_year` | int | Year of publication |
| `url` | string | Full-text URL |
| `pdf_url` | string | Direct PDF URL (if available) |
| `location_type` | string | Source type (primary, alternate, best_oa) |
| `version` | string | Version (publishedVersion, acceptedVersion, etc.) |
| `license` | string | License identifier (cc-by, cc0, etc.) |
| `host_type` | string | Host type (publisher, repository) |
| `oa_status` | string | Open access status (gold, green, closed) |
| `is_oa` | bool | Whether the work is open access |
| `work_type` | string | Work type (journal-article, book-chapter) |
| `is_retracted` | bool | Whether the work is retracted |

##### Command-Line Usage

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir /path/to/openalex \
    --output urls.csv \
    --format csv \
    --oa-only \
    --year-from 2020 \
    --year-to 2024 \
    --types journal-article book-chapter \
    --exclude-retracted \
    --resume
```

---

### DOI-URL Importer

**File**: `doi_url_importer.py`

Imports extracted CSV data into PostgreSQL with normalized schema support.

#### Class: `DOIURLImporter`

```python
from doi_url_importer import DOIURLImporter

db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'unpaywall',
    'user': 'myuser',
    'password': 'mypass'
}

importer = DOIURLImporter(
    db_config=db_config,
    csv_file="urls.csv",
    batch_size=25000,
    create_tables=True,
    resume=True
)
```

##### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db_config` | `Dict` | required | Database connection parameters |
| `csv_file` | `str` | required | Path to input CSV file |
| `batch_size` | `int` | `10000` | Rows per batch (25000 recommended) |
| `create_tables` | `bool` | `True` | Create tables if missing |
| `resume` | `bool` | `False` | Resume interrupted import |

##### Methods

###### `import_from_csv() -> Dict[str, int]`

Main import method. Returns statistics dictionary.

```python
stats = importer.import_from_csv()
# Returns: {'rows_imported': 1000000, 'rows_skipped': 50, ...}
```

###### `preload_lookup_caches() -> None`

Pre-load all lookup table values into memory for faster inserts.

```python
importer.preload_lookup_caches()
```

###### `disable_indexes_for_bulk_import() -> None`

Drop non-essential indexes before bulk import for better performance.

```python
importer.disable_indexes_for_bulk_import()
```

###### `enable_indexes_after_bulk_import() -> None`

Recreate indexes after bulk import completes.

```python
importer.enable_indexes_after_bulk_import()
```

###### `get_or_create_lookup_id(table_name: str, value: str) -> Optional[int]`

Get or create a lookup table entry, returning the ID.

```python
license_id = importer.get_or_create_lookup_id('license', 'cc-by')
```

##### Configuration via .env

The importer supports `.env` file configuration:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unpaywall
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypass
```

##### Command-Line Usage

```bash
# With .env file (credentials optional)
python doi_url_importer.py --csv-file urls.csv --resume

# With explicit credentials
python doi_url_importer.py \
    --csv-file urls.csv \
    --db-host localhost \
    --db-name unpaywall \
    --db-user myuser \
    --db-password mypass \
    --batch-size 25000 \
    --resume
```

---

### PDF Fetcher

**File**: `pdf_fetcher.py`

Downloads PDF files with progress tracking and resume capability.

#### Class: `PDFFetcher`

```python
from pdf_fetcher import PDFFetcher

fetcher = PDFFetcher(
    chunk_size=8192,    # Download chunk size in bytes
    timeout=30,         # Request timeout in seconds
    user_agent="PDF-Fetcher/1.0"
)
```

##### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk_size` | `int` | `8192` | Download chunk size in bytes |
| `timeout` | `int` | `30` | HTTP request timeout in seconds |
| `user_agent` | `str` | `"PDF-Fetcher/1.0"` | User-Agent header value |

##### Methods

###### `download_pdf(url: str, output_dir: str, filename: str = None, resume: bool = True) -> Tuple[bool, str]`

Download a PDF file.

```python
success, message = fetcher.download_pdf(
    url="https://example.com/paper.pdf",
    output_dir="./downloads/",
    filename="my_paper.pdf",  # Optional, extracted from URL if not provided
    resume=True               # Resume partial downloads
)

if success:
    print(f"Downloaded: {message}")
else:
    print(f"Error: {message}")
```

###### `validate_pdf_content(file_path: Path) -> bool`

Check if a file is a valid PDF by examining its header.

```python
is_valid = fetcher.validate_pdf_content(Path("./paper.pdf"))
```

###### `get_file_size(url: str) -> Optional[int]`

Get file size from HTTP headers without downloading.

```python
size = fetcher.get_file_size("https://example.com/paper.pdf")
# Returns size in bytes, or None if unavailable
```

###### `extract_filename_from_url(url: str) -> str`

Extract filename from URL.

```python
filename = fetcher.extract_filename_from_url("https://example.com/paper.pdf")
# Returns: "paper.pdf"
```

##### Batch Download Example

```python
from pdf_fetcher import PDFFetcher
import psycopg2

fetcher = PDFFetcher()
conn = psycopg2.connect("dbname=unpaywall user=myuser")
cursor = conn.cursor()

cursor.execute("""
    SELECT doi, pdf_url FROM unpaywall.doi_urls
    WHERE pdf_url IS NOT NULL
    LIMIT 100
""")

for doi, pdf_url in cursor:
    filename = f"{doi.replace('/', '_')}.pdf"
    success, message = fetcher.download_pdf(pdf_url, "./pdfs/", filename)
    print(f"{'OK' if success else 'FAIL'}: {doi}")

conn.close()
```

##### Command-Line Usage

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" \
    --filename "my_paper.pdf" \
    --chunk-size 16384 \
    --timeout 60 \
    --verbose
```

---

## Helper Modules

### File Tracker

**File**: `helpers/file_tracker.py`

SQLite-based file tracking system for incremental processing.

#### Class: `FileTracker`

```python
from helpers.file_tracker import FileTracker

tracker = FileTracker("processing_progress.db")
```

##### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db_path` | `str` | `"file_tracking.db"` | Path to SQLite database file |

##### Methods

###### `needs_processing(file_path: str) -> bool`

Check if a file needs processing based on hash comparison.

```python
if tracker.needs_processing("/data/file.gz"):
    # Process the file
    process_file("/data/file.gz")
```

###### `mark_completed(file_path: str, processing_stats: Dict = None) -> None`

Mark a file as completed with optional statistics.

```python
tracker.mark_completed("/data/file.gz", {
    'records_extracted': 50000,
    'processing_time_seconds': 120
})
```

###### `get_processed_files() -> List[Dict]`

Get list of all processed files with metadata.

```python
files = tracker.get_processed_files()
for f in files:
    print(f"{f['file_path']}: {f['completion_date']}")
```

###### `get_processing_summary() -> Dict`

Get summary statistics.

```python
summary = tracker.get_processing_summary()
# Returns:
# {
#     'total_files': 100,
#     'total_size_bytes': 5368709120,
#     'total_size_mb': 5120.0,
#     'first_processed': '2024-01-15T10:30:00',
#     'last_processed': '2024-01-15T14:45:00'
# }
```

###### `remove_file_record(file_path: str) -> bool`

Remove a file from tracking (to force reprocessing).

```python
tracker.remove_file_record("/data/file.gz")
```

###### `cleanup_missing_files() -> int`

Remove records for files that no longer exist on disk.

```python
removed_count = tracker.cleanup_missing_files()
```

##### How It Works

1. Calculates SHA-256 hash of each file
2. Stores hash, size, and timestamps in SQLite
3. On subsequent runs, compares current hash to stored hash
4. Only processes files that are new or changed

---

### CSV Utilities

**File**: `helpers/csv_utils.py`

Memory-efficient CSV processing using generators.

#### Function: `count_lines_fast`

Fast line counting using buffered reads.

```python
from helpers.csv_utils import count_lines_fast

line_count = count_lines_fast("large_file.csv", show_progress=True)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | required | Path to file |
| `show_progress` | `bool` | `True` | Show progress bar for files >10MB |

#### Class: `CSVBatchProcessor`

Memory-efficient CSV batch processor.

```python
from helpers.csv_utils import CSVBatchProcessor

processor = CSVBatchProcessor(
    csv_file="large_file.csv",
    batch_size=10000,
    validator=my_validator_func,  # Optional
    show_progress=True,
    encoding='utf-8',
    enable_line_count=True
)

for batch in processor.process_batches():
    # Each batch is a list of dictionaries
    for row in batch:
        process_row(row)
```

##### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `csv_file` | `str` | required | Path to CSV file |
| `batch_size` | `int` | `10000` | Rows per batch |
| `validator` | `Callable` | `None` | Row validation/transform function |
| `show_progress` | `bool` | `True` | Show progress bar |
| `encoding` | `str` | `'utf-8'` | File encoding |
| `enable_line_count` | `bool` | `True` | Count lines for progress (disable for max speed) |

##### Validator Function

The validator receives a row dict and should return:
- Transformed dict to include the row
- `None` to skip the row

```python
def my_validator(row):
    """Validate and transform a row."""
    if not row.get('doi'):
        return None  # Skip rows without DOI

    return {
        'doi': row['doi'].lower(),
        'url': row['url'].strip(),
        'year': int(row.get('publication_year', 0))
    }
```

##### Methods

###### `process_batches() -> Generator[List[Dict], None, None]`

Generator that yields batches of CSV rows.

```python
for batch in processor.process_batches():
    insert_batch_to_database(batch)
```

###### `get_stats() -> Dict[str, int]`

Get processing statistics.

```python
stats = processor.get_stats()
# Returns:
# {
#     'total_rows_processed': 1000000,
#     'rows_valid': 999500,
#     'rows_skipped': 500,
#     'batches_yielded': 100
# }
```

#### Function: `process_csv_in_batches`

Convenience function wrapping `CSVBatchProcessor`.

```python
from helpers.csv_utils import process_csv_in_batches

for batch in process_csv_in_batches("data.csv", batch_size=5000):
    process_batch(batch)
```

---

## Database Module

### Database Creator

**File**: `db/create_db.py`

Schema creation and management.

#### Class: `DatabaseCreator`

```python
from db.create_db import DatabaseCreator

# With explicit credentials
creator = DatabaseCreator(
    host='localhost',
    database='unpaywall',
    user='myuser',
    password='mypass',
    port=5432
)

# Or using .env file
creator = DatabaseCreator.from_env_or_args()
```

##### Methods

###### `create_complete_schema() -> None`

Create all tables, indexes, and constraints.

```python
creator.create_complete_schema()
```

###### `create_unpaywall_schema() -> None`

Create the `unpaywall` namespace.

```python
creator.create_unpaywall_schema()
```

###### `create_lookup_tables() -> None`

Create lookup tables (license, oa_status, host_type, work_type).

```python
creator.create_lookup_tables()
```

###### `create_doi_urls_table() -> None`

Create the main `doi_urls` table.

```python
creator.create_doi_urls_table()
```

###### `create_indexes() -> None`

Create all performance indexes.

```python
creator.create_indexes()
```

###### `test_connection() -> bool`

Test database connectivity.

```python
if creator.test_connection():
    print("Connected successfully")
```

##### Command-Line Usage

```bash
# Using .env file
python db/create_db.py

# With explicit credentials
python db/create_db.py \
    --db-host localhost \
    --db-name unpaywall \
    --db-user myuser \
    --db-password mypass
```

---

### Normalized Helpers

**File**: `db/normalized_helpers.py`

Utilities for working with the normalized database structure.

#### Class: `NormalizedHelper`

```python
from db.normalized_helpers import NormalizedHelper

helper = NormalizedHelper(db_config)
```

##### Methods

###### `normalize_location_type(location_type: str) -> str`

Convert location type text to CHAR(1).

```python
char = helper.normalize_location_type('primary')   # Returns 'p'
char = helper.normalize_location_type('alternate') # Returns 'a'
char = helper.normalize_location_type('best_oa')   # Returns 'b'
```

###### `denormalize_location_type(location_char: str) -> str`

Convert CHAR(1) back to text.

```python
text = helper.denormalize_location_type('p')  # Returns 'primary'
```

###### `get_or_create_lookup_id(table_name: str, value: str) -> Optional[int]`

Get or create lookup table entry.

```python
license_id = helper.get_or_create_lookup_id('license', 'cc-by')
oa_status_id = helper.get_or_create_lookup_id('oa_status', 'gold')
```

###### `get_lookup_value(table_name: str, lookup_id: int) -> Optional[str]`

Get text value from lookup ID.

```python
license_text = helper.get_lookup_value('license', 5)  # Returns 'cc-by'
```

###### `insert_doi_url_record(record_data: Dict) -> bool`

Insert a complete record with automatic normalization.

```python
success = helper.insert_doi_url_record({
    'doi': '10.1234/example',
    'url': 'https://example.com/paper',
    'pdf_url': 'https://example.com/paper.pdf',
    'title': 'My Paper',
    'publication_year': 2024,
    'license': 'cc-by',        # Text value, auto-converted to ID
    'oa_status': 'gold',       # Text value, auto-converted to ID
    'host_type': 'journal',    # Text value, auto-converted to ID
    'work_type': 'journal-article',
    'location_type': 'primary', # Auto-converted to 'p'
    'is_oa': True
})
```

###### `clear_cache() -> None`

Clear the lookup value cache.

```python
helper.clear_cache()
```

###### `get_cache_stats() -> Dict[str, int]`

Get cache statistics.

```python
stats = helper.get_cache_stats()
# Returns: {'total_entries': 50, 'license_entries': 10, ...}
```

#### Dataclass: `DOIURLRecord`

Typed container for DOI-URL records.

```python
from db.normalized_helpers import DOIURLRecord

record = DOIURLRecord(
    doi='10.1234/example',
    url='https://example.com/paper',
    pdf_url='https://example.com/paper.pdf',
    title='My Paper',
    publication_year=2024,
    location_type='p',
    license='cc-by',
    oa_status='gold',
    is_oa=True
)
```

---

## Database Schema

### Normalized Structure

The database uses a normalized structure for storage efficiency:

```sql
-- Main table
CREATE TABLE unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,              -- Numeric part only
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
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(doi, url)
);

-- Lookup tables
CREATE TABLE unpaywall.license (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL
);

CREATE TABLE unpaywall.oa_status (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL
);

CREATE TABLE unpaywall.host_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL
);

CREATE TABLE unpaywall.work_type (
    id SERIAL PRIMARY KEY,
    value TEXT UNIQUE NOT NULL
);
```

### Location Type Mapping

| Character | Meaning |
|-----------|---------|
| `p` | primary |
| `a` | alternate |
| `b` | best_oa |

### Storage Savings

- **Per row**: 70-160 bytes saved through normalization
- **For 250M rows**: 17-40 GB total storage reduction

### Indexes

```sql
CREATE INDEX idx_unpaywall_doi_urls_doi ON unpaywall.doi_urls(doi);
CREATE INDEX idx_unpaywall_doi_urls_url ON unpaywall.doi_urls(url);
CREATE INDEX idx_unpaywall_doi_urls_pdf_url ON unpaywall.doi_urls(pdf_url) WHERE pdf_url IS NOT NULL;
CREATE INDEX idx_unpaywall_doi_urls_openalex_work_id ON unpaywall.doi_urls(openalex_id);
CREATE INDEX idx_unpaywall_doi_urls_is_oa ON unpaywall.doi_urls(is_oa) WHERE is_oa = TRUE;
```

### Common Queries

```sql
-- Find all URLs for a DOI
SELECT d.doi, d.url, d.pdf_url, l.value AS license
FROM unpaywall.doi_urls d
LEFT JOIN unpaywall.license l ON d.license_id = l.id
WHERE d.doi = '10.1038/nature12373';

-- Count by OA status
SELECT o.value AS oa_status, COUNT(*) AS count
FROM unpaywall.doi_urls d
JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
GROUP BY o.value
ORDER BY count DESC;

-- Find gold OA articles from 2024
SELECT d.doi, d.url, w.value AS work_type
FROM unpaywall.doi_urls d
JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id
WHERE o.value = 'gold' AND d.publication_year = 2024;
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unpaywall
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypass

# Optional: Processing settings
BATCH_SIZE=25000
LOG_LEVEL=INFO
```

### pyproject.toml

```toml
[project]
name = "local_unpaywall"
requires-python = ">=3.12"
dependencies = [
    "psycopg2-binary>=2.9.10",
    "tqdm>=4.64.0",
    "requests>=2.28.0",
    "python-dotenv>=0.9.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.4.0",
]
```

### Logging

All modules use Python's logging module:

```python
import logging

# Set log level
logging.getLogger('local_unpaywall').setLevel(logging.DEBUG)

# Log files are created in the project root:
# - openalex_url_extraction.log
# - doi_url_import.log
```

---

## Testing

### Running Tests

```bash
# All tests
pytest test/ -v

# Specific test file
pytest test/test_file_tracker.py -v

# With coverage
pytest test/ --cov=. --cov-report=html
```

### Test Structure

```
test/
├── test_file_tracker.py      # FileTracker unit tests
├── test_csv_utils.py         # CSV processing tests
├── test_pdf_fetcher.py       # PDF download tests
├── test_normalized_db.py     # Database normalization tests
├── test_normalized_importer.py
├── test_integration.py       # End-to-end workflow tests
└── test_performance_optimizations.py
```

### Writing Tests

```python
import pytest
from helpers.file_tracker import FileTracker

def test_needs_processing_new_file(tmp_path):
    """Test that new files need processing."""
    db_path = tmp_path / "test.db"
    tracker = FileTracker(str(db_path))

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    assert tracker.needs_processing(str(test_file)) is True

def test_mark_completed(tmp_path):
    """Test marking files as completed."""
    db_path = tmp_path / "test.db"
    tracker = FileTracker(str(db_path))

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    tracker.mark_completed(str(test_file), {'records': 100})

    assert tracker.needs_processing(str(test_file)) is False
```

---

## Performance Optimization

### Bulk Import Best Practices

1. **Increase batch size**: Use 25,000-50,000 rows per batch
2. **Disable indexes**: Drop non-essential indexes during import
3. **Pre-load lookups**: Cache all lookup table values before import
4. **Use .env file**: Avoid passing credentials on command line

```bash
python doi_url_importer.py \
    --csv-file urls.csv \
    --batch-size 50000 \
    --resume
```

### PostgreSQL Tuning

```sql
-- Increase work memory for large imports
SET work_mem = '256MB';

-- Temporarily disable autovacuum
ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = false);

-- Run import...

-- Re-enable and analyze
ALTER TABLE unpaywall.doi_urls SET (autovacuum_enabled = true);
ANALYZE unpaywall.doi_urls;
```

### Memory Optimization

- Use `enable_line_count=False` in CSVBatchProcessor for max speed
- Process files sequentially (avoid parallel writes)
- Use generators throughout the pipeline

### Monitoring

```python
from helpers.file_tracker import FileTracker

tracker = FileTracker("progress.tracking.db")
summary = tracker.get_processing_summary()

print(f"Files processed: {summary['total_files']}")
print(f"Data processed: {summary['total_size_mb']:.2f} MB")
print(f"Last update: {summary['last_processed']}")
```

---

## Migrations

SQL migrations are in `db/migrations/`:

| File | Purpose |
|------|---------|
| `001_add_work_type_and_is_retracted.sql` | Add work type and retraction fields |
| `002_optimize_openalex_id_storage.sql` | Optimize OpenAlex ID to numeric |
| `003_create_unpaywall_schema.sql` | Create unpaywall namespace |
| `004_normalize_database_storage.sql` | Add lookup tables and foreign keys |

Run migrations:

```bash
python db/run_migration.py
```

---

## Error Handling

All modules use consistent error handling patterns:

```python
try:
    result = operation()
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
except psycopg2.Error as e:
    logger.error(f"Database error: {e}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `MemoryError` | Batch size too large | Reduce `--batch-size` |
| `psycopg2.OperationalError` | DB connection failed | Check credentials and `.env` |
| `FileNotFoundError` | Input file missing | Verify file path |
| `csv.Error` | Malformed CSV | Check CSV format and encoding |

---

## Contributing

### Code Style

- Follow PEP 8
- Use type hints for all functions
- Add docstrings (Google style)
- Write tests for new features

### Pull Request Process

1. Create feature branch from `main`
2. Write tests
3. Update documentation
4. Run full test suite
5. Submit PR with description

### Documentation

- Update `DEVELOPERS.md` for API changes
- Update `README.md` for user-facing changes
- Add module docs in `manual/` for new components
