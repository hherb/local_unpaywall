# PDF Fetcher Utility

## Overview

The PDF Fetcher (`pdf_fetcher.py`) is a utility script for downloading PDF files from URLs with progress tracking and robust error handling. It provides a clean command-line interface and can also be used as a Python module.

## Features

- **Progress Tracking**: Real-time download progress with tqdm progress bars
- **Resume Capability**: Automatically resumes interrupted downloads using HTTP range requests
- **PDF Validation**: Validates that downloaded content is actually a PDF file
- **Flexible Naming**: Supports custom filenames or automatic extraction from URLs
- **Robust Error Handling**: Comprehensive error handling for network issues, file I/O, and validation
- **Configurable**: Customizable chunk size, timeout, and user agent settings

## Installation

The PDF fetcher requires the `requests` library, which is included in the project dependencies:

```bash
uv add requests  # Already included in pyproject.toml
```

## Command Line Usage

### Basic Syntax

```bash
python pdf_fetcher.py <url> <output_dir> [options]
```

### Examples

```bash
# Download with original filename
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/"

# Download with custom filename
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" --filename "my_paper.pdf"

# Download without resume capability
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" --no-resume

# Download with custom settings
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" \
    --chunk-size 16384 \
    --timeout 60 \
    --verbose
```

### Command Line Options

- `url`: URL of the PDF to download (required)
- `output_dir`: Directory to save the PDF (required)
- `--filename`: Custom filename for the downloaded PDF
- `--no-resume`: Disable resume capability for interrupted downloads
- `--chunk-size`: Download chunk size in bytes (default: 8192)
- `--timeout`: Request timeout in seconds (default: 30)
- `--verbose, -v`: Enable verbose logging

## Python Module Usage

### Basic Usage

```python
from pdf_fetcher import PDFFetcher

# Create fetcher instance
fetcher = PDFFetcher()

# Download a PDF
success, message = fetcher.download_pdf(
    url="https://example.com/paper.pdf",
    output_dir="./downloads/",
    filename="my_paper.pdf"  # Optional
)

if success:
    print(f"Success: {message}")
else:
    print(f"Error: {message}")
```

### Advanced Configuration

```python
from pdf_fetcher import PDFFetcher

# Create fetcher with custom settings
fetcher = PDFFetcher(
    chunk_size=16384,           # Larger chunks for faster downloads
    timeout=60,                 # Longer timeout for slow connections
    user_agent="MyApp/1.0"      # Custom user agent
)

# Download with resume disabled
success, message = fetcher.download_pdf(
    url="https://example.com/paper.pdf",
    output_dir="./downloads/",
    resume=False
)
```

### Utility Methods

```python
from pdf_fetcher import PDFFetcher
from pathlib import Path

fetcher = PDFFetcher()

# Extract filename from URL
filename = fetcher.extract_filename_from_url("https://example.com/research.pdf")
print(filename)  # "research.pdf"

# Get file size without downloading
size = fetcher.get_file_size("https://example.com/paper.pdf")
print(f"File size: {size} bytes")

# Validate PDF content
is_valid = fetcher.validate_pdf_content(Path("downloaded.pdf"))
print(f"Valid PDF: {is_valid}")
```

## Implementation Details

### Resume Capability

The PDF fetcher supports resuming interrupted downloads using HTTP range requests:

1. **Existing File Check**: If a file already exists, checks its size
2. **Range Request**: Sends `Range: bytes=<existing_size>-` header
3. **Server Support**: Falls back to full download if server doesn't support ranges
4. **Validation**: Validates the complete file after resume

### PDF Validation

Downloaded files are validated to ensure they are actual PDF files:

- Checks for PDF header (`%PDF-`) at the beginning of the file
- Deletes invalid files to prevent confusion
- Returns appropriate error messages for validation failures

### Error Handling

Comprehensive error handling covers:

- **Network Errors**: Connection timeouts, DNS failures, HTTP errors
- **File I/O Errors**: Permission issues, disk space, invalid paths
- **Validation Errors**: Invalid PDF content, corrupted downloads
- **URL Errors**: Malformed URLs, empty URLs

### Progress Tracking

Uses tqdm for progress indication:

- Shows download speed and ETA
- Displays file size in human-readable format
- Supports resume progress (shows initial progress for resumed downloads)
- Clean progress bar formatting

## Testing

Run the unit tests to verify functionality:

```bash
# Run PDF fetcher tests
python -m pytest test/test_pdf_fetcher.py -v

# Run all tests
python test/run_all_tests.py
```

### Test Coverage

The test suite covers:

- Filename extraction from various URL formats
- PDF content validation (valid/invalid/missing files)
- File size retrieval with different server responses
- Download success and error scenarios
- Custom filename handling
- Network error simulation

## Integration with Project

The PDF fetcher follows the project's coding standards:

- **Type Hints**: Full type annotations for all functions
- **Documentation**: Comprehensive docstrings and comments
- **Error Handling**: Consistent error handling patterns
- **Logging**: Uses the project's logging configuration
- **Testing**: Unit tests in the `test/` directory
- **Dependencies**: Managed through `pyproject.toml`

## Common Use Cases

### Batch PDF Downloads

```python
from pdf_fetcher import PDFFetcher
import csv

fetcher = PDFFetcher()
urls_file = "pdf_urls.csv"
output_dir = "./downloaded_pdfs/"

with open(urls_file, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        url = row['pdf_url']
        filename = row.get('filename')  # Optional custom filename
        
        success, message = fetcher.download_pdf(url, output_dir, filename)
        if success:
            print(f"✓ Downloaded: {filename or url}")
        else:
            print(f"✗ Failed: {url} - {message}")
```

### Integration with Database

```python
from pdf_fetcher import PDFFetcher
import sqlite3

fetcher = PDFFetcher()

# Get URLs from database
conn = sqlite3.connect("papers.db")
cursor = conn.execute("SELECT doi, pdf_url FROM papers WHERE pdf_downloaded = 0")

for doi, pdf_url in cursor:
    filename = f"{doi.replace('/', '_')}.pdf"
    success, message = fetcher.download_pdf(pdf_url, "./pdfs/", filename)
    
    if success:
        # Mark as downloaded in database
        conn.execute("UPDATE papers SET pdf_downloaded = 1 WHERE doi = ?", (doi,))
        conn.commit()
        print(f"✓ Downloaded: {doi}")
    else:
        print(f"✗ Failed: {doi} - {message}")

conn.close()
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure write permissions for output directory
2. **Network Timeouts**: Increase timeout value for slow connections
3. **Invalid PDF**: Some servers return HTML error pages instead of PDFs
4. **Resume Failures**: Some servers don't support range requests

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" --verbose
```

Or in Python:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```
