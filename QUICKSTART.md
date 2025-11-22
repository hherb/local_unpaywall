# Developer Quickstart Guide

Get up and running with Local Unpaywall in 5 minutes.

## Prerequisites

- Python 3.12+
- PostgreSQL 13+
- ~500GB disk space (for full OpenAlex snapshot)
- AWS CLI (for downloading OpenAlex data)

## Quick Setup

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/hherb/local_unpaywall.git
cd local_unpaywall

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (using uv - recommended)
uv sync

# Or using pip
pip install psycopg2-binary tqdm requests python-dotenv pytest
```

### 2. Configure Database

Create a `.env` file in the project root:

```bash
# .env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unpaywall
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

Create the database and schema:

```bash
# Create database
createdb unpaywall

# Create the schema (reads from .env)
python db/create_db.py
```

### 3. Download OpenAlex Data

```bash
# Download only the "works" section (~384GB compressed)
aws s3 sync "s3://openalex/data/works" "./openalex-snapshot/data/works" --no-sign-request

# Or download a smaller subset for testing
aws s3 sync "s3://openalex/data/works/updated_date=2024-01-01" \
    "./openalex-snapshot/data/works/updated_date=2024-01-01" --no-sign-request
```

### 4. Extract DOI-URL Pairs

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --format csv \
    --oa-only \
    --resume
```

### 5. Import to PostgreSQL

```bash
python doi_url_importer.py \
    --csv-file doi_urls.csv \
    --resume
```

### 6. Query Your Data

```sql
-- Find URLs for a DOI
SELECT url, pdf_url FROM unpaywall.doi_urls
WHERE doi = '10.1038/nature12373';

-- Count open access articles by year
SELECT publication_year, COUNT(*)
FROM unpaywall.doi_urls
WHERE is_oa = TRUE
GROUP BY publication_year
ORDER BY publication_year DESC;
```

## Common Development Tasks

### Run Tests

```bash
# All tests
pytest test/ -v

# Specific module
pytest test/test_file_tracker.py -v
```

### Download a PDF

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/"
```

### Check Processing Progress

```python
from helpers.file_tracker import FileTracker

tracker = FileTracker("doi_urls.tracking.db")
print(tracker.get_processing_summary())
```

## Project Structure Overview

```
local_unpaywall/
├── openalex_unpaywall_extractor.py  # Extract DOI-URLs from OpenAlex
├── doi_url_importer.py              # Import to PostgreSQL
├── pdf_fetcher.py                   # Download PDFs
├── helpers/
│   ├── file_tracker.py              # SQLite progress tracking
│   └── csv_utils.py                 # Memory-efficient CSV processing
├── db/
│   ├── create_db.py                 # Schema creation
│   ├── normalized_helpers.py        # Database utilities
│   └── migrations/                  # SQL migration scripts
└── test/                            # Test suite
```

## Next Steps

- Read [DEVELOPERS.md](DEVELOPERS.md) for the complete API reference
- See [NORMALIZED_DATABASE.md](NORMALIZED_DATABASE.md) for database schema details
- Check the `manual/` directory for detailed component documentation

## Getting Help

- GitHub Issues: Report bugs and request features
- Run `python <script>.py --help` for command-line options
- Check log files: `*.log` in project root
