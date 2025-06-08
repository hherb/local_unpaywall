#!/usr/bin/env python3
"""
Integration test for the enhanced OpenAlex extractor with file tracking.

This test verifies that the file tracking system works correctly with
the OpenAlex URL extractor.
"""

import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openalex_unpaywall_extractor import OpenAlexURLExtractor


class TestExtractorIntegration(unittest.TestCase):
    """Test integration between extractor and file tracker."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = os.path.join(self.temp_dir, "openalex-snapshot")
        self.works_dir = os.path.join(self.snapshot_dir, "data", "works", "updated_date=2024-01-01")
        os.makedirs(self.works_dir, exist_ok=True)
        
        self.output_file = os.path.join(self.temp_dir, "test_output.csv")
        
        # Create a test works file with sample data
        self.test_works_file = os.path.join(self.works_dir, "part_000.gz")
        self._create_test_works_file()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_works_file(self):
        """Create a test works file with sample OpenAlex data."""
        sample_works = [
            {
                "id": "https://openalex.org/W2741809807",
                "doi": "https://doi.org/10.1038/nature12373",
                "title": "Test Article 1",
                "publication_year": 2023,
                "open_access": {
                    "is_oa": True,
                    "oa_status": "gold"
                },
                "primary_location": {
                    "landing_page_url": "https://www.nature.com/articles/nature12373",
                    "pdf_url": "https://www.nature.com/articles/nature12373.pdf",
                    "version": "publishedVersion",
                    "license": "cc-by"
                },
                "locations": [],
                "best_oa_location": None
            },
            {
                "id": "https://openalex.org/W2741809808",
                "doi": "https://doi.org/10.1126/science.1234567",
                "title": "Test Article 2",
                "publication_year": 2023,
                "open_access": {
                    "is_oa": False,
                    "oa_status": "closed"
                },
                "primary_location": {
                    "landing_page_url": "https://science.sciencemag.org/content/123/456/789",
                    "pdf_url": None,
                    "version": "publishedVersion",
                    "license": None
                },
                "locations": [],
                "best_oa_location": None
            }
        ]
        
        with gzip.open(self.test_works_file, 'wt', encoding='utf-8') as f:
            for work in sample_works:
                f.write(json.dumps(work) + '\n')
    
    def test_initial_processing(self):
        """Test initial processing of files."""
        extractor = OpenAlexURLExtractor(
            snapshot_dir=self.snapshot_dir,
            output_file=self.output_file,
            output_format='csv',
            resume=False
        )
        
        # Should need processing initially
        self.assertTrue(extractor.file_tracker.needs_processing(self.test_works_file))
        
        # Run extraction
        extractor.extract_urls()
        
        # Should no longer need processing
        self.assertFalse(extractor.file_tracker.needs_processing(self.test_works_file))
        
        # Check that output file was created
        self.assertTrue(Path(self.output_file).exists())
        
        # Check tracking database
        summary = extractor.file_tracker.get_processing_summary()
        self.assertEqual(summary['total_files'], 1)
        self.assertGreater(summary['total_size_bytes'], 0)
    
    def test_resume_unchanged_file(self):
        """Test that unchanged files are skipped on resume."""
        # First run
        extractor1 = OpenAlexURLExtractor(
            snapshot_dir=self.snapshot_dir,
            output_file=self.output_file,
            output_format='csv',
            resume=False
        )
        extractor1.extract_urls()
        
        # Second run with resume
        extractor2 = OpenAlexURLExtractor(
            snapshot_dir=self.snapshot_dir,
            output_file=self.output_file,
            output_format='csv',
            resume=True
        )
        
        # Should not need processing
        self.assertFalse(extractor2.file_tracker.needs_processing(self.test_works_file))
        
        # Run extraction - should skip the file
        extractor2.extract_urls()
        
        # Check that file was skipped
        self.assertEqual(extractor2.stats['files_skipped'], 1)
        self.assertEqual(extractor2.stats['files_processed'], 0)
    
    def test_resume_changed_file(self):
        """Test that changed files are reprocessed on resume."""
        # First run
        extractor1 = OpenAlexURLExtractor(
            snapshot_dir=self.snapshot_dir,
            output_file=self.output_file,
            output_format='csv',
            resume=False
        )
        extractor1.extract_urls()
        
        # Modify the file
        with gzip.open(self.test_works_file, 'wt', encoding='utf-8') as f:
            work = {
                "id": "https://openalex.org/W2741809809",
                "doi": "https://doi.org/10.1038/nature99999",
                "title": "Modified Test Article",
                "publication_year": 2024,
                "open_access": {"is_oa": True, "oa_status": "gold"},
                "primary_location": {
                    "landing_page_url": "https://www.nature.com/articles/nature99999",
                    "pdf_url": "https://www.nature.com/articles/nature99999.pdf"
                },
                "locations": [],
                "best_oa_location": None
            }
            f.write(json.dumps(work) + '\n')
        
        # Second run with resume
        extractor2 = OpenAlexURLExtractor(
            snapshot_dir=self.snapshot_dir,
            output_file=self.output_file,
            output_format='csv',
            resume=True
        )
        
        # Should need processing due to change
        self.assertTrue(extractor2.file_tracker.needs_processing(self.test_works_file))
        
        # Run extraction - should process the file
        extractor2.extract_urls()
        
        # Check that file was processed
        self.assertEqual(extractor2.stats['files_skipped'], 0)
        self.assertEqual(extractor2.stats['files_processed'], 1)


if __name__ == '__main__':
    unittest.main()
