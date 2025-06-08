#!/usr/bin/env python3
"""
Unit Tests for Memory-Efficient CSV Processing
==============================================

Tests for the helpers/csv_utils module.

Usage:
    python -m test.test_csv_utils
"""

import csv
import tempfile
import unittest
from pathlib import Path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.csv_utils import CSVBatchProcessor, process_csv_in_batches


class TestCSVBatchProcessor(unittest.TestCase):
    """Test cases for CSVBatchProcessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_data = [
            {'id': '1', 'name': 'Alice', 'email': 'alice@example.com', 'age': '25'},
            {'id': '2', 'name': 'Bob', 'email': 'bob@example.com', 'age': '30'},
            {'id': '3', 'name': 'Charlie', 'email': 'invalid-email', 'age': '35'},
            {'id': '4', 'name': 'Diana', 'email': 'diana@example.com', 'age': '28'},
            {'id': '5', 'name': 'Eve', 'email': '', 'age': '22'},
        ]
        
        # Create temporary CSV file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        fieldnames = ['id', 'name', 'email', 'age']
        writer = csv.DictWriter(self.temp_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(self.test_data)
        self.temp_file.close()
        
        self.csv_file = self.temp_file.name
    
    def tearDown(self):
        """Clean up test fixtures."""
        Path(self.csv_file).unlink(missing_ok=True)
    
    def test_basic_processing(self):
        """Test basic CSV processing without validation."""
        processor = CSVBatchProcessor(self.csv_file, batch_size=2, show_progress=False)
        
        batches = list(processor.process_batches())
        
        # Should have 3 batches: [2, 2, 1] rows
        self.assertEqual(len(batches), 3)
        self.assertEqual(len(batches[0]), 2)
        self.assertEqual(len(batches[1]), 2)
        self.assertEqual(len(batches[2]), 1)
        
        # Check total rows
        total_rows = sum(len(batch) for batch in batches)
        self.assertEqual(total_rows, len(self.test_data))
        
        # Check stats
        stats = processor.get_stats()
        self.assertEqual(stats['total_rows_processed'], len(self.test_data))
        self.assertEqual(stats['rows_valid'], len(self.test_data))
        self.assertEqual(stats['rows_skipped'], 0)
        self.assertEqual(stats['batches_yielded'], 3)
    
    def test_with_validation(self):
        """Test CSV processing with validation function."""
        def email_validator(row):
            """Only keep rows with valid email addresses."""
            email = row.get('email', '').strip()
            if email and '@' in email:
                return {
                    'id': int(row['id']),
                    'name': row['name'],
                    'email': email.lower(),
                    'age': int(row['age'])
                }
            return None
        
        processor = CSVBatchProcessor(
            self.csv_file, 
            batch_size=2, 
            validator=email_validator,
            show_progress=False
        )
        
        batches = list(processor.process_batches())
        
        # Should filter out 2 invalid emails (Charlie and Eve)
        total_valid_rows = sum(len(batch) for batch in batches)
        self.assertEqual(total_valid_rows, 3)  # Alice, Bob, Diana
        
        # Check stats
        stats = processor.get_stats()
        self.assertEqual(stats['total_rows_processed'], 5)
        self.assertEqual(stats['rows_valid'], 3)
        self.assertEqual(stats['rows_skipped'], 2)
        
        # Check data transformation
        all_rows = [row for batch in batches for row in batch]
        self.assertTrue(all(isinstance(row['id'], int) for row in all_rows))
        self.assertTrue(all('@' in row['email'] for row in all_rows))
    
    def test_empty_file(self):
        """Test handling of empty CSV file."""
        # Create empty file
        empty_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        empty_file.close()
        
        try:
            processor = CSVBatchProcessor(empty_file.name, show_progress=False)
            with self.assertRaises(ValueError):
                list(processor.process_batches())
        finally:
            Path(empty_file.name).unlink(missing_ok=True)
    
    def test_header_only_file(self):
        """Test handling of CSV file with only header."""
        # Create file with only header
        header_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        writer = csv.DictWriter(header_file, fieldnames=['id', 'name'])
        writer.writeheader()
        header_file.close()
        
        try:
            processor = CSVBatchProcessor(header_file.name, show_progress=False)
            with self.assertRaises(ValueError):
                list(processor.process_batches())
        finally:
            Path(header_file.name).unlink(missing_ok=True)
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent file."""
        processor = CSVBatchProcessor('nonexistent.csv', show_progress=False)
        with self.assertRaises(FileNotFoundError):
            list(processor.process_batches())
    
    def test_different_delimiters(self):
        """Test automatic delimiter detection."""
        # Create TSV file
        tsv_file = tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False)
        tsv_file.write("id\tname\temail\n")
        tsv_file.write("1\tAlice\talice@example.com\n")
        tsv_file.write("2\tBob\tbob@example.com\n")
        tsv_file.close()
        
        try:
            processor = CSVBatchProcessor(tsv_file.name, batch_size=10, show_progress=False)
            batches = list(processor.process_batches())
            
            self.assertEqual(len(batches), 1)
            self.assertEqual(len(batches[0]), 2)
            self.assertEqual(batches[0][0]['name'], 'Alice')
            self.assertEqual(batches[0][1]['name'], 'Bob')
        finally:
            Path(tsv_file.name).unlink(missing_ok=True)


class TestConvenienceFunction(unittest.TestCase):
    """Test cases for the convenience function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_data = [
            {'id': '1', 'value': 'A'},
            {'id': '2', 'value': 'B'},
            {'id': '3', 'value': 'C'},
        ]
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        writer = csv.DictWriter(self.temp_file, fieldnames=['id', 'value'])
        writer.writeheader()
        writer.writerows(self.test_data)
        self.temp_file.close()
        
        self.csv_file = self.temp_file.name
    
    def tearDown(self):
        """Clean up test fixtures."""
        Path(self.csv_file).unlink(missing_ok=True)
    
    def test_convenience_function(self):
        """Test the process_csv_in_batches convenience function."""
        batches = list(process_csv_in_batches(
            self.csv_file, 
            batch_size=2, 
            show_progress=False
        ))
        
        self.assertEqual(len(batches), 2)  # [2, 1] rows
        self.assertEqual(len(batches[0]), 2)
        self.assertEqual(len(batches[1]), 1)
        
        # Check data integrity
        all_rows = [row for batch in batches for row in batch]
        self.assertEqual(len(all_rows), 3)
        self.assertEqual(all_rows[0]['id'], '1')
        self.assertEqual(all_rows[2]['value'], 'C')
    
    def test_with_validator(self):
        """Test convenience function with validator."""
        def uppercase_validator(row):
            return {
                'id': int(row['id']),
                'value': row['value'].upper()
            }
        
        batches = list(process_csv_in_batches(
            self.csv_file,
            batch_size=10,
            validator=uppercase_validator,
            show_progress=False
        ))
        
        self.assertEqual(len(batches), 1)
        all_rows = batches[0]
        
        self.assertTrue(all(isinstance(row['id'], int) for row in all_rows))
        self.assertEqual(all_rows[0]['value'], 'A')
        self.assertEqual(all_rows[1]['value'], 'B')
        self.assertEqual(all_rows[2]['value'], 'C')


def run_tests():
    """Run all tests."""
    print("Running CSV Utils Tests")
    print("=" * 30)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCSVBatchProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestConvenienceFunction))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 30)
    if result.wasSuccessful():
        print("✓ All tests passed!")
    else:
        print(f"✗ {len(result.failures)} failures, {len(result.errors)} errors")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
