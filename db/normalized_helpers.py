#!/usr/bin/env python3
"""
Normalized Database Helpers
===========================

Helper functions for working with the normalized unpaywall database structure.
This module provides utilities for converting between text values and foreign key IDs,
and for inserting data into the normalized tables.

The normalized structure uses:
- lookup tables for license, oa_status, host_type, work_type
- CHAR(1) for location_type: 'p'=primary, 'a'=alternate, 'b'=best_oa
- foreign key references instead of redundant TEXT columns

Usage:
    from db.normalized_helpers import NormalizedHelper
    
    helper = NormalizedHelper(db_config)
    
    # Convert text values to IDs
    license_id = helper.get_or_create_lookup_id('license', 'cc-by')
    
    # Convert location type
    location_char = helper.normalize_location_type('primary')  # returns 'p'
    
    # Insert a complete record
    helper.insert_doi_url_record({
        'doi': '10.1234/example',
        'url': 'https://example.com/paper',
        'license': 'cc-by',
        'oa_status': 'gold',
        'host_type': 'journal',
        'work_type': 'journal-article',
        'location_type': 'primary'
    })
"""

import logging
import psycopg2
from typing import Dict, Optional, Any, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DOIURLRecord:
    """Data class for a DOI-URL record with normalized fields."""
    doi: str
    url: str
    pdf_url: Optional[str] = None
    openalex_id: Optional[int] = None
    title: Optional[str] = None
    publication_year: Optional[int] = None
    location_type: str = 'p'  # 'p', 'a', or 'b'
    version: Optional[str] = None
    license: Optional[str] = None
    host_type: Optional[str] = None
    oa_status: Optional[str] = None
    is_oa: bool = False
    work_type: Optional[str] = None
    is_retracted: bool = False
    url_quality_score: int = 50


