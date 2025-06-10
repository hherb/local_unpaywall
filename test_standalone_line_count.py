#!/usr/bin/env python3
"""
Test script to verify the standalone count_lines_fast function works correctly.
"""

import tempfile
import csv
from pathlib import Path
from helpers.csv_utils import count_lines_fast


def create_test_csv(filename: str, num_rows: int = 50000):
    """Create a test CSV file."""
    print(f"Creating test CSV with {num_rows:,} rows...")
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['id', 'name', 'email', 'value'])
        
        # Write data rows
        for i in range(num_rows):
            writer.writerow([
                i + 1,
                f'User {i + 1}',
                f'user{i + 1}@example.com',
                f'Value {i + 1}'
            ])
    
    file_size = Path(filename).stat().st_size
    print(f"Created {filename} ({file_size / 1024 / 1024:.1f} MB)")


def test_standalone_function():
    """Test the standalone count_lines_fast function."""
    
    print(f"\n{'='*60}")
    print("Testing Standalone count_lines_fast Function")
    print(f"{'='*60}")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Create test file
        create_test_csv(tmp_path, 50000)
        
        # Test with progress bar (default)
        print(f"\n1. Testing with progress bar (default):")
        line_count_with_progress = count_lines_fast(tmp_path)
        print(f"   Lines counted: {line_count_with_progress:,}")
        
        # Test without progress bar
        print(f"\n2. Testing without progress bar:")
        line_count_no_progress = count_lines_fast(tmp_path, show_progress=False)
        print(f"   Lines counted: {line_count_no_progress:,}")
        
        # Test with Path object
        print(f"\n3. Testing with Path object:")
        line_count_path = count_lines_fast(Path(tmp_path), show_progress=False)
        print(f"   Lines counted: {line_count_path:,}")
        
        # Verify all methods give same result
        if line_count_with_progress == line_count_no_progress == line_count_path:
            print(f"\n   ✅ All methods agree on line count: {line_count_with_progress:,}")
            print(f"   📊 Expected: 50,001 lines (50,000 data + 1 header)")
            
            if line_count_with_progress == 50001:
                print(f"   ✅ Line count is correct!")
            else:
                print(f"   ❌ Line count mismatch! Expected 50,001, got {line_count_with_progress}")
        else:
            print(f"   ❌ Methods disagree!")
            print(f"      With progress: {line_count_with_progress}")
            print(f"      Without progress: {line_count_no_progress}")
            print(f"      With Path: {line_count_path}")
        
    finally:
        # Clean up
        Path(tmp_path).unlink(missing_ok=True)


def test_error_handling():
    """Test error handling for the standalone function."""
    
    print(f"\n{'='*60}")
    print("Testing Error Handling")
    print(f"{'='*60}")
    
    # Test with non-existent file
    print(f"\n1. Testing with non-existent file:")
    try:
        count_lines_fast("non_existent_file.csv")
        print(f"   ❌ Should have raised FileNotFoundError")
    except FileNotFoundError as e:
        print(f"   ✅ Correctly raised FileNotFoundError: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    # Test with empty file
    print(f"\n2. Testing with empty file:")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # File is empty
        line_count = count_lines_fast(tmp_path, show_progress=False)
        print(f"   ✅ Empty file line count: {line_count}")
        
        if line_count == 0:
            print(f"   ✅ Correctly returned 0 for empty file")
        else:
            print(f"   ❌ Expected 0, got {line_count}")
            
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_integration_with_doi_importer():
    """Test that the doi_url_importer can use the fast line counting."""
    
    print(f"\n{'='*60}")
    print("Testing Integration with DOI URL Importer")
    print(f"{'='*60}")
    
    # Create a test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Create a small CSV file for testing
        create_test_csv(tmp_path, 1000)
        
        # Test importing the function (simulating what doi_url_importer does)
        print(f"\n1. Testing import and usage:")
        from helpers.csv_utils import count_lines_fast
        
        line_count = count_lines_fast(tmp_path, show_progress=False)
        csv_rows = line_count - 1  # Subtract header like the importer does
        
        print(f"   Total lines: {line_count:,}")
        print(f"   CSV rows (excluding header): {csv_rows:,}")
        print(f"   Expected CSV rows: 1,000")
        
        if csv_rows == 1000:
            print(f"   ✅ Integration test passed!")
        else:
            print(f"   ❌ Expected 1,000 rows, got {csv_rows}")
        
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == '__main__':
    print("🚀 Testing Standalone count_lines_fast Function")
    print("=" * 60)
    
    test_standalone_function()
    test_error_handling()
    test_integration_with_doi_importer()
    
    print(f"\n{'='*60}")
    print("✅ All standalone function tests completed!")
    print(f"{'='*60}")
    print("\n💡 Usage examples:")
    print("   from helpers.csv_utils import count_lines_fast")
    print("   ")
    print("   # Count lines with progress bar")
    print("   line_count = count_lines_fast('large_file.csv')")
    print("   ")
    print("   # Count lines without progress bar")
    print("   line_count = count_lines_fast('file.csv', show_progress=False)")
    print("   ")
    print("   # Works with Path objects too")
    print("   line_count = count_lines_fast(Path('file.csv'))")
