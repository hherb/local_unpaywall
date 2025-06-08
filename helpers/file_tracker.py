#!/usr/bin/env python3
"""
File Tracking System for OpenAlex Processing
============================================

This module provides a SQLite-based file tracking system that monitors
which files have been processed, their content hashes, and processing statistics.
This enables efficient incremental processing by skipping unchanged files.

Features:
- SHA-256 hash-based change detection
- SQLite database for fast lookups
- Atomic operations with transaction support
- Processing statistics tracking
- Backup and recovery capabilities

Usage:
    tracker = FileTracker("processing_progress.db")
    
    # Check if file needs processing
    if tracker.needs_processing("data/file.gz"):
        # Process the file
        stats = process_file("data/file.gz")
        # Mark as completed
        tracker.mark_completed("data/file.gz", stats)
"""

import hashlib
import json
import logging
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


class FileTracker:
    """
    SQLite-based file tracking system for monitoring processed files.
    
    Tracks file paths, content hashes, processing statistics, and timestamps
    to enable efficient incremental processing of large datasets.
    """
    
    def __init__(self, db_path: str = "file_tracking.db"):
        """
        Initialize the file tracker with SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    completion_date TEXT NOT NULL,
                    processing_stats TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create indexes for efficient lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_path 
                ON processed_files(file_path)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash 
                ON processed_files(file_hash)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_completion_date 
                ON processed_files(completion_date)
            """)
            
            conn.commit()
            logger.debug(f"Initialized file tracking database: {self.db_path}")
    
    def _calculate_file_hash(self, file_path: str) -> Tuple[str, int]:
        """
        Calculate SHA-256 hash and size of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (hash_string, file_size)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        hash_sha256 = hashlib.sha256()
        file_size = 0
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_sha256.update(chunk)
                    file_size += len(chunk)
        except IOError as e:
            raise IOError(f"Cannot read file {file_path}: {e}")
        
        return hash_sha256.hexdigest(), file_size
    
    def needs_processing(self, file_path: str) -> bool:
        """
        Check if a file needs processing based on existence and hash comparison.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file needs processing, False if already processed and unchanged
        """
        file_path = str(Path(file_path).resolve())
        
        try:
            current_hash, current_size = self._calculate_file_hash(file_path)
        except (FileNotFoundError, IOError) as e:
            logger.warning(f"Cannot access file {file_path}: {e}")
            return False  # Can't process if file is inaccessible
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT file_hash, file_size FROM processed_files 
                WHERE file_path = ?
            """, (file_path,))
            
            result = cursor.fetchone()
            
            if result is None:
                logger.debug(f"File not in database, needs processing: {file_path}")
                return True
            
            stored_hash, stored_size = result
            
            if current_hash != stored_hash or current_size != stored_size:
                logger.info(f"File changed, needs reprocessing: {file_path}")
                return True
            
            logger.debug(f"File unchanged, skipping: {file_path}")
            return False
    
    def mark_completed(self, file_path: str, processing_stats: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark a file as completed processing with current hash and statistics.
        
        Args:
            file_path: Path to the processed file
            processing_stats: Optional dictionary of processing statistics
        """
        file_path = str(Path(file_path).resolve())
        
        try:
            file_hash, file_size = self._calculate_file_hash(file_path)
        except (FileNotFoundError, IOError) as e:
            logger.error(f"Cannot mark file as completed, file inaccessible: {file_path}: {e}")
            return
        
        completion_date = datetime.now().isoformat()
        stats_json = json.dumps(processing_stats) if processing_stats else None
        
        with sqlite3.connect(self.db_path) as conn:
            # Use INSERT OR REPLACE for upsert behavior
            conn.execute("""
                INSERT OR REPLACE INTO processed_files 
                (file_path, file_hash, file_size, completion_date, processing_stats, 
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 
                        COALESCE((SELECT created_at FROM processed_files WHERE file_path = ?), ?),
                        ?)
            """, (file_path, file_hash, file_size, completion_date, stats_json,
                  file_path, completion_date, completion_date))
            
            conn.commit()
            logger.info(f"Marked file as completed: {file_path}")
    
    def get_processed_files(self) -> List[Dict[str, Any]]:
        """
        Get list of all processed files with their metadata.
        
        Returns:
            List of dictionaries containing file information
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT file_path, file_hash, file_size, completion_date, 
                       processing_stats, created_at, updated_at
                FROM processed_files
                ORDER BY completion_date DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['processing_stats']:
                    result['processing_stats'] = json.loads(result['processing_stats'])
                results.append(result)
            
            return results
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about processed files.
        
        Returns:
            Dictionary with summary statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_files,
                    SUM(file_size) as total_size,
                    MIN(completion_date) as first_processed,
                    MAX(completion_date) as last_processed
                FROM processed_files
            """)
            
            result = cursor.fetchone()
            
            return {
                'total_files': result[0] or 0,
                'total_size_bytes': result[1] or 0,
                'total_size_mb': round((result[1] or 0) / (1024 * 1024), 2),
                'first_processed': result[2],
                'last_processed': result[3]
            }
    
    def remove_file_record(self, file_path: str) -> bool:
        """
        Remove a file record from the tracking database.
        
        Args:
            file_path: Path to the file to remove from tracking
            
        Returns:
            True if record was removed, False if not found
        """
        file_path = str(Path(file_path).resolve())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM processed_files WHERE file_path = ?
            """, (file_path,))
            
            conn.commit()
            removed = cursor.rowcount > 0
            
            if removed:
                logger.info(f"Removed file record: {file_path}")
            else:
                logger.warning(f"File record not found: {file_path}")
            
            return removed
    
    def cleanup_missing_files(self) -> int:
        """
        Remove records for files that no longer exist on disk.
        
        Returns:
            Number of records removed
        """
        removed_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT file_path FROM processed_files")
            file_paths = [row[0] for row in cursor.fetchall()]
            
            for file_path in file_paths:
                if not Path(file_path).exists():
                    conn.execute("DELETE FROM processed_files WHERE file_path = ?", (file_path,))
                    removed_count += 1
                    logger.debug(f"Removed record for missing file: {file_path}")
            
            conn.commit()
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} records for missing files")
        
        return removed_count
