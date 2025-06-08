# Local Unpaywall - Programmer's Manual

This directory contains detailed technical documentation for the Local Unpaywall project components and systems.

## Documentation Index

### Core System Documentation

#### [File Tracking System](file_tracking_system.md)
- SQLite-based file tracking for incremental processing
- Hash-based change detection using SHA-256
- Resume capability and processing statistics
- Usage examples and API reference

#### [Memory-Efficient CSV Processing](memory_efficient_csv_processing.md)
- Generator-based batch processing for large CSV files
- Automatic delimiter detection
- Progress tracking with tqdm
- Memory optimization techniques

#### [PDF Fetcher Utility](pdf_fetcher.md)
- PDF download utility with progress tracking
- Resume capability for interrupted downloads
- PDF content validation
- Command-line and programmatic usage
- Batch download examples

#### [Testing Guide](testing_guide.md)
- Comprehensive testing framework
- Unit tests and integration tests
- Test data creation and management
- Performance testing guidelines

## System Architecture

### Component Overview

The Local Unpaywall system consists of several interconnected components:

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   OpenAlex Data     │    │    URL Extractor     │    │    CSV Output       │
│   (Compressed       │───▶│  (openalex_unpaywall │───▶│   (DOI-URL pairs)   │
│    JSONL Files)     │    │   _extractor.py)     │    │                     │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
                                       │                           │
                                       ▼                           ▼
                           ┌──────────────────────┐    ┌─────────────────────┐
                           │   File Tracker       │    │   Database Importer │
                           │  (SQLite Database)   │    │ (doi_url_importer.py)│
                           └──────────────────────┘    └─────────────────────┘
                                                                   │
                                                                   ▼
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Downloaded PDFs   │◀───│    PDF Fetcher       │◀───│   PostgreSQL        │
│                     │    │  (pdf_fetcher.py)    │    │   Database          │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

### Data Flow

1. **Extraction Phase**: OpenAlex snapshot data is processed to extract DOI-URL pairs
2. **Tracking Phase**: File tracker monitors processed files for incremental updates
3. **Import Phase**: Extracted data is imported into PostgreSQL with quality scoring
4. **Download Phase**: PDF fetcher downloads full-text PDFs from discovered URLs

### Key Design Principles

#### Memory Efficiency
- **Generator-based Processing**: All components use Python generators to process data in chunks
- **Configurable Batch Sizes**: Memory usage can be controlled through batch size parameters
- **Streaming Operations**: Large files are processed without loading entirely into memory

#### Fault Tolerance
- **Resume Capability**: All long-running operations can be safely interrupted and resumed
- **Hash-based Change Detection**: Only modified files are reprocessed
- **Robust Error Handling**: Network failures, file corruption, and other errors are handled gracefully

#### Scalability
- **Parallel Processing**: Multi-threaded processing where appropriate
- **Database Optimization**: Efficient indexing and batch operations
- **Progress Tracking**: Real-time progress monitoring for long operations

## Development Guidelines

### Code Organization

The project follows a clean separation of concerns:

- **`helpers/`**: Reusable utility modules
- **`test/`**: Comprehensive test suite
- **`manual/`**: Technical documentation
- **Root directory**: Main application scripts

### Coding Standards

- **Type Hints**: All functions include comprehensive type annotations
- **Documentation**: Detailed docstrings for all public APIs
- **Error Handling**: Explicit error handling with informative messages
- **Testing**: Unit tests for all components with high coverage

### Adding New Components

When adding new functionality:

1. **Create the module** in the appropriate directory
2. **Add comprehensive tests** in the `test/` directory
3. **Update documentation** in the `manual/` directory
4. **Update the main README.md** with usage examples
5. **Run the full test suite** to ensure compatibility

### Performance Considerations

#### Memory Usage
- Use generators for large data processing
- Implement configurable batch sizes
- Monitor memory usage during development

#### Database Performance
- Use batch operations for database writes
- Implement proper indexing strategies
- Consider connection pooling for high-throughput operations

#### Network Operations
- Implement retry logic with exponential backoff
- Use connection pooling for HTTP requests
- Handle rate limiting appropriately

## Troubleshooting

### Common Development Issues

#### Import Errors
```python
# Ensure proper path setup for tests
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

#### Memory Issues
```python
# Use generators instead of lists for large datasets
def process_large_file(filename):
    for batch in process_in_batches(filename, batch_size=1000):
        yield from batch
```

#### Database Connection Issues
```python
# Use context managers for database connections
with sqlite3.connect(db_path) as conn:
    # Database operations here
    pass  # Connection automatically closed
```

### Testing Best Practices

- **Isolated Tests**: Each test should be independent
- **Temporary Files**: Use `tempfile` for test data
- **Mock External Dependencies**: Mock network calls and file system operations
- **Comprehensive Coverage**: Test both success and failure scenarios

## API Reference

### Core Classes

#### `FileTracker`
- **Purpose**: SQLite-based file tracking for incremental processing
- **Key Methods**: `needs_processing()`, `mark_completed()`, `get_processing_summary()`
- **Documentation**: [file_tracking_system.md](file_tracking_system.md)

#### `CSVBatchProcessor`
- **Purpose**: Memory-efficient CSV processing with generators
- **Key Methods**: `process_batches()`, `get_statistics()`
- **Documentation**: [memory_efficient_csv_processing.md](memory_efficient_csv_processing.md)

#### `PDFFetcher`
- **Purpose**: PDF download utility with progress tracking
- **Key Methods**: `download_pdf()`, `validate_pdf_content()`, `get_file_size()`
- **Documentation**: [pdf_fetcher.md](pdf_fetcher.md)

### Utility Functions

#### `process_csv_in_batches()`
- **Purpose**: Convenience function for CSV batch processing
- **Parameters**: `csv_file`, `batch_size`, `validator`
- **Returns**: Generator yielding batches of validated rows

## Version History

### Current Version Features
- OpenAlex snapshot processing
- PostgreSQL database import
- SQLite-based file tracking
- Memory-efficient CSV processing
- PDF download utility
- Comprehensive test suite

### Future Enhancements
- Web interface for database queries
- Automated PDF content extraction
- Citation network analysis
- API endpoints for external access

## Contributing

### Development Workflow

1. **Fork the repository** and create a feature branch
2. **Implement changes** following the coding standards
3. **Add comprehensive tests** for new functionality
4. **Update documentation** in the `manual/` directory
5. **Run the full test suite** to ensure compatibility
6. **Submit a pull request** with detailed description

### Documentation Standards

- **Clear Examples**: Include practical usage examples
- **API Documentation**: Document all public methods and parameters
- **Architecture Diagrams**: Use ASCII art for system diagrams
- **Troubleshooting**: Include common issues and solutions

---

For specific implementation details, refer to the individual documentation files in this directory.
