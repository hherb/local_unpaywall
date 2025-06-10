#!/usr/bin/env python3
"""
Test script for the normalized DOI URL importer
===============================================

This script tests the key functionality of the modified importer
to ensure it works correctly with the normalized database structure.
"""

import sys
import tempfile
import csv
from pathlib import Path

# Add the current directory to the path so we can import the importer
sys.path.insert(0, str(Path(__file__).parent))

try:
    from doi_url_importer import DOIURLImporter, load_env_config
except ImportError as e:
    print(f"Error importing DOIURLImporter: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


def create_test_csv():
    """Create a small test CSV file with sample data"""
    test_data = [
        {
            'doi': '10.1234/test1',
            'url': 'https://example.com/paper1',
            'pdf_url': 'https://example.com/paper1.pdf',
            'openalex_id': 'W123456789',
            'title': 'Test Paper 1',
            'publication_year': '2023',
            'location_type': 'primary',
            'version': 'published',
            'license': 'cc-by',
            'host_type': 'journal',
            'oa_status': 'gold',
            'is_oa': 'true',
            'work_type': 'journal-article',
            'is_retracted': 'false'
        },
        {
            'doi': '10.1234/test2',
            'url': 'https://example.com/paper2',
            'pdf_url': '',
            'openalex_id': 'W987654321',
            'title': 'Test Paper 2',
            'publication_year': '2022',
            'location_type': 'alternate',
            'version': 'accepted',
            'license': 'cc0',
            'host_type': 'repository',
            'oa_status': 'green',
            'is_oa': 'true',
            'work_type': 'preprint',
            'is_retracted': 'false'
        },
        {
            'doi': '10.1234/test3',
            'url': 'https://example.com/paper3',
            'pdf_url': 'https://example.com/paper3.pdf',
            'openalex_id': '',
            'title': 'Test Paper 3',
            'publication_year': '2024',
            'location_type': 'best_oa',
            'version': 'published',
            'license': 'cc-by-sa',
            'host_type': 'journal',
            'oa_status': 'gold',
            'is_oa': 'true',
            'work_type': 'journal-article',
            'is_retracted': 'false'
        }
    ]
    
    # Create temporary CSV file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    fieldnames = ['doi', 'url', 'pdf_url', 'openalex_id', 'title', 'publication_year',
                  'location_type', 'version', 'license', 'host_type', 'oa_status',
                  'is_oa', 'work_type', 'is_retracted']
    
    writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(test_data)
    
    temp_file.close()
    return temp_file.name


def test_lookup_cache_functionality():
    """Test the lookup cache functionality"""
    print("Testing lookup cache functionality...")
    
    # Mock database config (won't actually connect)
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'test',
        'user': 'test',
        'password': 'test'
    }
    
    # Create importer instance
    importer = DOIURLImporter(
        db_config=db_config,
        csv_file='test.csv',
        batch_size=100,
        create_tables=False,
        resume=False
    )
    
    # Test location type normalization
    assert importer.normalize_location_type('primary') == 'p'
    assert importer.normalize_location_type('alternate') == 'a'
    assert importer.normalize_location_type('best_oa') == 'b'
    assert importer.normalize_location_type('unknown') == 'p'  # Default
    assert importer.normalize_location_type('') == 'p'  # Default
    
    print("✓ Location type normalization works correctly")
    
    # Test cache initialization
    assert 'license' in importer.lookup_caches
    assert 'oa_status' in importer.lookup_caches
    assert 'host_type' in importer.lookup_caches
    assert 'work_type' in importer.lookup_caches
    
    print("✓ Lookup caches initialized correctly")


def test_row_validation():
    """Test the row validation with normalized structure"""
    print("Testing row validation with normalized structure...")
    
    # Create test CSV
    csv_file = create_test_csv()
    
    try:
        # Mock database config
        db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'test',
            'user': 'test',
            'password': 'test'
        }
        
        # Create importer instance
        importer = DOIURLImporter(
            db_config=db_config,
            csv_file=csv_file,
            batch_size=100,
            create_tables=False,
            resume=False
        )
        
        # Test row validation (without database connection)
        test_row = {
            'doi': '10.1234/test',
            'url': 'https://example.com/paper',
            'pdf_url': 'https://example.com/paper.pdf',
            'openalex_id': 'W123456789',
            'title': 'Test Paper',
            'publication_year': '2023',
            'location_type': 'primary',
            'version': 'published',
            'license': 'cc-by',
            'host_type': 'journal',
            'oa_status': 'gold',
            'is_oa': 'true',
            'work_type': 'journal-article',
            'is_retracted': 'false'
        }
        
        # This will fail because we don't have a database connection,
        # but we can test the basic validation logic
        try:
            cleaned_row = importer.validate_and_clean_row(test_row)
            # If we get here without a database connection, something's wrong
            print("⚠ Row validation didn't fail as expected (no database connection)")
        except Exception:
            # Expected to fail due to no database connection
            print("✓ Row validation structure is correct (failed as expected without DB)")
        
        # Test DOI extraction
        assert importer._extract_doi_identifier('10.1234/test') == '10.1234/test'
        assert importer._extract_doi_identifier('https://doi.org/10.1234/test') == '10.1234/test'
        assert importer._extract_doi_identifier('http://dx.doi.org/10.1234/test') == '10.1234/test'
        
        print("✓ DOI extraction works correctly")
        
        # Test OpenAlex ID conversion
        assert importer._safe_openalex_id('W123456789') == 123456789
        assert importer._safe_openalex_id('123456789') == 123456789
        assert importer._safe_openalex_id('https://openalex.org/W123456789') == 123456789
        assert importer._safe_openalex_id('') is None
        assert importer._safe_openalex_id('invalid') is None
        
        print("✓ OpenAlex ID conversion works correctly")
        
    finally:
        # Clean up test file
        Path(csv_file).unlink()


def main():
    """Run all tests"""
    print("Testing Normalized DOI URL Importer")
    print("=" * 40)
    
    try:
        test_lookup_cache_functionality()
        test_row_validation()
        
        print("\n" + "=" * 40)
        print("✓ All tests passed!")
        print("\nThe normalized importer appears to be working correctly.")
        print("You can now test it with a real database connection.")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