class NormalizedHelper:
    """Helper class for working with the normalized database structure."""

    # Valid lookup table names (whitelist for SQL safety)
    VALID_LOOKUP_TABLES = frozenset(['license', 'oa_status', 'host_type', 'work_type'])

    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize the helper with database configuration.

        Args:
            db_config: Database connection parameters
        """
        self.db_config = db_config
        self._lookup_cache = {}  # Cache for lookup table values

    def _validate_lookup_table_name(self, table_name: str) -> None:
        """
        Validate that a table name is in the allowed whitelist.

        Args:
            table_name: Name of the lookup table to validate

        Raises:
            ValueError: If the table name is not in the whitelist
        """
        if table_name not in self.VALID_LOOKUP_TABLES:
            raise ValueError(f"Invalid lookup table name: {table_name}. "
                           f"Valid tables: {', '.join(sorted(self.VALID_LOOKUP_TABLES))}")

    def connect_db(self):
        """Establish database connection."""
        return psycopg2.connect(**self.db_config)
    
    def normalize_location_type(self, location_type: str) -> str:
        """
        Convert location_type text to CHAR(1) representation.

        Args:
            location_type: Text location type (primary, alternate, best_oa, secondary, etc.)

        Returns:
            Single character: 'p' for primary, 'a' for alternate/secondary, 'b' for best_oa
        """
        if not location_type:
            return 'p'

        location_lower = location_type.lower().strip()

        if location_lower in ['primary', 'p']:
            return 'p'
        elif location_lower in ['alternate', 'alternative', 'secondary', 'a']:
            return 'a'
        elif location_lower in ['best_oa', 'best', 'b']:
            return 'b'
        else:
            # Default to primary for unknown values
            return 'p'
    
    def get_or_create_lookup_id(self, table_name: str, value: Optional[str]) -> Optional[int]:
        """
        Get or create a lookup table entry and return its ID.

        Args:
            table_name: Name of the lookup table (license, oa_status, host_type, work_type)
            value: The value to look up or create

        Returns:
            The ID of the lookup entry, or None if value is empty
        """
        if not value or not value.strip():
            return None

        # Validate table name to prevent SQL injection
        self._validate_lookup_table_name(table_name)

        value = value.strip()
        cache_key = f"{table_name}:{value}"

        # Check cache first
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]
        
        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Try to get existing ID
                    cur.execute(f"""
                    SELECT id FROM unpaywall.{table_name} WHERE value = %s
                    """, (value,))
                    
                    result = cur.fetchone()
                    if result:
                        lookup_id = result[0]
                        self._lookup_cache[cache_key] = lookup_id
                        return lookup_id
                    
                    # Create new entry
                    cur.execute(f"""
                    INSERT INTO unpaywall.{table_name} (value) 
                    VALUES (%s) RETURNING id
                    """, (value,))
                    
                    new_id = cur.fetchone()[0]
                    conn.commit()
                    
                    # Cache the new ID
                    self._lookup_cache[cache_key] = new_id
                    return new_id
                    
                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Failed to get/create lookup ID for {table_name}.{value}: {e}")
                    return None
    
    def insert_doi_url_record(self, record_data: Union[Dict[str, Any], DOIURLRecord]) -> bool:
        """
        Insert a DOI-URL record into the normalized database.
        
        Args:
            record_data: Dictionary or DOIURLRecord with the data to insert
            
        Returns:
            True if successful, False otherwise
        """
        if isinstance(record_data, DOIURLRecord):
            data = record_data.__dict__
        else:
            data = record_data
        
        try:
            # Convert text values to foreign key IDs
            license_id = self.get_or_create_lookup_id('license', data.get('license'))
            oa_status_id = self.get_or_create_lookup_id('oa_status', data.get('oa_status'))
            host_type_id = self.get_or_create_lookup_id('host_type', data.get('host_type'))
            work_type_id = self.get_or_create_lookup_id('work_type', data.get('work_type'))
            
            # Normalize location type
            location_type = self.normalize_location_type(data.get('location_type', 'primary'))
            
            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                    INSERT INTO unpaywall.doi_urls (
                        doi, url, pdf_url, openalex_id, title, publication_year,
                        location_type, version, license_id, host_type_id, oa_status_id,
                        is_oa, work_type_id, is_retracted, url_quality_score
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (doi, url) DO UPDATE SET
                        pdf_url = EXCLUDED.pdf_url,
                        openalex_id = EXCLUDED.openalex_id,
                        title = EXCLUDED.title,
                        publication_year = EXCLUDED.publication_year,
                        location_type = EXCLUDED.location_type,
                        version = EXCLUDED.version,
                        license_id = EXCLUDED.license_id,
                        host_type_id = EXCLUDED.host_type_id,
                        oa_status_id = EXCLUDED.oa_status_id,
                        is_oa = EXCLUDED.is_oa,
                        work_type_id = EXCLUDED.work_type_id,
                        is_retracted = EXCLUDED.is_retracted,
                        url_quality_score = EXCLUDED.url_quality_score,
                        updated_at = CURRENT_TIMESTAMP
                    """, (
                        data.get('doi'),
                        data.get('url'),
                        data.get('pdf_url'),
                        data.get('openalex_id'),
                        data.get('title'),
                        data.get('publication_year'),
                        location_type,
                        data.get('version'),
                        license_id,
                        host_type_id,
                        oa_status_id,
                        data.get('is_oa', False),
                        work_type_id,
                        data.get('is_retracted', False),
                        data.get('url_quality_score', 50)
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to insert DOI-URL record: {e}")
            return False
    
    def get_lookup_value(self, table_name: str, lookup_id: int) -> Optional[str]:
        """
        Get the text value for a lookup table ID.

        Args:
            table_name: Name of the lookup table
            lookup_id: The ID to look up

        Returns:
            The text value, or None if not found
        """
        if not lookup_id:
            return None

        # Validate table name to prevent SQL injection
        self._validate_lookup_table_name(table_name)

        cache_key = f"{table_name}_id:{lookup_id}"

        # Check cache first
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]
        
        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(f"""
                    SELECT value FROM unpaywall.{table_name} WHERE id = %s
                    """, (lookup_id,))
                    
                    result = cur.fetchone()
                    if result:
                        value = result[0]
                        self._lookup_cache[cache_key] = value
                        return value
                    
                    return None
                    
                except psycopg2.Error as e:
                    logger.error(f"Failed to get lookup value for {table_name}.{lookup_id}: {e}")
                    return None
    
    def denormalize_location_type(self, location_char: str) -> str:
        """
        Convert CHAR(1) location_type back to text.
        
        Args:
            location_char: Single character ('p', 'a', 'b')
            
        Returns:
            Text representation (primary, alternate, best_oa)
        """
        mapping = {
            'p': 'primary',
            'a': 'alternate', 
            'b': 'best_oa'
        }
        return mapping.get(location_char, 'primary')
    
    def clear_cache(self):
        """Clear the lookup cache."""
        self._lookup_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about the lookup cache."""
        return {
            'total_entries': len(self._lookup_cache),
            'license_entries': len([k for k in self._lookup_cache.keys() if k.startswith('license:')]),
            'oa_status_entries': len([k for k in self._lookup_cache.keys() if k.startswith('oa_status:')]),
            'host_type_entries': len([k for k in self._lookup_cache.keys() if k.startswith('host_type:')]),
            'work_type_entries': len([k for k in self._lookup_cache.keys() if k.startswith('work_type:')])
        }
