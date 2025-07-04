#!/usr/bin/env python3
"""
Memory-Efficient CSV Processing Utilities
========================================

This module provides memory-efficient utilities for processing large CSV files
using Python generators to avoid loading entire files into memory.

Features:
- Generator-based batch processing for constant memory usage
- Automatic delimiter detection
- Progress tracking with tqdm
- Flexible validation and transformation callbacks
- Support for very large files (GB+ sizes)

Usage:
    from helpers.csv_utils import CSVBatchProcessor
    
    processor = CSVBatchProcessor('large_file.csv', batch_size=10000)
    
    for batch in processor.process_batches():
        # Process each batch of rows
        for row in batch:
            print(row)
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator, Callable, Union

try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm is not available
    class tqdm:
        def __init__(self, *args, **kwargs):
            self.total = kwargs.get('total', 0)
            self.n = 0
        
        def update(self, n=1):
            self.n += n
        
        def close(self):
            pass

logger = logging.getLogger(__name__)


def count_lines_fast(file_path: Union[str, Path], show_progress: bool = True) -> int:
    """
    Fast line counting using large buffer reads with optional progress indicator.

    This function is much faster than the old line-by-line approach,
    especially for large files. It reads the file in 1MB chunks
    and counts newline characters, showing progress for large files.

    Args:
        file_path: Path to the file to count lines in
        show_progress: Whether to show progress bar for large files (>10MB)

    Returns:
        Number of lines in the file

    Example:
        # Count lines in a CSV file
        line_count = count_lines_fast('large_file.csv')

        # Count lines without progress bar
        line_count = count_lines_fast('file.csv', show_progress=False)
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = file_path.stat().st_size
    if file_size == 0:
        return 0

    line_count = 0
    buffer_size = 1024 * 1024  # 1MB buffer for optimal performance

    # Show progress bar for files larger than 10MB
    show_count_progress = show_progress and file_size > 10 * 1024 * 1024
    progress_bar = None

    if show_count_progress:
        progress_bar = tqdm(
            total=file_size,
            desc="Counting lines",
            unit="B",
            unit_scale=True,
            unit_divisor=1024
        )

    try:
        with open(file_path, 'rb') as f:
            while True:
                buffer = f.read(buffer_size)
                if not buffer:
                    break

                line_count += buffer.count(b'\n')

                if progress_bar:
                    progress_bar.update(len(buffer))

    finally:
        if progress_bar:
            progress_bar.close()

    logger.debug(f"Fast line count: {line_count:,} lines ({file_size / 1024 / 1024:.1f} MB)")
    return line_count


