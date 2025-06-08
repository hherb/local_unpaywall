# File Tracking System

## Overview

The file tracking system provides efficient incremental processing capabilities for the OpenAlex URL extractor. It uses SQLite to track which files have been processed, their content hashes, and processing statistics, enabling the system to skip unchanged files during subsequent runs.

## Key Features

- **Hash-based change detection**: Uses SHA-256 hashing to detect file changes
- **SQLite database**: Fast lookups and reliable storage
- **Processing statistics**: Tracks detailed statistics per file
- **Atomic operations**: Transaction-based updates prevent corruption
- **Legacy migration**: Automatically migrates from old JSON progress files

## Architecture

### FileTracker Class

Located in `helpers/file_tracker.py`, this class provides the core functionality:

```python
from helpers.file_tracker import FileTracker

# Initialize tracker
tracker = FileTracker("processing_progress.db")

# Check if file needs processing
if tracker.needs_processing("data/file.gz"):
    # Process the file
    stats = process_file("data/file.gz")
    # Mark as completed
    tracker.mark_completed("data/file.gz", stats)
```

### Database Schema

The SQLite database contains a single table `processed_files`:

- `id`: Primary key (INTEGER)
- `file_path`: Full path to the file (TEXT, UNIQUE)
- `file_hash`: SHA-256 hash of file content (TEXT)
- `file_size`: File size in bytes (INTEGER)
- `completion_date`: ISO format timestamp (TEXT)
- `processing_stats`: JSON string with processing statistics (TEXT)
- `created_at`: When first processed (TEXT)
- `updated_at`: When last updated (TEXT)

### Indexes

- `idx_file_path`: Fast lookups by file path
- `idx_file_hash`: Fast lookups by hash
- `idx_completion_date`: Chronological queries

## Integration with OpenAlex Extractor

The `OpenAlexURLExtractor` class automatically uses the file tracking system:

1. **Initialization**: Creates a `.tracking.db` file alongside the output file
2. **Legacy migration**: Automatically migrates from old `.progress` files
3. **Processing**: Checks each file with `needs_processing()` before processing
4. **Completion**: Marks files as completed with `mark_completed()`
5. **Statistics**: Includes tracking information in final statistics

## Usage Examples

### Basic Usage

```python
from openalex_unpaywall_extractor import OpenAlexURLExtractor

# Create extractor with resume capability
extractor = OpenAlexURLExtractor(
    snapshot_dir="/path/to/openalex-snapshot",
    output_file="urls.csv",
    resume=True  # Enable file tracking
)

# Run extraction - will skip unchanged files
extractor.extract_urls()
```

### Manual File Tracking

```python
from helpers.file_tracker import FileTracker

tracker = FileTracker("my_processing.db")

# Check processing status
files_to_process = []
for file_path in all_files:
    if tracker.needs_processing(file_path):
        files_to_process.append(file_path)

# Process files and track completion
for file_path in files_to_process:
    stats = process_file(file_path)
    tracker.mark_completed(file_path, stats)

# Get summary
summary = tracker.get_processing_summary()
print(f"Processed {summary['total_files']} files")
```

### Cleanup Operations

```python
# Remove records for missing files
removed_count = tracker.cleanup_missing_files()

# Remove specific file record
tracker.remove_file_record("/path/to/file.gz")

# Get all processed files
processed_files = tracker.get_processed_files()
```

## Command Line Usage

The enhanced extractor supports the same command line interface with automatic file tracking:

```bash
# Initial run
python openalex_unpaywall_extractor.py \
    --snapshot-dir /path/to/openalex-snapshot \
    --output urls.csv \
    --format csv

# Resume run (will skip unchanged files)
python openalex_unpaywall_extractor.py \
    --snapshot-dir /path/to/openalex-snapshot \
    --output urls.csv \
    --format csv \
    --resume
```

## File Outputs

When using the enhanced extractor, you'll see these files:

- `urls.csv`: Main output file
- `urls.tracking.db`: SQLite tracking database
- `openalex_url_extraction.log`: Processing log

## Performance Benefits

- **Incremental processing**: Only processes changed files
- **Fast lookups**: SQLite indexes enable O(log n) file status checks
- **Reduced I/O**: Skips reading unchanged compressed files
- **Resume capability**: Safely resume interrupted processing

## Error Handling

The system gracefully handles:

- **Missing files**: Returns `False` for `needs_processing()`
- **Corrupted databases**: Automatically recreates schema
- **Permission errors**: Logs warnings and continues
- **Legacy migration**: Safely migrates old progress files

## Testing

Run the test suite to verify functionality:

```bash
python -m test.test_file_tracker
python -m test.test_integration
```

## Migration from Legacy System

The system automatically migrates from the old JSON-based progress tracking:

1. Detects existing `.progress` files
2. Reads processed file list
3. Marks files as completed in SQLite database
4. Backs up old progress file as `.progress.backup`
5. Removes original progress file

## Best Practices

1. **Database location**: Keep tracking database with output files
2. **Cleanup**: Periodically run `cleanup_missing_files()`
3. **Backup**: Include `.tracking.db` files in backups
4. **Monitoring**: Check processing summaries for insights
5. **Testing**: Verify file tracking with small datasets first

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure write access to database directory
2. **Disk space**: Monitor disk usage for large tracking databases
3. **Corruption**: Delete `.tracking.db` to reset (loses progress)
4. **Performance**: Consider cleanup if database grows very large

### Debug Information

Enable debug logging to see file tracking operations:

```python
import logging
logging.getLogger('helpers.file_tracker').setLevel(logging.DEBUG)
```
