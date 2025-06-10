#!/usr/bin/env python3
"""
Test script for OpenAlex ID storage optimization

This script tests the conversion from storing full OpenAlex URLs to storing
only the numeric part as BIGINT for storage efficiency.
"""

import tempfile
import json
import csv
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from openalex_unpaywall_extractor import OpenAlexURLExtractor
from doi_url_importer import DOIURLImporter


def test_openalex_id_extraction():
    """Test extraction of numeric ID from various OpenAlex URL formats"""
    print("Testing OpenAlex ID extraction...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_output.csv"
        
        extractor = OpenAlexURLExtractor(
            snapshot_dir=temp_path,
            output_file=output_file,
            output_format='csv'
        )
        
        # Test various input formats
        test_cases = [
            ("https://openalex.org/W1982051859", "1982051859"),
            ("https://openalex.org/W2741809807", "2741809807"),
            ("W1982051859", "1982051859"),
            ("1982051859", "1982051859"),
            ("", None),
            (None, None),
            ("invalid", None),
        ]
        
        for input_id, expected in test_cases:
            result = extractor._extract_openalex_work_id(input_id)
            assert result == expected, f"Expected {expected}, got {result} for input {input_id}"
        
        print("✓ OpenAlex ID extraction works correctly")
        return True


def test_csv_output_numeric_ids():
    """Test that CSV output contains numeric OpenAlex IDs"""
    print("Testing CSV output with numeric OpenAlex IDs...")
    
    # Create test OpenAlex work data
    test_work = {
        "id": "https://openalex.org/W1982051859",
        "doi": "https://doi.org/10.1038/nature12373",
        "title": "Test Article",
        "publication_year": 2023,
        "type": "journal-article",
        "is_retracted": False,
        "open_access": {"is_oa": True, "oa_status": "gold"},
        "primary_location": {
            "landing_page_url": "https://www.nature.com/articles/nature12373",
            "pdf_url": "https://www.nature.com/articles/nature12373.pdf",
            "version": "publishedVersion",
            "license": "cc-by",
            "source": {"display_name": "Nature", "is_in_doaj": True}
        },
        "locations": [],
        "best_oa_location": None
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_output.csv"
        
        # Create proper directory structure
        data_dir = temp_path / "data" / "works" / "updated_date=2023-01-01"
        data_dir.mkdir(parents=True)
        
        # Create test JSONL file
        test_jsonl = data_dir / "part_000.gz"
        import gzip
        with gzip.open(test_jsonl, 'wt') as f:
            f.write(json.dumps(test_work) + '\n')
        
        # Create extractor and process
        extractor = OpenAlexURLExtractor(
            snapshot_dir=temp_path,
            output_file=output_file,
            output_format='csv'
        )
        
        # Process the test file
        extractor.extract_urls({})
        
        # Verify CSV content
        with open(output_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) > 0, "No data rows in CSV output"
            
            row = rows[0]
            # Should contain numeric ID, not full URL
            assert row['openalex_id'] == '1982051859', f"Expected numeric ID '1982051859', got '{row['openalex_id']}'"
            assert 'openalex.org' not in row['openalex_id'], "CSV should contain numeric ID, not full URL"
        
        print("✓ CSV output correctly contains numeric OpenAlex IDs")
        return True


def test_importer_conversion():
    """Test that the importer correctly converts OpenAlex IDs to BIGINT"""
    print("Testing importer OpenAlex ID conversion...")
    
    # Create a temporary importer instance for testing conversion methods
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_csv = Path(temp_dir) / "test.csv"
        
        # We don't need a real database connection for this test
        db_config = {
            'host': 'localhost',
            'database': 'test',
            'user': 'test',
            'password': 'test'
        }
        importer = DOIURLImporter(
            db_config=db_config,
            csv_file=str(temp_csv)
        )
        
        # Test conversion method
        test_cases = [
            ("https://openalex.org/W1982051859", 1982051859),
            ("W1982051859", 1982051859),
            ("1982051859", 1982051859),
            ("", None),
            ("invalid", None),
            (None, None),
        ]
        
        for input_id, expected in test_cases:
            result = importer._safe_openalex_id(input_id)
            assert result == expected, f"Expected {expected}, got {result} for input {input_id}"
        
        print("✓ Importer correctly converts OpenAlex IDs to BIGINT")
        return True


def test_row_validation_with_numeric_ids():
    """Test row validation with numeric OpenAlex IDs"""
    print("Testing row validation with numeric OpenAlex IDs...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_csv = Path(temp_dir) / "test.csv"
        
        db_config = {
            'host': 'localhost',
            'database': 'test',
            'user': 'test',
            'password': 'test'
        }
        importer = DOIURLImporter(
            db_config=db_config,
            csv_file=str(temp_csv)
        )
        
        # Test row with numeric OpenAlex ID
        test_row = {
            'doi': '10.1038/nature12373',
            'url': 'https://www.nature.com/articles/nature12373',
            'openalex_id': '1982051859',  # Numeric ID as string
            'location_type': 'primary',
            'is_oa': 'true',
            'work_type': 'journal-article',
            'is_retracted': 'false'
        }
        
        cleaned_row = importer.validate_and_clean_row(test_row)
        
        assert cleaned_row is not None, "Row validation failed"
        assert cleaned_row['openalex_id'] == 1982051859, f"Expected integer 1982051859, got {cleaned_row['openalex_id']}"
        assert isinstance(cleaned_row['openalex_id'], int), f"Expected integer type, got {type(cleaned_row['openalex_id'])}"
        
        print("✓ Row validation correctly handles numeric OpenAlex IDs")
        return True


def test_storage_efficiency():
    """Test and demonstrate storage efficiency gains"""
    print("Testing storage efficiency calculations...")
    
    # Simulate storage calculations
    sample_ids = [
        "https://openalex.org/W1982051859",
        "https://openalex.org/W2741809807", 
        "https://openalex.org/W123456789",
        "https://openalex.org/W987654321",
        "https://openalex.org/W555666777"
    ]
    
    # Calculate old format storage (approximate)
    old_storage_per_id = sum(len(id_str.encode('utf-8')) for id_str in sample_ids) / len(sample_ids)
    
    # New format storage
    new_storage_per_id = 8  # BIGINT is 8 bytes
    
    savings_per_id = old_storage_per_id - new_storage_per_id
    savings_percentage = (savings_per_id / old_storage_per_id) * 100
    
    print(f"  Average old format storage: {old_storage_per_id:.1f} bytes per ID")
    print(f"  New format storage: {new_storage_per_id} bytes per ID")
    print(f"  Savings per ID: {savings_per_id:.1f} bytes ({savings_percentage:.1f}%)")
    
    # Extrapolate to larger datasets
    for num_records in [1_000_000, 10_000_000, 100_000_000]:
        old_total = num_records * old_storage_per_id
        new_total = num_records * new_storage_per_id
        savings_mb = (old_total - new_total) / (1024 * 1024)
        
        print(f"  {num_records:,} records: saves ~{savings_mb:.1f} MB")
    
    assert savings_percentage > 70, f"Expected >70% savings, got {savings_percentage:.1f}%"
    
    print("✓ Storage efficiency calculations confirm significant savings")
    return True


def main():
    """Run all tests"""
    print("Running OpenAlex ID optimization tests...\n")
    
    tests = [
        test_openalex_id_extraction,
        test_csv_output_numeric_ids,
        test_importer_conversion,
        test_row_validation_with_numeric_ids,
        test_storage_efficiency
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} failed with error: {e}")
        print()
    
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! OpenAlex ID optimization is working correctly.")
        print("\nNext steps:")
        print("1. Run the database migration: python db/run_migration.py --migration 002")
        print("2. Update existing data extraction workflows")
        print("3. Monitor storage usage and query performance improvements")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
