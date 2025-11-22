# Extracting URLs from OpenAlex

This guide covers downloading OpenAlex data and extracting DOI-URL pairs.

## Overview

The extraction process:
1. Download OpenAlex snapshot data from AWS S3
2. Run the extractor to process compressed JSONL files
3. Output DOI-URL pairs to CSV (or JSON/TSV)

## Step 1: Download OpenAlex Data

### Understanding OpenAlex Data

OpenAlex provides free snapshots of their entire database on AWS S3. The "works" dataset contains information about scholarly publications including:
- DOIs and metadata
- Open access locations (URLs)
- Author information
- Citations

### Download Options

#### Option A: Full Works Dataset (~384 GB)
```bash
aws s3 sync "s3://openalex/data/works" "./openalex-snapshot/data/works" --no-sign-request
```

> **Note**: This download takes several hours depending on your internet speed.

#### Option B: Recent Data Only (Faster)
Download only recent updates:
```bash
# Last month's data only
aws s3 sync "s3://openalex/data/works/updated_date=2024-11-01" \
    "./openalex-snapshot/data/works/updated_date=2024-11-01" --no-sign-request
```

#### Option C: Sample Data (For Testing)
```bash
# Download just one partition for testing
aws s3 sync "s3://openalex/data/works/updated_date=2024-01-01" \
    "./openalex-snapshot/data/works/updated_date=2024-01-01" \
    --no-sign-request
```

### Verify Download

```bash
# Check downloaded size
du -sh openalex-snapshot/

# Count files
find openalex-snapshot/ -name "*.gz" | wc -l
```

## Step 2: Run the Extractor

### Basic Usage

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --format csv \
    --resume
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--snapshot-dir` | Path to OpenAlex snapshot | Required |
| `--output` | Output file path | Required |
| `--format` | Output format: csv, json, tsv | csv |
| `--resume` | Resume from previous run | False |
| `--oa-only` | Only open access works | False |
| `--year-from` | Minimum publication year | None |
| `--year-to` | Maximum publication year | None |
| `--types` | Work types to include | All |
| `--exclude-retracted` | Skip retracted works | False |
| `--max-workers` | Parallel workers | 1 |

### Common Use Cases

#### Extract All Open Access URLs
```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output oa_urls.csv \
    --oa-only \
    --resume
```

#### Extract Recent Publications (2020+)
```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output recent_urls.csv \
    --year-from 2020 \
    --resume
```

#### Extract Journal Articles Only
```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output articles.csv \
    --types journal-article \
    --oa-only \
    --resume
```

#### Extract Non-Retracted Biomedical Articles
```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output biomedical.csv \
    --oa-only \
    --exclude-retracted \
    --year-from 2015 \
    --resume
```

## Step 3: Monitor Progress

### Progress Display

The extractor shows real-time progress:
```
Processing OpenAlex files: 45%|████▌     | 1234/2750 [02:15<02:45, 9.12files/s]
```

### Log File

Check the log file for detailed information:
```bash
tail -f openalex_url_extraction.log
```

Example log entries:
```
2024-11-22 10:30:15 - INFO - Processing file: works/updated_date=2024-01-01/part_000.gz
2024-11-22 10:30:45 - INFO - Extracted 15,234 URL records from 12,456 works
2024-11-22 10:30:45 - INFO - Marked file as completed: works/updated_date=2024-01-01/part_000.gz
```

### Check Progress Status

```python
from helpers.file_tracker import FileTracker

tracker = FileTracker("doi_urls.tracking.db")
summary = tracker.get_processing_summary()

print(f"Files processed: {summary['total_files']}")
print(f"Data processed: {summary['total_size_mb']:.2f} MB")
print(f"Last update: {summary['last_processed']}")
```

## Step 4: Resume Interrupted Extraction

If extraction is interrupted (power failure, manual stop, etc.), simply re-run with `--resume`:

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --oa-only \
    --resume
```

The extractor will:
1. Check which files were already processed (via SHA-256 hash)
2. Skip completed files
3. Continue from where it left off

### Force Reprocessing

To reprocess all files (ignore previous progress):
```bash
# Remove the tracking database
rm doi_urls.tracking.db

# Run without --resume
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.csv \
    --oa-only
```

## Output Format

### CSV Output (Default)

The CSV file contains these columns:

| Column | Description | Example |
|--------|-------------|---------|
| doi | DOI identifier | 10.1038/nature12373 |
| openalex_id | OpenAlex work ID | W2123456789 |
| title | Publication title | Crystal structure of... |
| publication_year | Year published | 2013 |
| url | Open access URL | https://europepmc.org/... |
| pdf_url | Direct PDF link | https://europepmc.org/...pdf |
| location_type | URL source type | primary, alternate, best_oa |
| version | Document version | publishedVersion |
| license | License type | cc-by |
| host_type | Host type | publisher, repository |
| oa_status | OA status | gold, green, bronze |
| is_oa | Is open access | TRUE/FALSE |
| work_type | Publication type | journal-article |
| is_retracted | Is retracted | TRUE/FALSE |

### Sample Output

```csv
doi,openalex_id,title,publication_year,url,pdf_url,location_type,version,license,host_type,oa_status,is_oa,work_type,is_retracted
10.1038/nature12373,W2089522426,"Crystal structure of...",2013,https://europepmc.org/articles/PMC3888826,https://europepmc.org/articles/PMC3888826?pdf=render,primary,publishedVersion,cc-by,repository,green,TRUE,journal-article,FALSE
```

### JSON Output

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.json \
    --format json
```

### TSV Output

```bash
python openalex_unpaywall_extractor.py \
    --snapshot-dir ./openalex-snapshot \
    --output doi_urls.tsv \
    --format tsv
```

## Performance Tips

### For Faster Extraction

1. **Use an SSD**: Random read performance is crucial
2. **Process sequentially**: Use `--max-workers 1` for reliability
3. **Filter early**: Use `--oa-only` and year filters to reduce output

### For Memory-Constrained Systems

The extractor uses streaming, so memory usage is minimal. However:
- Keep output files on a disk with sufficient space
- Monitor disk space during long runs

### Estimated Processing Times

| Dataset | Files | Estimated Time |
|---------|-------|----------------|
| Full snapshot | ~2,750 | 4-8 hours |
| Last 5 years | ~500 | 1-2 hours |
| Last year | ~100 | 15-30 minutes |
| OA only | varies | ~40% faster |

## Statistics

After extraction, the extractor displays statistics:

```
===== Extraction Statistics =====
Total works processed: 125,456,789
Works with DOI: 98,765,432
Works with URLs: 45,678,901
Total URL records: 67,890,123
DOIs with PDF URLs: 34,567,890
Total PDF URLs: 45,678,901
Files processed: 2,750
Files skipped (unchanged): 0
=================================
```

## Next Steps

With URLs extracted, proceed to:
- [Importing Data](05-importing-data.md) - Load data into PostgreSQL