class CSVBatchProcessor:
    """
    Memory-efficient CSV processor that yields batches of rows using generators.
    
    This class provides a memory-efficient way to process large CSV files by:
    1. Using generators to yield one batch at a time
    2. Automatic delimiter detection
    3. Optional row validation and transformation
    4. Progress tracking
    """
    
    def __init__(self,
                 csv_file: str,
                 batch_size: int = 10000,
                 validator: Optional[Callable[[Dict[str, str]], Optional[Dict[str, Any]]]] = None,
                 show_progress: bool = True,
                 encoding: str = 'utf-8',
                 enable_line_count: bool = True):
        """
        Initialize the CSV batch processor.

        Args:
            csv_file: Path to the CSV file
            batch_size: Number of rows per batch
            validator: Optional function to validate/transform each row
            show_progress: Whether to show progress bar
            encoding: File encoding
            enable_line_count: Whether to count lines for progress tracking (default: True)
                              Set to False for maximum performance on very large files
        """
        self.csv_file = Path(csv_file)
        self.batch_size = batch_size
        self.validator = validator
        self.show_progress = show_progress
        self.encoding = encoding
        self.enable_line_count = enable_line_count
        
        # Statistics
        self.stats = {
            'total_rows_processed': 0,
            'rows_valid': 0,
            'rows_skipped': 0,
            'batches_yielded': 0
        }
    
    def _detect_delimiter(self, sample: str) -> str:
        """Detect CSV delimiter from a sample of the file."""
        try:
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
            logger.info(f"Detected CSV delimiter: '{delimiter}'")
            return delimiter
        except csv.Error:
            # Fallback: try common delimiters in order of likelihood
            common_delimiters = [',', '\t', ';', '|']
            delimiter_counts = {delim: sample.count(delim) for delim in common_delimiters}
            
            # Choose delimiter with highest count (if any)
            if any(count > 0 for count in delimiter_counts.values()):
                delimiter = max(delimiter_counts, key=lambda x: delimiter_counts[x])
                logger.info(f"Auto-detected CSV delimiter: '{delimiter}' (found {delimiter_counts[delimiter]} occurrences)")
                return delimiter
            else:
                logger.warning(f"Could not detect delimiter, using default comma. Sample: {sample[:200]}")
                return ','
    
    def _count_lines(self) -> int:
        """
        Fast line counting using the standalone count_lines_fast function.

        Returns:
            Number of lines in the file
        """
        return count_lines_fast(self.csv_file, show_progress=True)
    
    def process_batches(self) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Memory-efficient generator that yields batches of CSV rows.
        
        Yields:
            List of dictionaries representing CSV rows in each batch
        """
        if not self.csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_file}")
        
        # Check if file is empty
        file_size = self.csv_file.stat().st_size
        if file_size == 0:
            raise ValueError("CSV file is empty")
        
        # Count lines for progress tracking (optional for performance)
        line_count = None
        if self.show_progress and self.enable_line_count:
            line_count = self._count_lines()
            if line_count <= 1:
                raise ValueError(f"CSV file has no data rows (only {line_count} line(s) found)")
            logger.info(f"Processing CSV file: {self.csv_file} ({line_count:,} lines)")
        elif self.show_progress:
            logger.info(f"Processing CSV file: {self.csv_file} (line counting disabled for performance)")
        else:
            logger.info(f"Processing CSV file: {self.csv_file}")
        
        with open(self.csv_file, 'r', encoding=self.encoding) as csvfile:
            # Detect delimiter
            sample = csvfile.read(8192)
            csvfile.seek(0)
            delimiter = self._detect_delimiter(sample)
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            # Validate CSV structure
            try:
                first_row = next(reader)
                csvfile.seek(0)
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                logger.info(f"CSV columns: {list(first_row.keys())}")
            except StopIteration:
                raise ValueError("CSV file appears to be empty or has no data rows")
            
            # Initialize progress bar
            progress_bar = None
            if self.show_progress:
                if line_count is not None:
                    progress_bar = tqdm(
                        total=line_count - 1,  # Subtract 1 for header
                        desc="Processing CSV",
                        unit="rows",
                        unit_scale=True
                    )
                else:
                    # Progress bar without total (shows count and rate only)
                    progress_bar = tqdm(
                        desc="Processing CSV",
                        unit="rows",
                        unit_scale=True
                    )
            
            current_batch = []
            
            try:
                for row in reader:
                    # Apply validation/transformation if provided
                    if self.validator:
                        processed_row = self.validator(row)
                        if processed_row:
                            current_batch.append(processed_row)
                            self.stats['rows_valid'] += 1
                        else:
                            self.stats['rows_skipped'] += 1
                    else:
                        current_batch.append(row)
                        self.stats['rows_valid'] += 1
                    
                    self.stats['total_rows_processed'] += 1
                    
                    if progress_bar is not None:
                        progress_bar.update(1)
                    
                    # Yield batch when full
                    if len(current_batch) >= self.batch_size:
                        self.stats['batches_yielded'] += 1
                        yield current_batch
                        current_batch = []
                
                # Yield final batch if not empty
                if current_batch:
                    self.stats['batches_yielded'] += 1
                    yield current_batch
                    
            finally:
                if progress_bar is not None:
                    progress_bar.close()
        
        logger.info(f"CSV processing complete. {self.stats['batches_yielded']} batches yielded, "
                   f"{self.stats['rows_valid']} valid rows, {self.stats['rows_skipped']} skipped")
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return self.stats.copy()


def process_csv_in_batches(csv_file: str,
                          batch_size: int = 10000,
                          validator: Optional[Callable[[Dict[str, str]], Optional[Dict[str, Any]]]] = None,
                          show_progress: bool = True,
                          enable_line_count: bool = True) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Convenience function for memory-efficient CSV batch processing.

    Args:
        csv_file: Path to CSV file
        batch_size: Number of rows per batch
        validator: Optional row validation/transformation function
        show_progress: Whether to show progress bar
        enable_line_count: Whether to count lines for progress tracking (default: True)
                          Set to False for maximum performance on very large files

    Yields:
        Batches of CSV rows as lists of dictionaries

    Example:
        def validate_row(row):
            if row.get('email'):
                return {'email': row['email'].lower(), 'name': row.get('name', '')}
            return None

        for batch in process_csv_in_batches('users.csv', validator=validate_row):
            # Process batch
            for user in batch:
                print(user['email'])
    """
    processor = CSVBatchProcessor(
        csv_file=csv_file,
        batch_size=batch_size,
        validator=validator,
        show_progress=show_progress,
        enable_line_count=enable_line_count
    )
    
    yield from processor.process_batches()


if __name__ == '__main__':
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Test CSV batch processing')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size')
    parser.add_argument('--max-batches', type=int, help='Maximum batches to process (for testing)')
    
    args = parser.parse_args()
    
    def simple_validator(row):
        # Example: only keep rows with non-empty first column
        first_col = next(iter(row.values()), '')
        return row if first_col.strip() else None
    
    batch_count = 0
    for batch in process_csv_in_batches(args.csv_file, args.batch_size, simple_validator):
        batch_count += 1
        print(f"Batch {batch_count}: {len(batch)} rows")
        
        if args.max_batches and batch_count >= args.max_batches:
            print(f"Stopping after {args.max_batches} batches")
            break
