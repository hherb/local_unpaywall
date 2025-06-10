# Database Creation Module

## Overview

The `db/create_db.py` module provides centralized database schema creation and management for the local_unpaywall project. This module was created to separate database structure management from import logic, following the principle of clean separation of concerns.

## Architecture

### Design Principles

1. **Separation of Concerns**: Database schema creation is now separate from data import logic
2. **Centralized Management**: All table/index creation is handled in one place
3. **Reusability**: The module can be used by multiple components
4. **Configuration Flexibility**: Supports both .env files and command-line arguments
5. **Idempotent Operations**: Safe to run multiple times without side effects

### Module Structure

```
db/
├── create_db.py          # Main database creation module
├── test_create_db.py     # Unit tests
├── run_migration.py      # Migration runner (existing)
└── migrations/           # SQL migration files (existing)
```

## DatabaseCreator Class

### Core Methods

#### Schema Creation
- `create_unpaywall_schema()`: Creates the unpaywall namespace
- `create_doi_urls_table()`: Creates the main DOI-URL mapping table
- `create_import_progress_table()`: Creates import tracking table

#### Index Management
- `create_doi_urls_indexes()`: Creates all indexes for doi_urls table
- `create_import_progress_indexes()`: Creates indexes for import_progress table

#### Permissions and Verification
- `set_permissions()`: Sets appropriate database permissions
- `verify_schema()`: Verifies all components were created successfully
- `get_schema_info()`: Returns current schema state information

#### Orchestration
- `create_complete_schema()`: Creates the complete schema in proper order
- `test_connection()`: Tests database connectivity

### Configuration Methods

#### Instance Creation
```python
# Direct instantiation
creator = DatabaseCreator(
    host='localhost',
    database='mydb',
    user='myuser',
    password='mypass',
    port=5432
)

# From .env file with command line override
creator = DatabaseCreator.from_env_or_args(
    host='localhost',  # Override .env value
    database=None,     # Use .env value
    user='myuser',     # Override .env value
    password=None,     # Use .env value
    port=None          # Use .env value
)
```

## Usage Examples

### Command Line Interface

```bash
# Create schema with explicit credentials
python db/create_db.py --db-name mydb --db-user myuser --db-password mypass

# Create schema using .env file
python db/create_db.py

# Test connection only
python db/create_db.py --test-only

# Get schema information
python db/create_db.py --info

# Verbose output
python db/create_db.py --verbose
```

### Programmatic Usage

```python
from db.create_db import DatabaseCreator

# Create and verify complete schema
creator = DatabaseCreator.from_env_or_args(
    database='unpaywall_db',
    user='postgres'
)

success = creator.create_complete_schema()
if success:
    print("Schema created successfully")
else:
    print("Schema creation failed")

# Get schema information
info = creator.get_schema_info()
print(f"Schema exists: {info['schema_exists']}")
print(f"Tables: {info['tables']}")
print(f"Row counts: {info['row_counts']}")
```

## Integration with DOI URL Importer

The `doi_url_importer.py` has been updated to use the new `DatabaseCreator`:

### Before (Old Implementation)
```python
def create_schema(self):
    """Create the DOI-URL mapping tables with error handling"""
    # 120+ lines of table creation SQL
    # Index creation SQL
    # Constraint creation SQL
    # etc.
```

### After (New Implementation)
```python
def create_schema(self):
    """Create the DOI-URL mapping tables using the centralized DatabaseCreator"""
    creator = DatabaseCreator(**self.db_config)
    success = creator.create_complete_schema(verify=True)
    if not success:
        raise RuntimeError("Schema creation failed")
```

## Database Schema Components

### Tables Created

1. **unpaywall.doi_urls**
   - Main DOI-URL mapping table
   - Includes all metadata fields
   - Primary key: `id` (BIGSERIAL)
   - Unique constraint: `(doi, url)`

2. **unpaywall.import_progress**
   - Import tracking and resume functionality
   - Primary key: `import_id` (TEXT)
   - Tracks file hashes for change detection

