# Downloading PDFs

This guide covers downloading full-text PDF articles using the PDF Fetcher utility.

## Overview

The PDF Fetcher:
- Downloads PDFs from URLs stored in your database
- Supports resume for interrupted downloads
- Validates downloaded files are actual PDFs
- Shows progress with download speed

## Basic Usage

### Download a Single PDF

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/"
```

### Download with Custom Filename

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" --filename "my_paper.pdf"
```

### Download with Options

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" \
    --filename "paper.pdf" \
    --chunk-size 16384 \
    --timeout 60 \
    --verbose
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `url` | URL of the PDF to download | Required |
| `output_dir` | Directory to save the PDF | Required |
| `--filename` | Custom filename | From URL |
| `--no-resume` | Disable resume capability | False |
| `--chunk-size` | Download chunk size (bytes) | 8192 |
| `--timeout` | Request timeout (seconds) | 30 |
| `--verbose` | Enable verbose output | False |

## Batch Downloading

### Using Python Script

Create a script to download multiple PDFs:

```python
#!/usr/bin/env python3
"""Download PDFs from database URLs."""

import psycopg2
from pdf_fetcher import PDFFetcher
import os

# Configuration
OUTPUT_DIR = "./pdfs"
LIMIT = 100  # Number of PDFs to download

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize fetcher
fetcher = PDFFetcher()

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="unpaywall",
    user="unpaywall_user",
    password="your_password"
)

cursor = conn.cursor()

# Query PDFs to download
cursor.execute("""
    SELECT doi, pdf_url
    FROM unpaywall.doi_urls
    WHERE pdf_url IS NOT NULL
    AND is_oa = TRUE
    LIMIT %s
""", (LIMIT,))

# Download each PDF
success_count = 0
fail_count = 0

for doi, pdf_url in cursor:
    # Create safe filename from DOI
    filename = doi.replace("/", "_").replace(":", "_") + ".pdf"

    # Download
    success, message = fetcher.download_pdf(pdf_url, OUTPUT_DIR, filename)

    if success:
        print(f"OK: {doi}")
        success_count += 1
    else:
        print(f"FAIL: {doi} - {message}")
        fail_count += 1

print(f"\nComplete: {success_count} downloaded, {fail_count} failed")

cursor.close()
conn.close()
```

### Download by Subject/Year

```python
# Query for specific criteria
cursor.execute("""
    SELECT d.doi, d.pdf_url
    FROM unpaywall.doi_urls d
    JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
    WHERE d.pdf_url IS NOT NULL
    AND o.value = 'gold'
    AND d.publication_year >= 2023
    LIMIT 500
""")
```

### Track Downloaded PDFs

Add a tracking table:

```sql
CREATE TABLE unpaywall.pdf_downloads (
    id SERIAL PRIMARY KEY,
    doi TEXT NOT NULL UNIQUE,
    pdf_url TEXT,
    file_path TEXT,
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_size BIGINT,
    success BOOLEAN
);
```

Update your download script:

```python
for doi, pdf_url in cursor:
    filename = doi.replace("/", "_") + ".pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    success, message = fetcher.download_pdf(pdf_url, OUTPUT_DIR, filename)

    # Record result
    cursor.execute("""
        INSERT INTO unpaywall.pdf_downloads (doi, pdf_url, file_path, success, file_size)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (doi) DO UPDATE SET
            success = EXCLUDED.success,
            downloaded_at = CURRENT_TIMESTAMP
    """, (
        doi, pdf_url, filepath if success else None,
        success,
        os.path.getsize(filepath) if success and os.path.exists(filepath) else None
    ))
    conn.commit()
```

## Using PDFFetcher in Python

### Basic Usage

```python
from pdf_fetcher import PDFFetcher

# Create fetcher with custom settings
fetcher = PDFFetcher(
    chunk_size=16384,  # 16KB chunks
    timeout=60,        # 60 second timeout
    user_agent="MyApp/1.0"
)

# Download a PDF
success, message = fetcher.download_pdf(
    url="https://example.com/paper.pdf",
    output_dir="./downloads/",
    filename="paper.pdf",
    resume=True
)

if success:
    print(f"Downloaded: {message}")
else:
    print(f"Error: {message}")
```

### Check File Size Before Download

```python
# Get file size without downloading
size = fetcher.get_file_size("https://example.com/paper.pdf")
if size:
    print(f"File size: {size / 1024 / 1024:.2f} MB")
else:
    print("Size unknown")
```

