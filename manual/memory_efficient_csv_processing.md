# Memory-Efficient CSV Processing

## Overview

This document describes the memory-efficient CSV processing utilities implemented in the `helpers/csv_utils.py` module. These utilities are designed to handle very large CSV files (GB+ sizes) without loading the entire file into memory.

## Problem Statement

Traditional CSV processing approaches load the entire file into memory, which can cause:
- Memory exhaustion with large files
- Poor performance due to memory pressure
- System instability when processing multiple large files

## Solution

The memory-efficient approach uses Python generators to:
- Process CSV files in configurable batches
- Maintain constant memory usage regardless of file size
- Provide progress tracking for long-running operations
- Support validation and transformation of rows

## Key Components

### CSVBatchProcessor Class

The main class for memory-efficient CSV processing:

```python
from helpers.csv_utils import CSVBatchProcessor

processor = CSVBatchProcessor(
    csv_file='large_file.csv',
    batch_size=10000,
    validator=my_validator_function,
    show_progress=True
)

for batch in processor.process_batches():
    # Process each batch of rows
    process_batch(batch)
```

### Convenience Function

For simple use cases:

```python
from helpers.csv_utils import process_csv_in_batches

for batch in process_csv_in_batches('file.csv', batch_size=5000):
    # Process batch
    for row in batch:
        print(row)
```

## Features

### 1. Automatic Delimiter Detection

The processor automatically detects CSV delimiters (comma, tab, semicolon, pipe) using Python's csv.Sniffer with fallback logic.

### 2. Row Validation and Transformation

Optional validator function can be provided to:
- Validate row data
- Transform/clean row data
- Filter out invalid rows

```python
def validator(row):
    if row.get('email') and '@' in row['email']:
        return {
            'email': row['email'].lower(),
            'name': row.get('name', '').strip(),
            'age': int(row.get('age', 0)) if row.get('age', '').isdigit() else None
        }
    return None  # Skip invalid rows
```

### 3. Progress Tracking

Uses tqdm for clean progress bars showing:
- Number of rows processed
- Processing rate
- Estimated time remaining

### 4. Error Handling

Robust error handling for:
- Missing files
- Empty files
- Malformed CSV data
- Encoding issues

## Memory Efficiency

### Traditional Approach
```python
# BAD: Loads entire file into memory
with open('huge_file.csv') as f:
    reader = csv.DictReader(f)
    all_rows = list(reader)  # Memory usage = file size
    process_all_rows(all_rows)
```

### Memory-Efficient Approach
```python
# GOOD: Constant memory usage
for batch in process_csv_in_batches('huge_file.csv', batch_size=10000):
    process_batch(batch)  # Memory usage = batch_size * row_size
```

## Performance Characteristics

- **Memory Usage**: O(batch_size) instead of O(file_size)
- **Processing Speed**: Similar to traditional methods
- **Scalability**: Can handle files larger than available RAM

## Integration Examples

### Database Import

```python
from helpers.csv_utils import CSVBatchProcessor

def import_to_database(csv_file, db_connection):
    processor = CSVBatchProcessor(csv_file, batch_size=10000)
    
    for batch in processor.process_batches():
        # Insert batch into database
        insert_batch_to_db(batch, db_connection)
```

### Data Transformation

```python
def transform_csv(input_file, output_file):
    def transformer(row):
        # Transform row data
        return {
            'id': int(row['id']),
            'email': row['email'].lower(),
            'created_at': parse_date(row['date'])
        }
    
    with open(output_file, 'w') as out:
        writer = csv.DictWriter(out, fieldnames=['id', 'email', 'created_at'])
        writer.writeheader()
        
        for batch in process_csv_in_batches(input_file, validator=transformer):
            writer.writerows(batch)
```

## Testing

Use the test script to compare memory usage:

```bash
python experimental/test_memory_efficient_csv.py --create-test --test-rows 100000 --compare-methods
```

This will create a test CSV and compare traditional vs memory-efficient processing methods.

## Best Practices

1. **Choose Appropriate Batch Size**:
   - Larger batches: Better performance, more memory usage
   - Smaller batches: Lower memory usage, more overhead
   - Recommended: 5,000-50,000 rows per batch

2. **Use Validation Functions**:
   - Filter out invalid data early
   - Transform data types as needed
   - Keep validator functions simple and fast

3. **Monitor Progress**:
   - Enable progress bars for long-running operations
   - Log batch processing statistics

4. **Handle Errors Gracefully**:
   - Wrap processing in try-catch blocks
   - Log problematic rows for debugging
   - Implement retry logic for transient failures

## Modified Components

### DOI URL Importer

The `doi_url_importer.py` has been updated to use memory-efficient processing:

- `read_csv_in_batches()` now returns a generator instead of a list
- Memory usage is constant regardless of CSV file size
- Progress tracking with tqdm
- All existing functionality preserved

## Dependencies

- `tqdm`: For progress bars (optional, graceful fallback)
- Standard library: `csv`, `pathlib`, `typing`

## Future Enhancements

1. **Parallel Processing**: Process multiple batches concurrently
2. **Streaming Validation**: Real-time validation during file reading
3. **Compression Support**: Direct processing of compressed CSV files
4. **Resume Capability**: Resume processing from specific batch/row
