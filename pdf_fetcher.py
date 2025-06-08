#!/usr/bin/env python3
"""
PDF Fetcher Utility
==================

A utility script for downloading PDF files from URLs with progress tracking.

Features:
- Downloads PDFs from specified URLs
- Saves to specified directories with optional custom filenames
- Progress indication using tqdm
- Resume capability for interrupted downloads
- PDF content validation
- Robust error handling for network issues

Usage:
    python pdf_fetcher.py <url> <output_dir> [--filename <custom_name>]
    
Examples:
    # Download with original filename
    python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/"
    
    # Download with custom filename
    python pdf_fetcher.py "https://example.com/paper.pdf" "./downloads/" --filename "my_paper.pdf"
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote

import requests
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFFetcher:
    """
    A utility class for downloading PDF files with progress tracking.
    
    Features:
    - Progress indication with tqdm
    - Resume capability for interrupted downloads
    - PDF content validation
    - Robust error handling
    """
    
    def __init__(self, 
                 chunk_size: int = 8192,
                 timeout: int = 30,
                 user_agent: str = "PDF-Fetcher/1.0"):
        """
        Initialize the PDF fetcher.
        
        Args:
            chunk_size: Size of chunks to download at a time (bytes)
            timeout: Request timeout in seconds
            user_agent: User agent string for HTTP requests
        """
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.user_agent = user_agent
        
        # Configure session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/pdf,*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def extract_filename_from_url(self, url: str) -> str:
        """
        Extract filename from URL, defaulting to 'downloaded.pdf' if not found.
        
        Args:
            url: The URL to extract filename from
            
        Returns:
            Extracted or default filename
        """
        try:
            parsed_url = urlparse(url)
            path = unquote(parsed_url.path)
            filename = os.path.basename(path)
            
            # If no filename or no .pdf extension, use default
            if not filename or not filename.lower().endswith('.pdf'):
                filename = 'downloaded.pdf'
                
            return filename
        except Exception as e:
            logger.warning(f"Could not extract filename from URL: {e}")
            return 'downloaded.pdf'
    
    def validate_pdf_content(self, file_path: Path) -> bool:
        """
        Validate that the downloaded file is actually a PDF.
        
        Args:
            file_path: Path to the downloaded file
            
        Returns:
            True if file appears to be a valid PDF
        """
        try:
            with open(file_path, 'rb') as f:
                # Read first few bytes to check PDF header
                header = f.read(8)
                return header.startswith(b'%PDF-')
        except Exception as e:
            logger.error(f"Error validating PDF content: {e}")
            return False
    
    def get_file_size(self, url: str) -> Optional[int]:
        """
        Get the file size from HTTP headers without downloading the file.
        
        Args:
            url: URL to check
            
        Returns:
            File size in bytes, or None if not available
        """
        try:
            response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            if content_length:
                return int(content_length)
        except Exception as e:
            logger.debug(f"Could not get file size: {e}")
        
        return None
    
    def download_pdf(self, 
                     url: str, 
                     output_dir: str, 
                     filename: Optional[str] = None,
                     resume: bool = True) -> Tuple[bool, str]:
        """
        Download a PDF from the specified URL.
        
        Args:
            url: URL of the PDF to download
            output_dir: Directory to save the PDF
            filename: Optional custom filename (defaults to extracted from URL)
            resume: Whether to resume interrupted downloads
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate URL
            if not url.strip():
                return False, "URL cannot be empty"
            
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Determine filename
            if not filename:
                filename = self.extract_filename_from_url(url)
            
            # Ensure filename has .pdf extension
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
            
            file_path = output_path / filename
            
            # Check if file already exists and get its size for resume
            existing_size = 0
            if file_path.exists() and resume:
                existing_size = file_path.stat().st_size
                logger.info(f"Found existing file of {existing_size} bytes, attempting to resume")
            
            # Get total file size
            total_size = self.get_file_size(url)
            
            # If file is already complete, skip download
            if existing_size > 0 and total_size and existing_size >= total_size:
                if self.validate_pdf_content(file_path):
                    return True, f"File already exists and is complete: {file_path}"
                else:
                    logger.warning("Existing file appears corrupted, re-downloading")
                    existing_size = 0
            
            # Set up headers for resume
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
            
            # Start download
            logger.info(f"Downloading PDF from: {url}")
            response = self.session.get(
                url, 
                headers=headers,
                stream=True, 
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Check if server supports range requests for resume
            if existing_size > 0 and response.status_code != 206:
                logger.warning("Server doesn't support range requests, starting fresh download")
                existing_size = 0
            
            # Get content length from response
            content_length = response.headers.get('content-length')
            if content_length:
                remaining_size = int(content_length)
                if existing_size > 0:
                    total_download_size = existing_size + remaining_size
                else:
                    total_download_size = remaining_size
            else:
                total_download_size = total_size
            
            # Open file for writing (append if resuming)
            mode = 'ab' if existing_size > 0 else 'wb'
            
            with open(file_path, mode) as f:
                # Set up progress bar
                progress_desc = f"Downloading {filename}"
                if existing_size > 0:
                    progress_desc += f" (resuming from {existing_size} bytes)"
                
                with tqdm(
                    total=total_download_size,
                    initial=existing_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=progress_desc
                ) as pbar:
                    
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:  # Filter out keep-alive chunks
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            # Validate the downloaded PDF
            if not self.validate_pdf_content(file_path):
                file_path.unlink()  # Delete invalid file
                return False, "Downloaded file is not a valid PDF"
            
            file_size = file_path.stat().st_size
            logger.info(f"Successfully downloaded PDF: {file_path} ({file_size} bytes)")
            
            return True, f"Successfully downloaded: {file_path}"
            
        except requests.exceptions.RequestException as e:
            return False, f"Network error: {e}"
        except IOError as e:
            return False, f"File I/O error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Download PDF files from URLs with progress tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://example.com/paper.pdf" "./downloads/"
  %(prog)s "https://example.com/paper.pdf" "./downloads/" --filename "my_paper.pdf"
  %(prog)s "https://example.com/paper.pdf" "./downloads/" --no-resume
        """
    )
    
    parser.add_argument('url', help='URL of the PDF to download')
    parser.add_argument('output_dir', help='Directory to save the PDF')
    parser.add_argument('--filename', help='Custom filename for the downloaded PDF')
    parser.add_argument('--no-resume', action='store_true', 
                       help='Disable resume capability for interrupted downloads')
    parser.add_argument('--chunk-size', type=int, default=8192,
                       help='Download chunk size in bytes (default: 8192)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create fetcher
    fetcher = PDFFetcher(
        chunk_size=args.chunk_size,
        timeout=args.timeout
    )
    
    # Download the PDF
    success, message = fetcher.download_pdf(
        url=args.url,
        output_dir=args.output_dir,
        filename=args.filename,
        resume=not args.no_resume
    )
    
    if success:
        print(f"✓ {message}")
        sys.exit(0)
    else:
        print(f"✗ {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