### Validate Existing PDF

```python
from pathlib import Path

# Check if file is a valid PDF
is_valid = fetcher.validate_pdf_content(Path("./paper.pdf"))
if is_valid:
    print("Valid PDF")
else:
    print("Not a valid PDF or corrupted")
```

## Handling Common Issues

### Rate Limiting

Many publishers rate-limit downloads. Add delays between requests:

```python
import time

for doi, pdf_url in cursor:
    success, message = fetcher.download_pdf(pdf_url, OUTPUT_DIR, filename)
    time.sleep(1)  # Wait 1 second between downloads
```

### Failed Downloads

Track and retry failed downloads:

```python
failed_downloads = []

for doi, pdf_url in cursor:
    success, message = fetcher.download_pdf(pdf_url, OUTPUT_DIR, filename)
    if not success:
        failed_downloads.append((doi, pdf_url, message))

# Retry failed downloads
print(f"\nRetrying {len(failed_downloads)} failed downloads...")
for doi, pdf_url, _ in failed_downloads:
    filename = doi.replace("/", "_") + ".pdf"
    success, message = fetcher.download_pdf(pdf_url, OUTPUT_DIR, filename)
    print(f"{'OK' if success else 'FAIL'}: {doi}")
```

### Handling Redirects

The PDF Fetcher automatically follows HTTP redirects. No special handling needed.

### Timeout Errors

Increase timeout for slow servers:

```python
fetcher = PDFFetcher(timeout=120)  # 2 minute timeout
```

## Organizing Downloaded PDFs

### By Year

```python
import os

for doi, pdf_url, year in cursor:
    # Create year subdirectory
    year_dir = os.path.join(OUTPUT_DIR, str(year))
    os.makedirs(year_dir, exist_ok=True)

    filename = doi.replace("/", "_") + ".pdf"
    fetcher.download_pdf(pdf_url, year_dir, filename)
```

### By Publisher

```python
for doi, pdf_url, host_type in cursor:
    # Create publisher subdirectory
    pub_dir = os.path.join(OUTPUT_DIR, host_type or "unknown")
    os.makedirs(pub_dir, exist_ok=True)

    filename = doi.replace("/", "_") + ".pdf"
    fetcher.download_pdf(pdf_url, pub_dir, filename)
```

## Disk Space Management

### Estimate Space Requirements

```sql
-- Count PDFs to download
SELECT COUNT(*) FROM unpaywall.doi_urls WHERE pdf_url IS NOT NULL;

-- Average PDF size is ~2-5 MB
-- For 1 million PDFs: 2-5 TB of storage needed
```

### Monitor Disk Usage

```bash
# Check disk space
df -h

# Check download directory size
du -sh ./pdfs/

# Count downloaded files
find ./pdfs/ -name "*.pdf" | wc -l
```

### Compress Old PDFs

```bash
# Compress PDFs older than 30 days
find ./pdfs/ -name "*.pdf" -mtime +30 -exec gzip {} \;
```

## Performance Tips

### Parallel Downloads

For faster downloads, use multiple processes:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def download_one(args):
    doi, pdf_url = args
    filename = doi.replace("/", "_") + ".pdf"
    fetcher = PDFFetcher()
    return fetcher.download_pdf(pdf_url, OUTPUT_DIR, filename)

# Download with 4 parallel workers
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(download_one, (doi, url)): doi
               for doi, url in url_list}

    for future in as_completed(futures):
        doi = futures[future]
        success, message = future.result()
        print(f"{'OK' if success else 'FAIL'}: {doi}")
```

> **Warning**: Be respectful of server resources. Too many parallel connections may result in IP blocks.

### Resume Interrupted Batch Downloads

Track progress in database:

```python
# Query only undownloaded PDFs
cursor.execute("""
    SELECT d.doi, d.pdf_url
    FROM unpaywall.doi_urls d
    LEFT JOIN unpaywall.pdf_downloads p ON d.doi = p.doi
    WHERE d.pdf_url IS NOT NULL
    AND (p.success IS NULL OR p.success = FALSE)
    LIMIT 1000
""")
```

## Next Steps

- [Querying Data](07-querying-data.md) - Find URLs and PDFs in your database
- [Maintenance](08-maintenance.md) - Keep your PDF collection organized
