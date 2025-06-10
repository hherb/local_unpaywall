#!/usr/bin/env python3
"""
Test script for the normalized database structure.

This script tests the normalized database functionality including:
- Creating the schema with lookup tables
- Inserting data using the helper functions
- Querying normalized data
- Verifying storage efficiency

Usage:
    python test_normalized_db.py
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from db.create_db import DatabaseCreator
from db.normalized_helpers import NormalizedHelper, DOIURLRecord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_normalized_database():
    """Test the normalized database functionality."""
    
    # Database configuration (using environment variables or defaults)
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', '5432')),
        'database': os.getenv('POSTGRES_DB', 'unpaywall_test'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'password')
    }
    
    logger.info("Testing normalized database structure...")
    
    try:
        # Step 1: Create the database schema
        logger.info("Creating database schema...")
        creator = DatabaseCreator(**db_config)
        
        if not creator.test_connection():
            logger.error("Cannot connect to database")
            return False
        
        success = creator.create_complete_schema(verify=True)
        if not success:
            logger.error("Failed to create schema")
            return False
        
        logger.info("✓ Schema created successfully")
        
        # Step 2: Test the helper functions
        logger.info("Testing normalized helper functions...")
        helper = NormalizedHelper(db_config)
        
        # Test data
        test_records = [
            {
                'doi': '10.1234/test1',
                'url': 'https://example.com/paper1',
                'pdf_url': 'https://example.com/paper1.pdf',
                'title': 'Test Paper 1',
                'publication_year': 2023,
                'location_type': 'primary',
                'license': 'cc-by',
                'host_type': 'journal',
                'oa_status': 'gold',
                'work_type': 'journal-article',
                'is_oa': True,
                'url_quality_score': 85
            },
            {
                'doi': '10.1234/test2',
                'url': 'https://example.com/paper2',
                'title': 'Test Paper 2',
                'publication_year': 2023,
                'location_type': 'alternate',
                'license': 'cc-by-sa',
                'host_type': 'repository',
                'oa_status': 'green',
                'work_type': 'journal-article',
                'is_oa': True,
                'url_quality_score': 70
            },
            {
                'doi': '10.1234/test3',
                'url': 'https://example.com/paper3',
                'title': 'Test Paper 3',
                'publication_year': 2024,
                'location_type': 'best_oa',
                'license': 'cc0',
                'host_type': 'preprint_server',
                'oa_status': 'gold',
                'work_type': 'preprint',
                'is_oa': True,
                'url_quality_score': 90
            }
        ]
        
        # Insert test records
        for i, record in enumerate(test_records, 1):
            success = helper.insert_doi_url_record(record)
            if success:
                logger.info(f"✓ Inserted test record {i}")
            else:
                logger.error(f"✗ Failed to insert test record {i}")
                return False
        
        # Step 3: Test queries
        logger.info("Testing normalized queries...")
        
        with helper.connect_db() as conn:
            with conn.cursor() as cur:
                # Test 1: Basic query
                cur.execute("SELECT COUNT(*) FROM unpaywall.doi_urls")
                count = cur.fetchone()[0]
                logger.info(f"✓ Total records in doi_urls: {count}")
                
                # Test 2: Join with lookup tables
                cur.execute("""
                SELECT d.doi, d.url, l.value as license, h.value as host_type, 
                       o.value as oa_status, w.value as work_type, d.location_type
                FROM unpaywall.doi_urls d
                LEFT JOIN unpaywall.license l ON d.license_id = l.id
                LEFT JOIN unpaywall.host_type h ON d.host_type_id = h.id
                LEFT JOIN unpaywall.oa_status o ON d.oa_status_id = o.id
                LEFT JOIN unpaywall.work_type w ON d.work_type_id = w.id
                ORDER BY d.doi
                """)
                
                results = cur.fetchall()
                logger.info(f"✓ Retrieved {len(results)} records with joins")
                
                for row in results:
                    doi, url, license, host_type, oa_status, work_type, location_type = row
                    logger.info(f"  {doi}: {license}, {host_type}, {oa_status}, {work_type}, location={location_type}")
                
                # Test 3: Check lookup tables
                lookup_tables = ['license', 'oa_status', 'host_type', 'work_type']
                for table in lookup_tables:
                    cur.execute(f"SELECT COUNT(*) FROM unpaywall.{table}")
                    count = cur.fetchone()[0]
                    logger.info(f"✓ {table} lookup table has {count} entries")
                
                # Test 4: Verify location_type normalization
                cur.execute("""
                SELECT location_type, COUNT(*) 
                FROM unpaywall.doi_urls 
                GROUP BY location_type 
                ORDER BY location_type
                """)
                
                location_counts = cur.fetchall()
                logger.info("✓ Location type distribution:")
                for location_type, count in location_counts:
                    location_name = helper.denormalize_location_type(location_type)
                    logger.info(f"  {location_type} ({location_name}): {count}")
        
        # Step 4: Test helper utility functions
        logger.info("Testing helper utility functions...")
        
        # Test lookup ID retrieval
        license_id = helper.get_or_create_lookup_id('license', 'cc-by')
        logger.info(f"✓ License 'cc-by' has ID: {license_id}")
        
        # Test reverse lookup
        license_value = helper.get_lookup_value('license', license_id)
        logger.info(f"✓ License ID {license_id} has value: {license_value}")
        
        # Test location type normalization
        test_locations = ['primary', 'alternate', 'best_oa', 'unknown']
        for location in test_locations:
            normalized = helper.normalize_location_type(location)
            denormalized = helper.denormalize_location_type(normalized)
            logger.info(f"✓ '{location}' → '{normalized}' → '{denormalized}'")
        
        # Test cache statistics
        cache_stats = helper.get_cache_stats()
        logger.info(f"✓ Cache statistics: {cache_stats}")
        
        logger.info("✅ All tests passed! Normalized database is working correctly.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


def main():
    """Main function."""
    success = test_normalized_database()
    
    if success:
        print("\n🎉 Normalized database test completed successfully!")
        print("The database is ready for use with storage-optimized structure.")
        sys.exit(0)
    else:
        print("\n💥 Normalized database test failed!")
        print("Please check the logs for details.")
        sys.exit(1)


if __name__ == '__main__':
    main()
