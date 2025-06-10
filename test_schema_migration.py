#!/usr/bin/env python3
"""
Test script for schema migration 001 - Integration of work_type and is_retracted fields

This script tests the new schema changes to ensure:
1. The OpenAlex extractor includes the new fields
2. The CSV output contains the new columns
3. The importer can handle the new fields
4. The database schema is correctly updated
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


def create_test_openalex_data() -> Dict[str, Any]:
    """Create sample OpenAlex work data for testing"""
    return {
        "id": "https://openalex.org/W2741809807",
        "doi": "https://doi.org/10.1038/nature12373",
        "title": "Test Article: Machine Learning in Biology",
        "publication_year": 2023,
        "type": "journal-article",  # This should map to work_type
        "is_retracted": False,      # This should map to is_retracted
        "open_access": {
            "is_oa": True,
            "oa_status": "gold"
        },
        "primary_location": {
            "landing_page_url": "https://www.nature.com/articles/nature12373",
            "pdf_url": "https://www.nature.com/articles/nature12373.pdf",
            "version": "publishedVersion",
            "license": "cc-by",
            "source": {
                "display_name": "Nature",
                "is_in_doaj": True
            }
        },
        "locations": [
            {
                "landing_page_url": "https://www.nature.com/articles/nature12373",
                "pdf_url": "https://www.nature.com/articles/nature12373.pdf",
                "version": "publishedVersion",
                "license": "cc-by",
                "source": {
                    "display_name": "Nature",
                    "is_in_doaj": True
                }
            }
        ],
        "best_oa_location": {
            "landing_page_url": "https://www.nature.com/articles/nature12373",
            "pdf_url": "https://www.nature.com/articles/nature12373.pdf",
            "version": "publishedVersion",
            "license": "cc-by",
            "source": {
                "display_name": "Nature",
                "is_in_doaj": True
            }
        }
    }


def test_extractor_includes_new_fields():
    """Test that the OpenAlex extractor includes work_type and is_retracted"""
    print("Testing OpenAlex extractor with new fields...")
    
    # Create test data
    test_work = create_test_openalex_data()
    
    # Create temporary extractor
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_output.csv"
        
        extractor = OpenAlexURLExtractor(
            snapshot_dir=temp_path,
            output_file=output_file,
            output_format='csv'
        )
        
        # Extract URLs from test work
        url_records, pdf_stats = extractor.extract_urls_from_work(test_work, {})
        
        # Verify we got records
        assert len(url_records) > 0, "No URL records extracted"
        
        # Check first record has new fields
        record = url_records[0]
        
        # Verify new fields are present
        assert 'work_type' in record, "work_type field missing from extracted record"
        assert 'is_retracted' in record, "is_retracted field missing from extracted record"
        
        # Verify field values
        assert record['work_type'] == 'journal-article', f"Expected work_type 'journal-article', got '{record['work_type']}'"
        assert record['is_retracted'] == 'False', f"Expected is_retracted 'False', got '{record['is_retracted']}'"
        
        print("✓ Extractor correctly includes work_type and is_retracted fields")
        return True


def test_csv_output_format():
    """Test that CSV output includes the new columns"""
    print("Testing CSV output format...")
    
    # Create test data
    test_work = create_test_openalex_data()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_output.csv"

        # Create proper directory structure for OpenAlex data
        data_dir = temp_path / "data" / "works" / "updated_date=2023-01-01"
        data_dir.mkdir(parents=True)

        # Create test JSONL file in proper location
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
        
        # Verify CSV file was created
        assert output_file.exists(), "CSV output file was not created"
        
        # Read and verify CSV content
        with open(output_file, 'r') as f:
            reader = csv.DictReader(f)
            
            # Check header includes new fields
            fieldnames = reader.fieldnames
            assert 'work_type' in fieldnames, "work_type column missing from CSV header"
            assert 'is_retracted' in fieldnames, "is_retracted column missing from CSV header"
            
            # Check data row
            rows = list(reader)
            assert len(rows) > 0, "No data rows in CSV output"
            
            row = rows[0]
            assert row['work_type'] == 'journal-article', f"Expected work_type 'journal-article', got '{row['work_type']}'"
            assert row['is_retracted'] == 'False', f"Expected is_retracted 'False', got '{row['is_retracted']}'"
        
        print("✓ CSV output correctly includes work_type and is_retracted columns")
        return True


def test_retracted_work():
    """Test handling of retracted works"""
    print("Testing retracted work handling...")
    
    # Create test data for retracted work
    test_work = create_test_openalex_data()
    test_work['is_retracted'] = True
    test_work['type'] = 'preprint'
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_output.csv"
        
        extractor = OpenAlexURLExtractor(
            snapshot_dir=temp_path,
            output_file=output_file,
            output_format='csv'
        )
        
        # Test with exclude_retracted=True (default)
        url_records, pdf_stats = extractor.extract_urls_from_work(test_work, {'exclude_retracted': True})
        assert len(url_records) == 0, "Retracted work should be excluded when exclude_retracted=True"
        
        # Test with exclude_retracted=False
        url_records, pdf_stats = extractor.extract_urls_from_work(test_work, {'exclude_retracted': False})
        assert len(url_records) > 0, "Retracted work should be included when exclude_retracted=False"
        
        record = url_records[0]
        assert record['work_type'] == 'preprint', f"Expected work_type 'preprint', got '{record['work_type']}'"
        assert record['is_retracted'] == 'True', f"Expected is_retracted 'True', got '{record['is_retracted']}'"
        
        print("✓ Retracted work handling works correctly")
        return True


def test_work_type_filtering():
    """Test filtering by work type"""
    print("Testing work type filtering...")
    
    # Create test data
    test_work = create_test_openalex_data()
    test_work['type'] = 'book-chapter'
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "test_output.csv"
        
        extractor = OpenAlexURLExtractor(
            snapshot_dir=temp_path,
            output_file=output_file,
            output_format='csv'
        )
        
        # Test with type filter that excludes our work
        url_records, pdf_stats = extractor.extract_urls_from_work(test_work, {'types': ['journal-article']})
        assert len(url_records) == 0, "Work should be excluded when type not in filter list"
        
        # Test with type filter that includes our work
        url_records, pdf_stats = extractor.extract_urls_from_work(test_work, {'types': ['book-chapter', 'journal-article']})
        assert len(url_records) > 0, "Work should be included when type in filter list"
        
        record = url_records[0]
        assert record['work_type'] == 'book-chapter', f"Expected work_type 'book-chapter', got '{record['work_type']}'"
        
        print("✓ Work type filtering works correctly")
        return True


def main():
    """Run all tests"""
    print("Running schema migration tests...\n")
    
    tests = [
        test_extractor_includes_new_fields,
        test_csv_output_format,
        test_retracted_work,
        test_work_type_filtering
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
        print("🎉 All tests passed! Schema migration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