### Indexes Created

#### DOI URLs Table
- `idx_unpaywall_doi_urls_doi`: Primary DOI lookups
- `idx_unpaywall_doi_urls_url`: URL lookups
- `idx_unpaywall_doi_urls_pdf_url`: PDF URL access (partial index)
- `idx_unpaywall_doi_urls_doi_location_type`: Combined DOI/location queries
- `idx_unpaywall_doi_urls_oa_status`: Open access filtering (partial index)
- `idx_unpaywall_doi_urls_host_type`: Host type filtering
- `idx_unpaywall_doi_urls_publication_year`: Year-based queries
- `idx_unpaywall_doi_urls_work_type`: Work type filtering
- `idx_unpaywall_doi_urls_is_retracted`: Retraction status filtering
- `idx_unpaywall_doi_urls_openalex_work_id`: OpenAlex ID lookups

#### Import Progress Table
- `idx_unpaywall_import_progress_file_path`: File path lookups
- `idx_unpaywall_import_progress_status`: Status filtering

### Permissions

The module sets public permissions for general access:
- Schema usage: `GRANT USAGE ON SCHEMA unpaywall TO PUBLIC`
- Table access: `GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.* TO PUBLIC`
- Sequence access: `GRANT USAGE, SELECT ON SEQUENCE unpaywall.doi_urls_id_seq TO PUBLIC`

## Error Handling

### Connection Errors
- Comprehensive error logging
- Graceful failure with meaningful messages
- Connection testing before schema operations

### Schema Creation Errors
- Transaction rollback on failures
- Detailed error reporting
- Verification of successful creation

### Configuration Errors
- Clear error messages for missing parameters
- Validation of .env file values
- Type checking for numeric parameters

## Testing

### Unit Tests
The module includes comprehensive unit tests in `db/test_create_db.py`:

```bash
# Run all tests
python -m unittest db.test_create_db -v

# Run specific test
python -m unittest db.test_create_db.TestDatabaseCreator.test_create_complete_schema_success -v
```

### Test Coverage
- Configuration loading (.env and command line)
- Database connection testing
- Schema creation methods
- Error handling scenarios
- Complete schema orchestration

## Migration Compatibility

The new module is fully compatible with the existing migration system:

1. **Migration 003** created the unpaywall schema structure
2. **DatabaseCreator** maintains the same schema structure
3. **Migration system** continues to handle schema evolution
4. **DatabaseCreator** handles initial schema creation

## Benefits

### For Developers
1. **Cleaner Code**: Separation of concerns makes code more maintainable
2. **Reusability**: Database creation logic can be used by multiple components
3. **Testing**: Easier to unit test database creation separately
4. **Documentation**: Centralized location for all schema creation logic

### For Operations
1. **Standalone Tool**: Can create schemas independently of imports
2. **Verification**: Built-in schema verification and information gathering
3. **Flexibility**: Supports multiple configuration methods
4. **Reliability**: Comprehensive error handling and logging

## Future Enhancements

### Planned Features
1. **Schema Validation**: More comprehensive schema validation
2. **Backup Integration**: Schema backup before modifications
3. **Performance Monitoring**: Index usage and performance metrics
4. **Multi-Database Support**: Support for multiple database backends

### Extension Points
1. **Custom Indexes**: Easy addition of new indexes
2. **Additional Tables**: Framework for adding new tables
3. **Permission Management**: More granular permission control
4. **Configuration Sources**: Additional configuration sources (YAML, JSON)

## Best Practices

### When to Use
- Initial database setup
- Development environment setup
- Testing environment preparation
- Schema recreation after major changes

### When NOT to Use
- Production schema modifications (use migrations instead)
- Data-preserving schema changes (use migrations instead)
- Minor schema adjustments (use migrations instead)

### Recommended Workflow
1. **Development**: Use `DatabaseCreator` for fresh setups
2. **Schema Changes**: Create migrations for modifications
3. **Testing**: Use `DatabaseCreator` for test database setup
4. **Production**: Use migration system for all changes
