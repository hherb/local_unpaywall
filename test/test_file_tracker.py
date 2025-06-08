#!/usr/bin/env python3
"""
Unit tests for the FileTracker module.

Tests the SQLite-based file tracking system including:
- Database initialization
- File hash calculation
- Processing status tracking
- Change detection
- Statistics and cleanup operations
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.file_tracker import FileTracker


class TestFileTracker(unittest.TestCase):
    """Test cases for FileTracker class."""
    
    def setUp(self):
        """Set up test environment with temporary database and files."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tracking.db")
        self.tracker = FileTracker(self.db_path)
        
        # Create test files
        self.test_file1 = os.path.join(self.temp_dir, "test1.txt")
        self.test_file2 = os.path.join(self.temp_dir, "test2.txt")
        
        with open(self.test_file1, 'w') as f:
            f.write("Test content 1")
        
        with open(self.test_file2, 'w') as f:
            f.write("Test content 2")
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_database_initialization(self):
        """Test that database is properly initialized."""
        self.assertTrue(Path(self.db_path).exists())
        
        # Check that tables exist
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='processed_files'
            """)
            self.assertIsNotNone(cursor.fetchone())
    
    def test_file_hash_calculation(self):
        """Test file hash and size calculation."""
        hash_val, size = self.tracker._calculate_file_hash(self.test_file1)
        
        self.assertIsInstance(hash_val, str)
        self.assertEqual(len(hash_val), 64)  # SHA-256 hex length
        self.assertEqual(size, 14)  # Length of "Test content 1"
    
    def test_file_hash_consistency(self):
        """Test that hash calculation is consistent."""
        hash1, size1 = self.tracker._calculate_file_hash(self.test_file1)
        hash2, size2 = self.tracker._calculate_file_hash(self.test_file1)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(size1, size2)
    
    def test_needs_processing_new_file(self):
        """Test that new files need processing."""
        self.assertTrue(self.tracker.needs_processing(self.test_file1))
    
    def test_needs_processing_nonexistent_file(self):
        """Test handling of nonexistent files."""
        nonexistent = os.path.join(self.temp_dir, "nonexistent.txt")
        self.assertFalse(self.tracker.needs_processing(nonexistent))
    
    def test_mark_completed_and_check(self):
        """Test marking file as completed and checking status."""
        # Initially needs processing
        self.assertTrue(self.tracker.needs_processing(self.test_file1))
        
        # Mark as completed
        stats = {"records_processed": 100, "errors": 0}
        self.tracker.mark_completed(self.test_file1, stats)
        
        # Should no longer need processing
        self.assertFalse(self.tracker.needs_processing(self.test_file1))
    
    def test_file_change_detection(self):
        """Test that file changes are detected."""
        # Mark as completed
        self.tracker.mark_completed(self.test_file1)
        self.assertFalse(self.tracker.needs_processing(self.test_file1))
        
        # Modify file
        with open(self.test_file1, 'w') as f:
            f.write("Modified content")
        
        # Should need processing again
        self.assertTrue(self.tracker.needs_processing(self.test_file1))
    
    def test_processing_stats_storage(self):
        """Test that processing statistics are stored correctly."""
        stats = {
            "records_processed": 1000,
            "errors": 5,
            "processing_time": 45.2
        }
        
        self.tracker.mark_completed(self.test_file1, stats)
        
        processed_files = self.tracker.get_processed_files()
        self.assertEqual(len(processed_files), 1)
        
        stored_stats = processed_files[0]['processing_stats']
        self.assertEqual(stored_stats, stats)
    
    def test_get_processed_files(self):
        """Test retrieval of processed files list."""
        # Mark multiple files as completed
        self.tracker.mark_completed(self.test_file1, {"records": 100})
        self.tracker.mark_completed(self.test_file2, {"records": 200})
        
        processed_files = self.tracker.get_processed_files()
        self.assertEqual(len(processed_files), 2)
        
        # Check that all required fields are present
        for file_info in processed_files:
            self.assertIn('file_path', file_info)
            self.assertIn('file_hash', file_info)
            self.assertIn('file_size', file_info)
            self.assertIn('completion_date', file_info)
            self.assertIn('processing_stats', file_info)
    
    def test_get_processing_summary(self):
        """Test processing summary statistics."""
        # Initially empty
        summary = self.tracker.get_processing_summary()
        self.assertEqual(summary['total_files'], 0)
        self.assertEqual(summary['total_size_bytes'], 0)
        
        # Add some files
        self.tracker.mark_completed(self.test_file1)
        self.tracker.mark_completed(self.test_file2)
        
        summary = self.tracker.get_processing_summary()
        self.assertEqual(summary['total_files'], 2)
        self.assertGreater(summary['total_size_bytes'], 0)
        self.assertIsNotNone(summary['first_processed'])
        self.assertIsNotNone(summary['last_processed'])
    
    def test_remove_file_record(self):
        """Test removal of file records."""
        # Mark file as completed
        self.tracker.mark_completed(self.test_file1)
        self.assertFalse(self.tracker.needs_processing(self.test_file1))
        
        # Remove record
        removed = self.tracker.remove_file_record(self.test_file1)
        self.assertTrue(removed)
        
        # Should need processing again
        self.assertTrue(self.tracker.needs_processing(self.test_file1))
        
        # Try to remove again
        removed = self.tracker.remove_file_record(self.test_file1)
        self.assertFalse(removed)
    
    def test_cleanup_missing_files(self):
        """Test cleanup of records for missing files."""
        # Mark files as completed
        self.tracker.mark_completed(self.test_file1)
        self.tracker.mark_completed(self.test_file2)
        
        # Remove one file from disk
        os.remove(self.test_file1)
        
        # Cleanup should remove one record
        removed_count = self.tracker.cleanup_missing_files()
        self.assertEqual(removed_count, 1)
        
        # Only one file should remain in database
        processed_files = self.tracker.get_processed_files()
        self.assertEqual(len(processed_files), 1)
        self.assertEqual(processed_files[0]['file_path'], str(Path(self.test_file2).resolve()))
    
    def test_upsert_behavior(self):
        """Test that marking the same file multiple times updates the record."""
        # Mark file as completed first time
        stats1 = {"records": 100}
        self.tracker.mark_completed(self.test_file1, stats1)
        
        # Mark again with different stats
        stats2 = {"records": 150}
        self.tracker.mark_completed(self.test_file1, stats2)
        
        # Should have only one record with updated stats
        processed_files = self.tracker.get_processed_files()
        self.assertEqual(len(processed_files), 1)
        self.assertEqual(processed_files[0]['processing_stats'], stats2)


if __name__ == '__main__':
    unittest.main()
