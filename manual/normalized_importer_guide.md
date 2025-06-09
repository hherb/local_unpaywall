# Normalized Database Importer Guide

## Overview

The DOI URL importer has been updated to work with the new normalized database structure. This guide explains the changes and how to use the enhanced importer.

## Key Changes

### 1. Normalized Database Support

The importer now works with the normalized database structure that uses:
- **Lookup tables** for `license`, `oa_status`, `host_type`, and `work_type`
- **Foreign key references** instead of redundant text columns
- **Single character location types**: `'p'` (primary), `'a'` (alternate), `'b'` (best_oa)

### 2. Performance Optimizations

#### Lookup Table Caching
- **In-memory caches** for all lookup tables to avoid repeated database queries
- **Cache hit/miss statistics** to monitor performance
- **Preloading** of existing lookup values at import start

#### Index Management
- **Automatic index disabling** during bulk import for faster inserts
- **Index recreation** after import completion
- **Configurable index management** for different import scenarios

### 3. Enhanced Statistics

The importer now provides additional metrics:
- Lookup cache hit rates
- Cache performance statistics
- Normalized database-specific information

## Usage

### Basic Usage (Same as Before)

```bash
# With .env file
python doi_url_importer.py --csv-file data.csv

# With command line arguments
python doi_url_importer.py --csv-file data.csv \
    --db-host localhost --db-name unpaywall \
    --db-user myuser --db-password mypass
```

### New Features

#### Performance Mode
The importer automatically:
1. Preloads lookup table caches
2. Disables non-essential indexes during import
3. Recreates indexes after completion

#### Resume Functionality
Resume works the same way but now includes:
- Cached lookup table state
- Normalized data validation

## Database Schema Requirements

The importer requires the normalized database schema with:

### Lookup Tables
```sql
-- Required lookup tables
unpaywall.license
unpaywall.oa_status  
unpaywall.host_type
unpaywall.work_type
```

### Main Table
```sql
-- Updated doi_urls table with foreign keys
unpaywall.doi_urls (
    -- ... other columns ...
    license_id INTEGER REFERENCES unpaywall.license(id),
    host_type_id INTEGER REFERENCES unpaywall.host_type(id),
    oa_status_id INTEGER REFERENCES unpaywall.oa_status(id),
    work_type_id INTEGER REFERENCES unpaywall.work_type(id),
    location_type CHAR(1) CHECK (location_type IN ('p', 'a', 'b'))
)
```

## Data Transformation

### Location Type Mapping
- `'primary'` → `'p'`
- `'alternate'` → `'a'` 
- `'best_oa'` → `'b'`
- Unknown values → `'p'` (default)

### Lookup Value Processing
Text values are automatically converted to foreign key IDs:
- `license: 'cc-by'` → `license_id: 1`
- `oa_status: 'gold'` → `oa_status_id: 2`
- `host_type: 'journal'` → `host_type_id: 3`
- `work_type: 'journal-article'` → `work_type_id: 4`

## Performance Considerations

### Cache Performance
- **Cache hit rate** should be >95% for optimal performance
- **Cache misses** indicate new lookup values being created
- **Total cache size** shows memory usage for lookups

### Index Management
- Indexes are automatically disabled during bulk import
- **~50-70% performance improvement** during large imports
- Indexes are recreated after completion

### Batch Processing
- Default batch size: 10,000 rows
- Smaller batches for better error recovery
- Progress tracking with cache statistics

## Monitoring and Debugging

### Enhanced Statistics
```
DOI-URL IMPORT COMPLETED (NORMALIZED DATABASE)
============================================================
Import ID: doi_urls_1733123456_abc123
Total rows processed: 1,000,000
Rows inserted: 950,000
Rows updated: 50,000
Lookup cache entries: 1,234
Cache hit rate: 98.5% (2,500,000 hits, 37,500 misses)
Import duration: 1,200.5 seconds
Processing rate: 833.0 rows/sec
============================================================
```

### Cache Analysis
- **High cache hit rate** (>95%) = good performance
- **Many cache misses** = lots of new lookup values
- **Large cache size** = diverse data with many unique values

## Troubleshooting

### Common Issues

#### 1. Missing Lookup Tables
```
Error: relation "unpaywall.license" does not exist
```
**Solution**: Run database schema creation first:
```bash
python db/create_db.py
```

#### 2. Foreign Key Constraint Violations
```
Error: insert or update on table "doi_urls" violates foreign key constraint
```
**Solution**: Ensure lookup tables exist and are populated

#### 3. Location Type Validation Errors
```
Error: new row for relation "doi_urls" violates check constraint "chk_location_type"
```
**Solution**: Check location_type values in CSV data

### Performance Issues

#### Low Cache Hit Rate
- **Cause**: Many unique lookup values
- **Solution**: Consider data preprocessing to normalize values

#### Slow Index Recreation
- **Cause**: Large dataset with complex indexes
- **Solution**: Monitor progress, consider running during off-peak hours

## Migration from Old Importer

### Automatic Compatibility
The new importer automatically:
1. Detects normalized vs. legacy schema
2. Converts data formats appropriately
3. Maintains backward compatibility

### Data Validation
- All existing validation rules still apply
- Additional validation for foreign key constraints
- Enhanced error reporting for normalization issues

## Testing

Use the provided test script to verify functionality:

```bash
python test_normalized_importer.py
```

This tests:
- Location type normalization
- Lookup cache functionality
- Data validation logic
- DOI and OpenAlex ID processing

## Best Practices

### 1. Schema Preparation
- Always create the complete normalized schema first
- Verify lookup tables are properly indexed
- Test with small datasets before large imports

### 2. Performance Optimization
- Use appropriate batch sizes (10,000 is usually optimal)
- Monitor cache hit rates during import
- Allow sufficient time for index recreation

### 3. Data Quality
- Validate CSV data format before import
- Check for consistent lookup values
- Monitor import statistics for anomalies

### 4. Error Recovery
- Use resume functionality for interrupted imports
- Monitor log files for validation errors
- Keep backup of original CSV data

## Future Enhancements

Planned improvements include:
- Parallel processing for very large datasets
- Advanced cache warming strategies
- Custom index management options
- Integration with data quality tools
