# Testing Guide

## Overview

This document describes the testing framework and practices for the local_unpaywall project. All tests are organized in a dedicated `test/` directory to maintain clean separation between production code and test code.

## Test Organization

### Directory Structure

```
test/
├── __init__.py                 # Test package initialization
├── run_all_tests.py           # Test runner script
├── test_csv_utils.py          # Tests for CSV processing utilities
├── test_file_tracker.py       # Tests for file tracking system
└── test_integration.py        # Integration tests
```

### Test Categories

1. **Unit Tests**: Test individual modules and functions in isolation
   - `test_csv_utils.py`: Memory-efficient CSV processing
   - `test_file_tracker.py`: SQLite-based file tracking

2. **Integration Tests**: Test interactions between components
   - `test_integration.py`: OpenAlex extractor with file tracking

## Running Tests

### Run All Tests

```bash
# From project root
python -m test.run_all_tests

# Or directly
python test/run_all_tests.py
```

### Run Individual Test Modules

```bash
# CSV utilities tests
python -m test.test_csv_utils

# File tracker tests
python -m test.test_file_tracker

# Integration tests
python -m test.test_integration
```

### Run Specific Test Classes or Methods

```bash
# Run specific test class
python -m unittest test.test_file_tracker.TestFileTracker

# Run specific test method
python -m unittest test.test_file_tracker.TestFileTracker.test_file_hash_calculation
```

## Test Coverage

### CSV Utils Tests (`test_csv_utils.py`)

Tests the memory-efficient CSV processing utilities:

- **Basic Processing**: Batch processing without validation
- **Validation**: Row validation and transformation
- **Error Handling**: Empty files, missing files, malformed data
- **Delimiter Detection**: Automatic detection of CSV delimiters
- **Convenience Functions**: High-level processing functions

### File Tracker Tests (`test_file_tracker.py`)

Tests the SQLite-based file tracking system:

- **Database Operations**: Initialization, schema creation
- **Hash Calculation**: File content hashing and consistency
- **Processing Status**: Tracking file processing state
- **Change Detection**: Detecting file modifications
- **Statistics**: Processing summaries and metadata
- **Cleanup**: Removing records for missing files

### Integration Tests (`test_integration.py`)

Tests the complete workflow:

- **Initial Processing**: First-time file processing
- **Resume Functionality**: Skipping unchanged files
- **Change Detection**: Reprocessing modified files
- **End-to-End Workflow**: Complete extraction pipeline

## Test Data and Fixtures

### Temporary Files

All tests use temporary files and directories that are automatically cleaned up:

```python
def setUp(self):
    self.temp_dir = tempfile.mkdtemp()
    # Create test files...

def tearDown(self):
    shutil.rmtree(self.temp_dir)
```

### Test Data Generation

Tests generate realistic test data:

- **CSV Files**: Sample data with various formats and edge cases
- **OpenAlex Data**: Mock JSON data matching real OpenAlex structure
- **Compressed Files**: Gzipped test files for realistic scenarios

## Best Practices

### Writing Tests

1. **Descriptive Names**: Use clear, descriptive test method names
2. **Single Responsibility**: Each test should verify one specific behavior
3. **Isolation**: Tests should not depend on each other
4. **Cleanup**: Always clean up temporary resources
5. **Edge Cases**: Test boundary conditions and error scenarios

### Test Structure

```python
class TestMyComponent(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize test data
        
    def tearDown(self):
        """Clean up after each test method."""
        # Remove temporary files
        
    def test_normal_operation(self):
        """Test normal operation with valid input."""
        # Test implementation
        
    def test_error_handling(self):
        """Test error handling with invalid input."""
        # Test error scenarios
```

## Continuous Integration

### Test Automation

Tests are designed to run in automated environments:

- **No External Dependencies**: Tests use only standard library and project dependencies
- **Deterministic**: Tests produce consistent results across runs
- **Fast Execution**: Complete test suite runs in under 2 minutes
- **Clear Output**: Detailed reporting of test results

### Performance Testing

Integration tests include performance validation:

- **Memory Usage**: Verify constant memory usage for large files
- **Processing Speed**: Ensure reasonable processing rates
- **Database Performance**: Validate SQLite query performance

## Debugging Tests

### Verbose Output

```bash
# Run with maximum verbosity
python -m unittest -v test.test_file_tracker

# Run with custom test runner for detailed output
python -m test.run_all_tests
```

### Logging

Enable debug logging during tests:

```python
import logging
logging.getLogger('helpers.file_tracker').setLevel(logging.DEBUG)
logging.getLogger('helpers.csv_utils').setLevel(logging.DEBUG)
```

### Test Isolation

Run individual tests to isolate issues:

```bash
# Run single test method
python -m unittest test.test_file_tracker.TestFileTracker.test_file_hash_calculation -v
```

## Adding New Tests

### For New Modules

1. Create new test file: `test/test_new_module.py`
2. Follow naming convention: `test_<module_name>.py`
3. Import the module under test
4. Create test class inheriting from `unittest.TestCase`
5. Add comprehensive test coverage

### For Bug Fixes

1. Write a test that reproduces the bug
2. Verify the test fails with the current code
3. Fix the bug
4. Verify the test passes
5. Ensure no regression in other tests

## Test Dependencies

### Required Packages

- `unittest`: Standard library testing framework
- `tempfile`: Temporary file/directory creation
- `pathlib`: Path manipulation
- `json`: JSON data handling
- `gzip`: Compressed file testing

### Optional Packages

- `tqdm`: Progress bar testing (graceful fallback if missing)

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure project root is in Python path
2. **Permission Errors**: Check write permissions for temporary directories
3. **Resource Cleanup**: Verify all temporary files are properly cleaned up
4. **Test Isolation**: Ensure tests don't interfere with each other

### Debug Tips

1. **Print Statements**: Add temporary print statements for debugging
2. **Test Data**: Inspect temporary test files if tests fail
3. **Logging**: Enable detailed logging to trace execution
4. **Breakpoints**: Use debugger breakpoints in test methods
