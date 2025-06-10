# DOI URL Importer Performance Improvements

## Issues Fixed

### 1. Double Line Counting (Major Performance Issue)
**Problem**: The importer was counting CSV lines twice:
- Once in `_count_csv_rows()` method 
- Again in `read_csv_in_batches_optimized()` method

**Solution**: 
- Added caching of line count in `_count_csv_rows()` method
- Modified CSV reader to use cached count instead of recounting
- Added logging to show when line counting occurs

### 2. Excessive Database Row Counting (Performance Overhead)
**Problem**: The importer was counting database rows before and after each batch, adding significant overhead.

**Solution**:
- Removed row counting from individual batch operations
- Reduced periodic database count checks from every 10 batches to every 50 batches
- Simplified batch result reporting to focus on insert/conflict counts

### 3. Poor Performance Monitoring
**Problem**: Limited visibility into where time was being spent during import.

**Solution**:
- Added detailed timing for each phase (schema creation, cache loading, index disabling, etc.)
- Added per-batch timing information showing insert time and rows/second
- Added overall processing rate monitoring

### 4. Suboptimal Default Batch Size
**Problem**: Default batch size of 10,000 was conservative for large imports.

**Solution**:
- Increased default batch size to 25,000 for better performance
- Updated help text to encourage larger batch sizes for performance

## Expected Performance Improvements

1. **Elimination of double line counting**: Should save 20-30 seconds on a 60GB file
2. **Reduced database counting overhead**: Should improve batch processing speed by 10-20%
3. **Better monitoring**: Will help identify remaining bottlenecks
4. **Larger batch size**: Should improve overall throughput by 15-25%

## Usage

The improved importer maintains the same command line interface:

```bash
python doi_url_importer.py --csv-file unpaywall_new.csv --db-name knowledgebase --db-user rwbadmin --db-password rwb2025admin --resume
```

For maximum performance on large files, consider:

```bash
python doi_url_importer.py --csv-file unpaywall_new.csv --db-name knowledgebase --db-user rwbadmin --db-password rwb2025admin --resume --batch-size 50000
```

## Monitoring

The improved version provides detailed timing information:
- Phase-by-phase timing (schema, cache, indexes, etc.)
- Per-batch timing and throughput
- Overall processing rate
- Periodic progress reports every 50 batches instead of every 10

This will help identify any remaining performance bottlenecks.
