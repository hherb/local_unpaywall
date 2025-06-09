#!/usr/bin/env python3
"""
Test suite for DOI URL Importer Resume Functionality
"""

import unittest
import tempfile
import os
import csv
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from doi_url_importer import DOIURLImporter


class TestDOIURLImporterResume(unittest.TestCase):
    """Test resume functionality of DOI URL Importer"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.csv_file = Path(self.temp_dir) / "test_dois.csv"
        
        # Create test CSV file
        self.create_test_csv()
        
        # Mock database config
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_pass'
        }

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_csv(self):
        """Create a test CSV file with sample data"""
        test_data = [
            {
                'doi': '10.1000/test1',
                'url': 'https://example.com/paper1',
                'pdf_url': 'https://example.com/paper1.pdf',
                'location_type': 'primary',
                'is_oa': 'true',
                'title': 'Test Paper 1'
            },
            {
                'doi': '10.1000/test2',
                'url': 'https://example.com/paper2',
                'pdf_url': '',
                'location_type': 'alternate',
                'is_oa': 'false',
                'title': 'Test Paper 2'
            },
            {
                'doi': '10.1000/test3',
                'url': 'https://example.com/paper3',
                'pdf_url': 'https://example.com/paper3.pdf',
                'location_type': 'best_oa',
                'is_oa': 'true',
                'title': 'Test Paper 3'
            }
        ]
        
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=test_data[0].keys())
            writer.writeheader()
            writer.writerows(test_data)

    def test_file_hash_calculation(self):
        """Test that file hash calculation is consistent"""
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        hash1 = importer._calculate_file_hash()
        hash2 = importer._calculate_file_hash()
        
        self.assertEqual(hash1, hash2, "File hash should be consistent")
        self.assertEqual(len(hash1), 64, "SHA-256 hash should be 64 characters")

    def test_csv_row_counting(self):
        """Test CSV row counting functionality"""
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        row_count = importer._count_csv_rows()
        self.assertEqual(row_count, 3, "Should count 3 data rows (excluding header)")

    def test_import_id_generation(self):
        """Test import ID generation"""
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        id1 = importer._generate_import_id()
        id2 = importer._generate_import_id()
        
        self.assertNotEqual(id1, id2, "Import IDs should be unique")
        self.assertTrue(id1.startswith("test_dois_"), "Import ID should start with filename")

    @patch('doi_url_importer.psycopg2')
    def test_check_existing_import(self, mock_psycopg2):
        """Test checking for existing incomplete imports"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock existing import record
        mock_cursor.fetchone.return_value = {
            'import_id': 'test_import_123',
            'csv_file_hash': 'abc123',
            'processed_rows': 100,
            'total_rows': 1000
        }
        
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=True
        )
        
        result = importer._check_existing_import()
        
        self.assertIsNotNone(result, "Should find existing import")
        self.assertEqual(result['import_id'], 'test_import_123')

    @patch('doi_url_importer.psycopg2')
    def test_create_import_record(self, mock_psycopg2):
        """Test creating new import progress record"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        # Set required attributes
        importer.csv_file_hash = "test_hash"
        importer.total_csv_rows = 100
        
        import_id = importer._create_import_record()
        
        self.assertIsNotNone(import_id, "Should return import ID")
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('doi_url_importer.psycopg2')
    def test_update_import_progress(self, mock_psycopg2):
        """Test updating import progress"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        importer.import_id = "test_import_123"
        
        importer._update_import_progress(processed_rows=50, batch_id=5)
        
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch('doi_url_importer.psycopg2')
    def test_complete_import_success(self, mock_psycopg2):
        """Test marking import as completed successfully"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        importer.import_id = "test_import_123"
        
        importer._complete_import(success=True)
        
        # Verify the SQL call
        args, kwargs = mock_cursor.execute.call_args
        self.assertIn('completed', args[1])  # Status should be 'completed'
        self.assertIsNone(args[1][1])  # Error message should be None

    @patch('doi_url_importer.psycopg2')
    def test_complete_import_failure(self, mock_psycopg2):
        """Test marking import as failed"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=10,
            create_tables=False,
            resume=False
        )
        
        importer.import_id = "test_import_123"
        error_msg = "Test error message"
        
        importer._complete_import(success=False, error_message=error_msg)
        
        # Verify the SQL call
        args, kwargs = mock_cursor.execute.call_args
        self.assertIn('failed', args[1])  # Status should be 'failed'
        self.assertEqual(args[1][1], error_msg)  # Error message should match

    def test_csv_reading_with_resume(self):
        """Test CSV reading with resume functionality"""
        importer = DOIURLImporter(
            db_config=self.db_config,
            csv_file=str(self.csv_file),
            batch_size=2,  # Small batch size for testing
            create_tables=False,
            resume=False
        )
        
        # Set start row to skip first row
        importer.start_row = 1
        
        batches = list(importer.read_csv_in_batches())
        
        # Should have 2 batches: [row2, row3] and []
        self.assertEqual(len(batches), 1, "Should have 1 batch when starting from row 1")
        
        batch_data, current_row = batches[0]
        self.assertEqual(len(batch_data), 2, "First batch should have 2 rows")
        self.assertEqual(current_row, 3, "Current row should be 3 after processing 2 rows")


if __name__ == '__main__':
    unittest.main()
