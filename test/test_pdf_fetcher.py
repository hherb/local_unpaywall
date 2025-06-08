#!/usr/bin/env python3
"""
Unit tests for PDF Fetcher utility.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import requests

# Add parent directory to path to import pdf_fetcher
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_fetcher import PDFFetcher


class TestPDFFetcher(unittest.TestCase):
    """Test cases for PDFFetcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.fetcher = PDFFetcher()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_extract_filename_from_url(self):
        """Test filename extraction from URLs."""
        test_cases = [
            ("https://example.com/paper.pdf", "paper.pdf"),
            ("https://example.com/docs/research.pdf", "research.pdf"),
            ("https://example.com/file.PDF", "file.PDF"),
            ("https://example.com/paper", "downloaded.pdf"),  # No extension
            ("https://example.com/", "downloaded.pdf"),  # No filename
            ("https://example.com/paper.txt", "downloaded.pdf"),  # Wrong extension
            ("https://example.com/path%20with%20spaces/file.pdf", "file.pdf"),  # URL encoded
        ]
        
        for url, expected in test_cases:
            with self.subTest(url=url):
                result = self.fetcher.extract_filename_from_url(url)
                self.assertEqual(result, expected)
    
    def test_validate_pdf_content_valid(self):
        """Test PDF content validation with valid PDF."""
        # Create a temporary file with PDF header
        test_file = self.temp_path / "test.pdf"
        with open(test_file, 'wb') as f:
            f.write(b'%PDF-1.4\n%some pdf content')
        
        result = self.fetcher.validate_pdf_content(test_file)
        self.assertTrue(result)
    
    def test_validate_pdf_content_invalid(self):
        """Test PDF content validation with invalid content."""
        # Create a temporary file with non-PDF content
        test_file = self.temp_path / "test.pdf"
        with open(test_file, 'wb') as f:
            f.write(b'<html><body>Not a PDF</body></html>')
        
        result = self.fetcher.validate_pdf_content(test_file)
        self.assertFalse(result)
    
    def test_validate_pdf_content_nonexistent(self):
        """Test PDF content validation with nonexistent file."""
        test_file = self.temp_path / "nonexistent.pdf"
        result = self.fetcher.validate_pdf_content(test_file)
        self.assertFalse(result)
    
    @patch('pdf_fetcher.requests.Session.head')
    def test_get_file_size_success(self, mock_head):
        """Test successful file size retrieval."""
        # Mock successful response with content-length header
        mock_response = Mock()
        mock_response.headers = {'content-length': '1024'}
        mock_response.raise_for_status.return_value = None
        mock_head.return_value = mock_response
        
        result = self.fetcher.get_file_size("https://example.com/test.pdf")
        self.assertEqual(result, 1024)
    
    @patch('pdf_fetcher.requests.Session.head')
    def test_get_file_size_no_header(self, mock_head):
        """Test file size retrieval when content-length header is missing."""
        # Mock response without content-length header
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.raise_for_status.return_value = None
        mock_head.return_value = mock_response
        
        result = self.fetcher.get_file_size("https://example.com/test.pdf")
        self.assertIsNone(result)
    
    @patch('pdf_fetcher.requests.Session.head')
    def test_get_file_size_error(self, mock_head):
        """Test file size retrieval when request fails."""
        # Mock request exception
        mock_head.side_effect = requests.exceptions.RequestException("Network error")
        
        result = self.fetcher.get_file_size("https://example.com/test.pdf")
        self.assertIsNone(result)
    
    def test_download_pdf_empty_url(self):
        """Test download with empty URL."""
        success, message = self.fetcher.download_pdf("", self.temp_dir)
        self.assertFalse(success)
        self.assertIn("URL cannot be empty", message)
    
    @patch('pdf_fetcher.requests.Session.get')
    @patch('pdf_fetcher.requests.Session.head')
    def test_download_pdf_success(self, mock_head, mock_get):
        """Test successful PDF download."""
        # Mock HEAD request for file size
        mock_head_response = Mock()
        mock_head_response.headers = {'content-length': '100'}
        mock_head_response.raise_for_status.return_value = None
        mock_head.return_value = mock_head_response
        
        # Mock GET request for download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.headers = {'content-length': '100'}
        mock_get_response.raise_for_status.return_value = None
        
        # Mock PDF content
        pdf_content = b'%PDF-1.4\n%some pdf content here' + b'x' * 70  # Total ~100 bytes
        mock_get_response.iter_content.return_value = [pdf_content]
        mock_get.return_value = mock_get_response
        
        success, message = self.fetcher.download_pdf(
            "https://example.com/test.pdf", 
            self.temp_dir
        )
        
        self.assertTrue(success)
        self.assertIn("Successfully downloaded", message)
        
        # Check that file was created
        expected_file = self.temp_path / "test.pdf"
        self.assertTrue(expected_file.exists())
    
    @patch('pdf_fetcher.requests.Session.get')
    def test_download_pdf_network_error(self, mock_get):
        """Test download with network error."""
        # Mock network exception
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        success, message = self.fetcher.download_pdf(
            "https://example.com/test.pdf", 
            self.temp_dir
        )
        
        self.assertFalse(success)
        self.assertIn("Network error", message)
    
    @patch('pdf_fetcher.requests.Session.get')
    @patch('pdf_fetcher.requests.Session.head')
    def test_download_pdf_invalid_content(self, mock_head, mock_get):
        """Test download with invalid PDF content."""
        # Mock HEAD request
        mock_head_response = Mock()
        mock_head_response.headers = {'content-length': '50'}
        mock_head_response.raise_for_status.return_value = None
        mock_head.return_value = mock_head_response
        
        # Mock GET request with non-PDF content
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.headers = {'content-length': '50'}
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.iter_content.return_value = [b'<html>Not a PDF</html>' + b'x' * 27]
        mock_get.return_value = mock_get_response
        
        success, message = self.fetcher.download_pdf(
            "https://example.com/test.pdf", 
            self.temp_dir
        )
        
        self.assertFalse(success)
        self.assertIn("not a valid PDF", message)
    
    def test_download_pdf_custom_filename(self):
        """Test download with custom filename."""
        with patch('pdf_fetcher.requests.Session.get') as mock_get, \
             patch('pdf_fetcher.requests.Session.head') as mock_head:
            
            # Mock HEAD request
            mock_head_response = Mock()
            mock_head_response.headers = {'content-length': '100'}
            mock_head_response.raise_for_status.return_value = None
            mock_head.return_value = mock_head_response
            
            # Mock GET request
            mock_get_response = Mock()
            mock_get_response.status_code = 200
            mock_get_response.headers = {'content-length': '100'}
            mock_get_response.raise_for_status.return_value = None
            
            # Mock PDF content
            pdf_content = b'%PDF-1.4\n%some pdf content' + b'x' * 70
            mock_get_response.iter_content.return_value = [pdf_content]
            mock_get.return_value = mock_get_response
            
            success, message = self.fetcher.download_pdf(
                "https://example.com/original.pdf", 
                self.temp_dir,
                filename="custom_name.pdf"
            )
            
            self.assertTrue(success)
            
            # Check that file was created with custom name
            expected_file = self.temp_path / "custom_name.pdf"
            self.assertTrue(expected_file.exists())
            
            # Check that original filename file was NOT created
            original_file = self.temp_path / "original.pdf"
            self.assertFalse(original_file.exists())
    
    def test_download_pdf_filename_without_extension(self):
        """Test download with custom filename without .pdf extension."""
        with patch('pdf_fetcher.requests.Session.get') as mock_get, \
             patch('pdf_fetcher.requests.Session.head') as mock_head:
            
            # Mock HEAD request
            mock_head_response = Mock()
            mock_head_response.headers = {'content-length': '100'}
            mock_head_response.raise_for_status.return_value = None
            mock_head.return_value = mock_head_response
            
            # Mock GET request
            mock_get_response = Mock()
            mock_get_response.status_code = 200
            mock_get_response.headers = {'content-length': '100'}
            mock_get_response.raise_for_status.return_value = None
            
            # Mock PDF content
            pdf_content = b'%PDF-1.4\n%some pdf content' + b'x' * 70
            mock_get_response.iter_content.return_value = [pdf_content]
            mock_get.return_value = mock_get_response
            
            success, message = self.fetcher.download_pdf(
                "https://example.com/test.pdf", 
                self.temp_dir,
                filename="custom_name"  # No .pdf extension
            )
            
            self.assertTrue(success)
            
            # Check that file was created with .pdf extension added
            expected_file = self.temp_path / "custom_name.pdf"
            self.assertTrue(expected_file.exists())


if __name__ == '__main__':
    unittest.main()
