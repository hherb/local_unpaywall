#!/usr/bin/env python3
"""
OpenAlex DOI and Full Text URL Extractor
========================================

This script extracts DOI and full text URL pairs directly from the OpenAlex snapshot
without importing into a database. Useful for integration with existing systems.

Features:
- Processes compressed JSONL files directly
- Extracts multiple URLs per DOI when available
- Filters by open access status, publication year, etc.
- Outputs to CSV, JSON, or TSV format
- Progress tracking and resumption capability

Usage:
    python extract_urls.py --snapshot-dir /path/to/openalex-snapshot --output urls.csv
"""

import argparse
import csv
import gzip
import json
import logging
import os
import sys
import glob
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tqdm import tqdm

# Import our file tracking system
from helpers.file_tracker import FileTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('openalex_url_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OpenAlexURLExtractor:
    """
    Extracts DOI and full text URL pairs from OpenAlex snapshot data.

    This class processes compressed JSONL files from OpenAlex snapshots to extract
    DOI and URL pairs, with support for filtering, progress tracking, and resumption.

    Attributes:
        snapshot_dir (Path): Path to the OpenAlex snapshot directory
        output_file (Path): Path to the output file
        output_format (str): Output format ('csv', 'json', or 'tsv')
        resume (bool): Whether to resume from a previous incomplete run
        file_tracker (FileTracker): SQLite-based file tracking system
        progress_file (Path): Legacy progress file path for backward compatibility
        stats (Dict[str, int]): Processing statistics
    """

    def __init__(self, snapshot_dir: str, output_file: str,
                 output_format: str = 'csv', resume: bool = False) -> None:
        """
        Initialize the OpenAlex URL extractor.

        Args:
            snapshot_dir: Path to the OpenAlex snapshot directory
            output_file: Path to the output file
            output_format: Output format ('csv', 'json', or 'tsv')
            resume: Whether to resume from a previous incomplete run
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.output_file = Path(output_file)
        self.output_format = output_format.lower()
        self.resume = resume

        # Initialize SQLite-based file tracking system
        tracking_db = self.output_file.with_suffix('.tracking.db')
        self.file_tracker = FileTracker(str(tracking_db))

        # Legacy progress file for backward compatibility
        self.progress_file = self.output_file.with_suffix('.progress')

        # Migrate from old progress system if needed
        if self.resume and self.progress_file.exists() and not self._has_tracking_data():
            self._migrate_from_legacy_progress()

        # Statistics
        self.stats = {
            'total_works_processed': 0,
            'works_with_doi': 0,
            'works_with_urls': 0,
            'total_url_records': 0,
            'dois_with_pdf_urls': 0,
            'total_pdf_urls': 0,
            'files_processed': 0,
            'files_skipped': 0
        }

    def _has_tracking_data(self) -> bool:
        """Check if the SQLite tracking database has any data."""
        try:
            summary = self.file_tracker.get_processing_summary()
            return summary['total_files'] > 0
        except Exception:
            return False

    def _migrate_from_legacy_progress(self) -> None:
        """
        Migrate from old JSON progress file to new SQLite tracking system.

        This method handles backward compatibility by converting old JSON-based
        progress tracking to the new SQLite-based system.

        Raises:
            Exception: If migration fails, logs warning but continues execution
        """
        try:
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
                processed_files = progress_data.get('processed_files', [])

            print(f"Migrating {len(processed_files)} files from legacy progress system...")

            for file_path in processed_files:
                if Path(file_path).exists():
                    # Mark as completed without stats (legacy data)
                    self.file_tracker.mark_completed(file_path, {'migrated_from_legacy': True})

            print("Migration completed successfully")

            # Backup and remove old progress file
            backup_file = self.progress_file.with_suffix('.progress.backup')
            self.progress_file.rename(backup_file)
            print(f"Legacy progress file backed up to: {backup_file}")

        except Exception as e:
            logger.warning(f"Could not migrate legacy progress: {e}")

    def _load_progress(self) -> None:
        """
        Load progress from previous run (legacy method for compatibility).

        This method is kept for backward compatibility but now uses SQLite
        instead of JSON files for progress tracking.
        """
        # This method is kept for backward compatibility but now uses SQLite
        summary = self.file_tracker.get_processing_summary()
        if summary['total_files'] > 0:
            print(f"Resuming from previous run. {summary['total_files']} files already processed.")


    def extract_urls_from_work(self, work: Dict[str, Any],
                              filters: Dict[str, Any]) -> tuple[List[Dict[str, str]], Dict[str, int]]:
        """
        Extract DOI and URL pairs from a single work record.

        Processes a single OpenAlex work record to extract all available URLs
        and their associated metadata, applying the specified filters.

        Args:
            work: OpenAlex work record as a dictionary
            filters: Dictionary of filters to apply (year_range, oa_only, etc.)

        Returns:
            A tuple containing:
                - List of URL record dictionaries with keys: doi, openalex_id, title,
                  publication_year, url, pdf_url, location_type, version, license,
                  host_type, oa_status, is_oa, work_type, is_retracted
                - Dictionary with PDF statistics: {'has_pdf_urls': bool, 'pdf_url_count': int}
        """
        
        # Initialize PDF statistics for this work
        pdf_stats = {
            'has_pdf_urls': False,
            'pdf_url_count': 0
        }

        # Validate input
        if not work or not isinstance(work, dict):
            return [], pdf_stats

        # Check if work has DOI
        doi = work.get('doi')
        if not doi:
            return [], pdf_stats

        # Additional validation for critical fields
        try:
            # Test access to potentially problematic nested structures
            _ = work.get('open_access', {})
            _ = work.get('primary_location', {})
            _ = work.get('locations', [])
            _ = work.get('best_oa_location', {})
        except Exception as e:
            logger.warning(f"Invalid work structure detected: {e}")
            return [], pdf_stats

        # Apply filters
        if not self._passes_filters(work, filters):
            return [], pdf_stats
        
        url_records = []
        work_id = work.get('id', '')
        # Extract numeric part from OpenAlex ID for storage efficiency
        openalex_work_id = self._extract_openalex_work_id(work_id)
        publication_year = work.get('publication_year')
        title = work.get('title', '')
        work_type = work.get('type', '')
        is_retracted = work.get('is_retracted', False)

        # Safely access nested open_access data
        open_access_data = work.get('open_access') or {}
        oa_status = open_access_data.get('oa_status', 'closed')
        is_oa = open_access_data.get('is_oa', False)
        
        # Helper function to create URL record
        def create_url_record(url: str, pdf_url: str, location_type: str,
                            version: Optional[str] = None, license_info: Optional[str] = None,
                            host_type: Optional[str] = None) -> Dict[str, str]:
            """
            Create a standardized URL record dictionary.

            Args:
                url: Landing page URL
                pdf_url: Direct PDF URL (if available)
                location_type: Type of location (primary, alternate, best_oa, etc.)
                version: Version information (publishedVersion, acceptedVersion, etc.)
                license_info: License information
                host_type: Type of host (journal, repository, preprint_server, etc.)

            Returns:
                Dictionary containing all URL record fields
            """
            # Track PDF URL statistics
            if pdf_url and pdf_url.strip():
                pdf_stats['has_pdf_urls'] = True
                pdf_stats['pdf_url_count'] += 1

            return {
                'doi': doi,
                'openalex_id': openalex_work_id or '',  # Store numeric ID for efficiency
                'title': title,
                'publication_year': str(publication_year) if publication_year else '',
                'url': url,
                'pdf_url': pdf_url or '',  # Direct PDF link (most important!)
                'location_type': location_type,  # primary, alternate, publisher, repository
                'version': version or '',
                'license': license_info or '',
                'host_type': host_type or '',
                'oa_status': oa_status,
                'is_oa': str(is_oa),
                'work_type': work_type,
                'is_retracted': str(is_retracted)
            }
        
        # Extract from primary location
        if primary_location := work.get('primary_location'):
            url = primary_location.get('landing_page_url')
            pdf_url = primary_location.get('pdf_url')
            if url and self._is_valid_url(url):
                url_records.append(create_url_record(
                    url=url,
                    pdf_url=pdf_url,
                    location_type='primary',
                    version=primary_location.get('version'),
                    license_info=primary_location.get('license'),
                    host_type=self._get_host_type(primary_location)
                ))
        
        # Extract from all locations (including alternates)
        locations = work.get('locations', [])
        for i, location in enumerate(locations):
            url = location.get('landing_page_url')
            pdf_url = location.get('pdf_url')
            if url and self._is_valid_url(url):
                # Skip if it's the same as primary location
                if work.get('primary_location', {}).get('landing_page_url') == url:
                    continue
                
                location_type = 'alternate' if i > 0 else 'secondary'
                url_records.append(create_url_record(
                    url=url,
                    pdf_url=pdf_url,
                    location_type=location_type,
                    version=location.get('version'),
                    license_info=location.get('license'),
                    host_type=self._get_host_type(location)
                ))
        
        # Extract from best OA location if different
        if best_oa_location := work.get('best_oa_location'):
            url = best_oa_location.get('landing_page_url')
            pdf_url = best_oa_location.get('pdf_url')
            if url and self._is_valid_url(url):
                # Check if we already have this URL
                existing_urls = {record['url'] for record in url_records}
                if url not in existing_urls:
                    url_records.append(create_url_record(
                        url=url,
                        pdf_url=pdf_url,
                        location_type='best_oa',
                        version=best_oa_location.get('version'),
                        license_info=best_oa_location.get('license'),
                        host_type=self._get_host_type(best_oa_location)
                    ))
        
        return url_records, pdf_stats

    def _passes_filters(self, work: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Check if work passes the specified filters.

        Args:
            work: OpenAlex work record as a dictionary
            filters: Dictionary of filters to apply including:
                - year_range: Tuple of (min_year, max_year)
                - oa_only: Boolean to include only open access works
                - language: Language code to filter by
                - types: List of work types to include
                - exclude_retracted: Boolean to exclude retracted works

        Returns:
            True if the work passes all filters, False otherwise
        """

        # Publication year filter
        if year_range := filters.get('year_range'):
            pub_year = work.get('publication_year')
            if pub_year:
                if year_range[0] and pub_year < year_range[0]:
                    return False
                if year_range[1] and pub_year > year_range[1]:
                    return False

        # Open access filter
        if filters.get('oa_only'):
            open_access_data = work.get('open_access') or {}
            if not open_access_data.get('is_oa', False):
                return False

        # Language filter (if available in future OpenAlex versions)
        if language := filters.get('language'):
            work_language = work.get('language')
            if work_language and work_language != language:
                return False

        # Type filter
        if work_types := filters.get('types'):
            work_type = work.get('type')
            if work_type and work_type not in work_types:
                return False

        # Exclude retracted works
        if filters.get('exclude_retracted', True):
            if work.get('is_retracted', False):
                return False

        return True

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid and useful for full-text access.

        Args:
            url: URL string to validate

        Returns:
            True if URL is valid and potentially useful, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
        except:
            return False

        # Filter out obvious non-fulltext URLs
        url_lower = url.lower()
        exclude_patterns = [
            'mailto:',
            'javascript:',
            'about:',
            '#',  # Fragment-only URLs
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        return True

    def _extract_openalex_work_id(self, openalex_url: str) -> Optional[str]:
        """
        Extract numeric work ID from OpenAlex URL for storage efficiency.

        Args:
            openalex_url: Full OpenAlex URL like "https://openalex.org/W1982051859"

        Returns:
            Numeric part as string (e.g., "1982051859") or None if extraction fails
        """
        if not openalex_url:
            return None

        try:
            # Handle full URLs like "https://openalex.org/W1982051859"
            if 'openalex.org/W' in openalex_url:
                return openalex_url.split('openalex.org/W')[1]
            # Handle W-prefixed IDs like "W1982051859"
            elif openalex_url.startswith('W'):
                return openalex_url[1:]  # Remove the 'W' prefix
            # If it's already just numbers, return as-is
            elif openalex_url.isdigit():
                return openalex_url
            else:
                return None
        except (IndexError, AttributeError):
            return None

    def _get_host_type(self, location: Dict[str, Any]) -> str:
        """
        Determine the type of host (publisher, repository, etc.).

        Args:
            location: OpenAlex location dictionary containing source information

        Returns:
            String indicating host type: 'doaj_journal', 'preprint_server',
            'repository', 'journal', or 'other'
        """
        source = location.get('source') or {}
        if not isinstance(source, dict):
            return 'other'

        # Check if it's in DOAJ (Directory of Open Access Journals)
        if source.get('is_in_doaj'):
            return 'doaj_journal'

        # Check host organization type
        host_org_name = source.get('host_organization_name')
        host_org = (host_org_name or '').lower()

        if any(term in host_org for term in ['arxiv', 'preprint', 'biorxiv', 'medrxiv']):
            return 'preprint_server'
        elif any(term in host_org for term in ['pubmed', 'pmc', 'europepmc']):
            return 'repository'
        elif source.get('type') == 'repository':
            return 'repository'
        elif source.get('type') == 'journal':
            return 'journal'
        else:
            return 'other'

    def process_works_file(self, jsonl_file: str,
                          output_writer, filters: Dict[str, Any],
                          show_progress: bool = True) -> Dict[str, int]:
        """
        Process a single works JSONL file and extract URL records.

        Args:
            jsonl_file: Path to the compressed JSONL file to process
            output_writer: Writer object for output (CSV writer, file handle, etc.)
            filters: Dictionary of filters to apply to works
            show_progress: Whether to show progress bar for this file

        Returns:
            Dictionary containing processing statistics for this file:
            - works_processed: Total works processed
            - works_with_doi: Works that have DOI
            - works_with_urls: Works that have extractable URLs
            - url_records_created: Total URL records created
            - dois_with_pdf_urls: DOIs that have PDF URLs
            - total_pdf_urls: Total PDF URLs found
        """
        file_stats = {
            'works_processed': 0,
            'works_with_doi': 0,
            'works_with_urls': 0,
            'url_records_created': 0,
            'dois_with_pdf_urls': 0,
            'total_pdf_urls': 0
        }

        pbar = None
        file_size = 0
        last_pos = 0

        try:
            # Get file size for progress estimation
            file_size = os.path.getsize(jsonl_file)

            with gzip.open(jsonl_file, 'rt', encoding='utf-8') as f:
                # Create progress bar for this file if requested
                # Use file size as approximation since we can't easily count lines
                if show_progress:
                    filename = os.path.basename(jsonl_file)
                    pbar = tqdm(
                        total=file_size,
                        unit='B',
                        unit_scale=True,
                        desc=f"Processing {filename}",
                        leave=False,
                        position=1
                    )
                    last_pos = 0

                for line_num, line in enumerate(f, 1):
                    try:
                        work = json.loads(line.strip())
                        file_stats['works_processed'] += 1

                        # Extract URL records for this work
                        try:
                            url_records, pdf_stats = self.extract_urls_from_work(work, filters)
                        except Exception as e:
                            logger.error(f"Error extracting URLs from work in {jsonl_file} line {line_num}: {e}")
                            # Log work structure for debugging
                            work_keys = list(work.keys()) if isinstance(work, dict) else "Not a dict"
                            logger.debug(f"Work keys: {work_keys}")
                            if isinstance(work, dict) and 'id' in work:
                                logger.debug(f"Work ID: {work.get('id')}")
                            url_records = []
                            pdf_stats = {'has_pdf_urls': False, 'pdf_url_count': 0}

                        if work.get('doi'):
                            file_stats['works_with_doi'] += 1

                            # Track PDF URL statistics for DOIs
                            if pdf_stats['has_pdf_urls']:
                                file_stats['dois_with_pdf_urls'] += 1
                            file_stats['total_pdf_urls'] += pdf_stats['pdf_url_count']

                        if url_records:
                            file_stats['works_with_urls'] += 1
                            file_stats['url_records_created'] += len(url_records)

                            # Write records
                            for record in url_records:
                                if self.output_format == 'csv':
                                    output_writer.writerow(record)
                                elif self.output_format == 'json':
                                    output_writer.write(json.dumps(record) + '\n')
                                elif self.output_format == 'tsv':
                                    # TSV writer
                                    output_writer.writerow(record)

                        # Update progress bar every 5000 lines using estimated progress
                        if pbar and line_num % 5000 == 0:
                            # Estimate progress based on line number and average line length
                            estimated_progress = min(line_num * 200, file_size)  # Assume ~200 bytes per line
                            progress_delta = estimated_progress - last_pos
                            if progress_delta > 0:
                                pbar.update(progress_delta)
                                last_pos = estimated_progress

                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode error in {jsonl_file} line {line_num}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing work in {jsonl_file} line {line_num}: {e}")
                        continue

                # Final progress bar update to 100%
                if pbar:
                    remaining = file_size - pbar.n
                    if remaining > 0:
                        pbar.update(remaining)
                    pbar.close()

        except Exception as e:
            if pbar:
                pbar.close()
            logger.error(f"Error reading file {jsonl_file}: {e}")
            return file_stats

        return file_stats

    def extract_urls(self, filters: Optional[Dict[str, Any]] = None,
                    max_workers: int = 4) -> None:
        """
        Extract DOI and URL pairs from all works files in the snapshot.

        This is the main method that orchestrates the entire extraction process,
        including file discovery, filtering, processing, and output generation.

        Args:
            filters: Optional dictionary of filters to apply to works
            max_workers: Number of parallel workers (currently unused as processing
                        is sequential to avoid file writing conflicts)
        """

        if filters is None:
            filters = {}

        print("Starting URL extraction from OpenAlex works...")

        # Find all works files
        works_pattern = self.snapshot_dir / 'data' / 'works' / '*' / '*.gz'
        works_files = list(glob.glob(str(works_pattern)))

        if not works_files:
            logger.error(f"No works files found at {works_pattern}")
            return

        # Filter out already processed files if resuming
        if self.resume:
            original_count = len(works_files)
            works_files = [f for f in works_files if self.file_tracker.needs_processing(f)]
            skipped_count = original_count - len(works_files)
            self.stats['files_skipped'] = skipped_count
            if skipped_count > 0:
                print(f"Skipping {skipped_count} unchanged files")

        print(f"Found {len(works_files)} works files to process")
        
        # Prepare output file
        output_mode = 'a' if (self.resume and self.output_file.exists()) else 'w'
        
        if self.output_format == 'csv':
            fieldnames = [
                'doi', 'openalex_id', 'title', 'publication_year', 'url', 'pdf_url',
                'location_type', 'version', 'license', 'host_type',
                'oa_status', 'is_oa', 'work_type', 'is_retracted'
            ]
            
            with open(self.output_file, output_mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if output_mode == 'w':  # Write header only for new files
                    writer.writeheader()
                
                self._process_files_parallel(works_files, writer, filters, max_workers)
                
        elif self.output_format == 'json':
            with open(self.output_file, output_mode, encoding='utf-8') as jsonfile:
                self._process_files_parallel(works_files, jsonfile, filters, max_workers)
                
        elif self.output_format == 'tsv':
            fieldnames = [
                'doi', 'openalex_id', 'title', 'publication_year', 'url', 'pdf_url',
                'location_type', 'version', 'license', 'host_type',
                'oa_status', 'is_oa', 'work_type', 'is_retracted'
            ]
            
            with open(self.output_file, output_mode, newline='', encoding='utf-8') as tsvfile:
                writer = csv.DictWriter(tsvfile, fieldnames=fieldnames, delimiter='\t')
                if output_mode == 'w':
                    writer.writeheader()
                
                self._process_files_parallel(works_files, writer, filters, max_workers)
        
        # Clean up legacy progress file on successful completion
        if self.progress_file.exists():
            self.progress_file.unlink()

        self._print_final_stats()

    def _process_files_parallel(self, works_files: List[str], output_writer,
                               filters: Dict[str, Any], max_workers: int) -> None:
        """
        Process files sequentially with progress tracking.

        Note: Despite the name suggesting parallel processing, this method currently
        processes files sequentially to avoid file writing conflicts. The max_workers
        parameter is kept for future optimization.

        Args:
            works_files: List of file paths to process
            output_writer: Writer object for output
            filters: Dictionary of filters to apply
            max_workers: Number of parallel workers (currently unused)
        """

        # For simplicity, process files sequentially to avoid file writing conflicts
        # Could be optimized with proper synchronization if needed

        # Create main progress bar for files
        with tqdm(
            total=len(works_files),
            desc="Processing files",
            unit="file",
            position=0,
            leave=True
        ) as file_pbar:

            for works_file in works_files:
                # Update file progress bar description with current file
                filename = os.path.basename(works_file)
                file_pbar.set_description(f"Processing {filename}")

                file_stats = self.process_works_file(works_file, output_writer, filters, show_progress=True)

                # Update global stats
                self.stats['total_works_processed'] += file_stats['works_processed']
                self.stats['works_with_doi'] += file_stats['works_with_doi']
                self.stats['works_with_urls'] += file_stats['works_with_urls']
                self.stats['total_url_records'] += file_stats['url_records_created']
                self.stats['dois_with_pdf_urls'] += file_stats['dois_with_pdf_urls']
                self.stats['total_pdf_urls'] += file_stats['total_pdf_urls']
                self.stats['files_processed'] += 1

                # Mark file as processed with statistics
                self.file_tracker.mark_completed(works_file, file_stats)

                # Update file progress bar
                file_pbar.update(1)

                # Update postfix with current stats
                file_pbar.set_postfix({
                    'URLs': f"{file_stats['works_with_urls']:,}",
                    'Records': f"{file_stats['url_records_created']:,}",
                    'Total Works': f"{self.stats['total_works_processed']:,}"
                })

    def _print_final_stats(self) -> None:
        """
        Print final extraction statistics to console.

        Displays comprehensive statistics about the extraction process including
        file counts, work counts, URL coverage, and file tracking information.
        """
        print("\n" + "=" * 60)
        print("URL EXTRACTION COMPLETED")
        print("=" * 60)
        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Files skipped (unchanged): {self.stats.get('files_skipped', 0)}")
        print(f"Total works processed: {self.stats['total_works_processed']:,}")
        print(f"Works with DOI: {self.stats['works_with_doi']:,}")
        print(f"Works with URLs: {self.stats['works_with_urls']:,}")
        print(f"Total URL records: {self.stats['total_url_records']:,}")
        print(f"DOIs with PDF URLs: {self.stats['dois_with_pdf_urls']:,}")
        print(f"Total PDF URLs found: {self.stats['total_pdf_urls']:,}")

        if self.stats['works_with_doi'] > 0:
            url_percentage = (self.stats['works_with_urls'] / self.stats['works_with_doi']) * 100
            print(f"URL coverage: {url_percentage:.1f}% of DOI works have URLs")

            pdf_percentage = (self.stats['dois_with_pdf_urls'] / self.stats['works_with_doi']) * 100
            print(f"PDF URL coverage: {pdf_percentage:.1f}% of DOI works have PDF URLs")

        # Print file tracking summary
        tracking_summary = self.file_tracker.get_processing_summary()
        print(f"Total files tracked: {tracking_summary['total_files']}")
        print(f"Total data processed: {tracking_summary['total_size_mb']} MB")

        print(f"Output saved to: {self.output_file}")
        print(f"File tracking database: {self.file_tracker.db_path}")


def main() -> None:
    """
    Main entry point for the OpenAlex URL extractor script.

    Parses command line arguments, sets up filters, and runs the extraction process.
    """
    parser = argparse.ArgumentParser(description='Extract DOI and URL pairs from OpenAlex snapshot')
    parser.add_argument('--snapshot-dir', required=True,
                        help='Path to OpenAlex snapshot directory')
    parser.add_argument('--output', required=True,
                        help='Output file path')
    parser.add_argument('--format', choices=['csv', 'json', 'tsv'], default='csv',
                        help='Output format (default: csv)')
    parser.add_argument('--year-from', type=int,
                        help='Include works from this year onwards')
    parser.add_argument('--year-to', type=int,
                        help='Include works up to this year')
    parser.add_argument('--oa-only', action='store_true',
                        help='Only include open access works')
    parser.add_argument('--types', nargs='+',
                        help='Include only specific work types (e.g., journal-article, book-chapter)')
    parser.add_argument('--exclude-retracted', action='store_true', default=True,
                        help='Exclude retracted works (default: True)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous incomplete run')
    parser.add_argument('--max-workers', type=int, default=4,
                        help='Number of parallel workers (default: 4)')

    args = parser.parse_args()

    # Build filters
    filters = {}

    if args.year_from or args.year_to:
        filters['year_range'] = (args.year_from, args.year_to)

    if args.oa_only:
        filters['oa_only'] = True

    if args.types:
        filters['types'] = args.types

    filters['exclude_retracted'] = args.exclude_retracted

    # Create extractor and run
    extractor = OpenAlexURLExtractor(
        snapshot_dir=args.snapshot_dir,
        output_file=args.output,
        output_format=args.format,
        resume=args.resume
    )

    extractor.extract_urls(filters=filters, max_workers=args.max_workers)


if __name__ == '__main__':
    main()
