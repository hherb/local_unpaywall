#!/usr/bin/env python3
"""
Database Schema Creation Module
===============================

This module handles all database schema creation and modification for the
local_unpaywall project. It provides a centralized location for database
structure management, separate from the import logic.

Features:
- Complete schema creation for the unpaywall namespace
- Table creation with proper indexes and constraints
- Support for .env file credentials with command line fallback
- Comprehensive error handling and logging
- Integration with the existing migration system
- Idempotent operations (safe to run multiple times)

Database Structure:
- unpaywall.doi_urls: Main DOI-URL mapping table
- unpaywall.import_progress: Import tracking and resume functionality
- unpaywall.schema_migrations: Migration tracking (handled by migration system)

Usage:
    from db.create_db import DatabaseCreator
    
    # With explicit credentials
    creator = DatabaseCreator(host='localhost', database='mydb', 
                            user='myuser', password='mypass')
    creator.create_complete_schema()
    
    # With .env file support
    creator = DatabaseCreator.from_env_or_args(
        host='localhost', database='mydb', user='myuser', password='mypass'
    )
    creator.create_complete_schema()
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any
import psycopg2
from psycopg2 import sql

# Try to import python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)


class DatabaseCreator:
    """
    Handles creation and management of the unpaywall database schema.
    
    This class provides methods to create all necessary tables, indexes,
    constraints, and permissions for the unpaywall functionality.
    """
    
    def __init__(self, host: str, database: str, user: str, password: str, 
                 port: int = 5432, **kwargs):
        """
        Initialize DatabaseCreator with connection parameters.
        
        Args:
            host: Database host
            database: Database name
            user: Database user
            password: Database password
            port: Database port (default: 5432)
            **kwargs: Additional connection parameters
        """
        self.db_config = {
            'host': host,
            'database': database,
            'user': user,
            'password': password,
            'port': port,
            **kwargs
        }
        
    @classmethod
    def from_env_or_args(cls, host: Optional[str] = None, database: Optional[str] = None,
                        user: Optional[str] = None, password: Optional[str] = None,
                        port: Optional[int] = None) -> 'DatabaseCreator':
        """
        Create DatabaseCreator instance using .env file with command line fallback.
        
        Command line arguments take precedence over .env file values.
        
        Args:
            host: Database host (overrides .env)
            database: Database name (overrides .env)
            user: Database user (overrides .env)
            password: Database password (overrides .env)
            port: Database port (overrides .env)
            
        Returns:
            DatabaseCreator instance
            
        Raises:
            ValueError: If required credentials are missing
        """
        config = {}
        
        # Load from .env file if available
        env_config = cls._load_env_config()
        if env_config:
            config.update(env_config)
            logger.info("Loaded database configuration from .env file")
        
        # Override with command line arguments
        if host is not None:
            config['host'] = host
        if database is not None:
            config['database'] = database
        if user is not None:
            config['user'] = user
        if password is not None:
            config['password'] = password
        if port is not None:
            config['port'] = port
            
        # Validate required parameters
        required_params = ['host', 'database', 'user', 'password']
        missing_params = [param for param in required_params if param not in config]
        
        if missing_params:
            raise ValueError(f"Missing required database parameters: {missing_params}")
            
        return cls(**config)
    
    @staticmethod
    def _load_env_config() -> Optional[Dict[str, Any]]:
        """
        Load database configuration from .env file if available.
        
        Returns:
            Dictionary with database configuration or None if .env not available
        """
        if not DOTENV_AVAILABLE:
            return None

        env_file = Path('.env')
        if not env_file.exists():
            return None

        # Load .env file
        load_dotenv(env_file)

        # Extract database configuration
        config = {}
        env_mappings = {
            'host': 'POSTGRES_HOST',
            'port': 'POSTGRES_PORT',
            'database': 'POSTGRES_DB',
            'user': 'POSTGRES_USER',
            'password': 'POSTGRES_PASSWORD'
        }

        for config_key, env_key in env_mappings.items():
            value = os.getenv(env_key)
            if value:
                config[config_key] = value

        # Convert port to integer if present
        if 'port' in config:
            try:
                config['port'] = int(config['port'])
            except ValueError:
                logger.warning(f"Invalid port value in .env: {config['port']}")
                del config['port']

        return config if config else None
    
    def connect_db(self):
        """
        Establish database connection.
        
        Returns:
            psycopg2 connection object
            
        Raises:
            psycopg2.Error: If connection fails
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test database connection and basic operations.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    # Test basic connection
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result[0] != 1:
                        logger.error("Database connection test failed")
                        return False

                    logger.info("Database connection test successful")
                    return True

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def create_unpaywall_schema(self):
        """
        Create the unpaywall schema if it doesn't exist.

        Raises:
            psycopg2.Error: If schema creation fails
        """
        logger.info("Creating unpaywall schema...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Create unpaywall schema if it doesn't exist
                    cur.execute("CREATE SCHEMA IF NOT EXISTS unpaywall")
                    conn.commit()
                    logger.info("Unpaywall schema created successfully")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Failed to create unpaywall schema: {e}")
                    raise

    def create_lookup_tables(self):
        """
        Create lookup tables for normalized data storage.

        Creates tables for license, oa_status, host_type, and work_type
        to normalize the doi_urls table and save storage space.

        Raises:
            psycopg2.Error: If table creation fails
        """
        logger.info("Creating lookup tables...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # License lookup table
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.license (
                        id SERIAL PRIMARY KEY,
                        value TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)

                    # OA status lookup table
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.oa_status (
                        id SERIAL PRIMARY KEY,
                        value TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)

                    # Host type lookup table
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.host_type (
                        id SERIAL PRIMARY KEY,
                        value TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)

                    # Work type lookup table
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.work_type (
                        id SERIAL PRIMARY KEY,
                        value TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)

                    conn.commit()
                    logger.info("Successfully created lookup tables")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Lookup table creation failed: {e}")
                    raise

    def create_doi_urls_table(self):
        """
        Create the main doi_urls table with normalized structure.

        This table stores DOI-URL mappings with foreign key references
        to lookup tables for efficient storage.

        Raises:
            psycopg2.Error: If table creation fails
        """
        logger.info("Creating unpaywall.doi_urls table...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Create main table with normalized structure
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.doi_urls (
                        id BIGSERIAL PRIMARY KEY,
                        doi TEXT NOT NULL,
                        url TEXT NOT NULL,
                        pdf_url TEXT,
                        openalex_id BIGINT,
                        title TEXT,
                        publication_year INTEGER,
                        location_type CHAR(1) NOT NULL CHECK (location_type IN ('p', 'a', 'b')),
                        version TEXT,
                        license_id INTEGER REFERENCES unpaywall.license(id),
                        host_type_id INTEGER REFERENCES unpaywall.host_type(id),
                        oa_status_id INTEGER REFERENCES unpaywall.oa_status(id),
                        is_oa BOOLEAN DEFAULT FALSE,
                        work_type_id INTEGER REFERENCES unpaywall.work_type(id),
                        is_retracted BOOLEAN DEFAULT FALSE,
                        url_quality_score INTEGER DEFAULT 50,
                        last_verified TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT unique_unpaywall_doi_url UNIQUE(doi, url)
                    )
                    """)

                    conn.commit()
                    logger.info("DOI URLs table created successfully")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"DOI URLs table creation failed: {e}")
                    raise

    def create_import_progress_table(self):
        """
        Create the import_progress table for tracking import operations.

        This table enables resume functionality and import monitoring.

        Raises:
            psycopg2.Error: If table creation fails
        """
        logger.info("Creating unpaywall.import_progress table...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Create import progress tracking table
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.import_progress (
                        import_id TEXT PRIMARY KEY,
                        csv_file_path TEXT NOT NULL,
                        csv_file_hash TEXT NOT NULL,
                        total_rows INTEGER NOT NULL,
                        processed_rows INTEGER DEFAULT 0,
                        last_batch_id INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'in_progress',
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """)

                    conn.commit()
                    logger.info("Import progress table created successfully")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Import progress table creation failed: {e}")
                    raise

    def create_doi_urls_indexes(self):
        """
        Create all indexes for the normalized doi_urls table.

        Creates indexes for optimal query performance based on common access patterns.

        Raises:
            psycopg2.Error: If index creation fails
        """
        logger.info("Creating indexes for unpaywall.doi_urls table...")

        # Define all indexes to create
        indexes = [
            # Primary access patterns
            ("idx_unpaywall_doi_urls_doi", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi ON unpaywall.doi_urls(doi)"),
            ("idx_unpaywall_doi_urls_url", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_url ON unpaywall.doi_urls(url)"),

            # PDF access optimization
            ("idx_unpaywall_doi_urls_pdf_url", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_pdf_url ON unpaywall.doi_urls(pdf_url) WHERE pdf_url IS NOT NULL"),

            # Combined lookups
            ("idx_unpaywall_doi_urls_doi_location_type", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi_location_type ON unpaywall.doi_urls(doi, location_type)"),

            # Foreign key indexes for efficient joins
            ("idx_unpaywall_doi_urls_license_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_license_id ON unpaywall.doi_urls(license_id)"),
            ("idx_unpaywall_doi_urls_oa_status_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_oa_status_id ON unpaywall.doi_urls(oa_status_id)"),
            ("idx_unpaywall_doi_urls_host_type_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_host_type_id ON unpaywall.doi_urls(host_type_id)"),
            ("idx_unpaywall_doi_urls_work_type_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_work_type_id ON unpaywall.doi_urls(work_type_id)"),

            # Other filtering indexes
            ("idx_unpaywall_doi_urls_location_type", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_location_type ON unpaywall.doi_urls(location_type)"),
            ("idx_unpaywall_doi_urls_publication_year", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_publication_year ON unpaywall.doi_urls(publication_year)"),
            ("idx_unpaywall_doi_urls_is_retracted", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_is_retracted ON unpaywall.doi_urls(is_retracted)"),
            ("idx_unpaywall_doi_urls_openalex_work_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_openalex_work_id ON unpaywall.doi_urls(openalex_id)"),
        ]

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    for index_name, index_sql in indexes:
                        logger.debug(f"Creating index: {index_name}")
                        cur.execute(index_sql)

                    conn.commit()
                    logger.info(f"Successfully created {len(indexes)} indexes for doi_urls table")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Index creation failed: {e}")
                    raise

    def create_import_progress_indexes(self):
        """
        Create indexes for the import_progress table.

        Creates indexes for efficient import tracking and monitoring.

        Raises:
            psycopg2.Error: If index creation fails
        """
        logger.info("Creating indexes for unpaywall.import_progress table...")

        # Define indexes for import_progress table
        indexes = [
            ("idx_unpaywall_import_progress_file_path", "CREATE INDEX IF NOT EXISTS idx_unpaywall_import_progress_file_path ON unpaywall.import_progress(csv_file_path)"),
            ("idx_unpaywall_import_progress_status", "CREATE INDEX IF NOT EXISTS idx_unpaywall_import_progress_status ON unpaywall.import_progress(status)"),
        ]

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    for index_name, index_sql in indexes:
                        logger.debug(f"Creating index: {index_name}")
                        cur.execute(index_sql)

                    conn.commit()
                    logger.info(f"Successfully created {len(indexes)} indexes for import_progress table")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Index creation failed: {e}")
                    raise

    def get_or_create_lookup_id(self, table_name: str, value: str) -> Optional[int]:
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

        value = value.strip()

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Try to get existing ID
                    cur.execute(f"""
                    SELECT id FROM unpaywall.{table_name} WHERE value = %s
                    """, (value,))

                    result = cur.fetchone()
                    if result:
                        return result[0]

                    # Create new entry
                    cur.execute(f"""
                    INSERT INTO unpaywall.{table_name} (value)
                    VALUES (%s) RETURNING id
                    """, (value,))

                    new_id = cur.fetchone()[0]
                    conn.commit()
                    return new_id

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Failed to get/create lookup ID for {table_name}.{value}: {e}")
                    return None



    def normalize_location_type(self):
        """
        Convert location_type from TEXT to CHAR(1) with normalized values.

        Maps: 'primary' -> 'p', 'alternate' -> 'a', 'best_oa' -> 'b'

        Raises:
            psycopg2.Error: If normalization fails
        """
        logger.info("Normalizing location_type column...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Add new CHAR(1) column
                    cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_schema = 'unpaywall'
                        AND table_name = 'doi_urls'
                        AND column_name = 'location_type_new'
                    )
                    """)

                    if not cur.fetchone()[0]:
                        logger.debug("Adding location_type_new column")
                        cur.execute("""
                        ALTER TABLE unpaywall.doi_urls
                        ADD COLUMN location_type_new CHAR(1)
                        """)

                    # Update with normalized values
                    logger.debug("Updating location_type_new with normalized values")
                    cur.execute("""
                    UPDATE unpaywall.doi_urls
                    SET location_type_new = CASE
                        WHEN LOWER(location_type) = 'primary' THEN 'p'
                        WHEN LOWER(location_type) = 'alternate' THEN 'a'
                        WHEN LOWER(location_type) = 'best_oa' THEN 'b'
                        ELSE 'p'  -- Default to primary for unknown values
                    END
                    """)

                    updated_rows = cur.rowcount
                    logger.info(f"Updated {updated_rows} rows for location_type normalization")

                    conn.commit()
                    logger.info("Successfully normalized location_type column")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Location type normalization failed: {e}")
                    raise

    def finalize_normalization(self):
        """
        Finalize the normalization by dropping old TEXT columns and renaming new ones.

        This method completes the normalization process by:
        1. Dropping the old TEXT columns (license, oa_status, host_type, work_type)
        2. Renaming location_type_new to location_type
        3. Adding NOT NULL constraints where appropriate

        Raises:
            psycopg2.Error: If finalization fails
        """
        logger.info("Finalizing database normalization...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Drop old TEXT columns
                    old_columns = ['license', 'oa_status', 'host_type', 'work_type']
                    for column in old_columns:
                        logger.debug(f"Dropping old column: {column}")
                        cur.execute(f"""
                        ALTER TABLE unpaywall.doi_urls
                        DROP COLUMN IF EXISTS {column}
                        """)

                    # Drop old location_type and rename new one
                    logger.debug("Replacing location_type column")
                    cur.execute("""
                    ALTER TABLE unpaywall.doi_urls
                    DROP COLUMN IF EXISTS location_type
                    """)

                    cur.execute("""
                    ALTER TABLE unpaywall.doi_urls
                    RENAME COLUMN location_type_new TO location_type
                    """)

                    # Add NOT NULL constraint to location_type
                    cur.execute("""
                    ALTER TABLE unpaywall.doi_urls
                    ALTER COLUMN location_type SET NOT NULL
                    """)

                    # Add check constraint for location_type values
                    cur.execute("""
                    ALTER TABLE unpaywall.doi_urls
                    ADD CONSTRAINT chk_location_type
                    CHECK (location_type IN ('p', 'a', 'b'))
                    """)

                    conn.commit()
                    logger.info("Successfully finalized database normalization")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Normalization finalization failed: {e}")
                    raise

    def create_normalized_indexes(self):
        """
        Create indexes for the normalized foreign key columns.

        Creates indexes on the new foreign key columns to maintain query performance.

        Raises:
            psycopg2.Error: If index creation fails
        """
        logger.info("Creating indexes for normalized columns...")

        # Define indexes for foreign key columns
        indexes = [
            ("idx_unpaywall_doi_urls_license_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_license_id ON unpaywall.doi_urls(license_id)"),
            ("idx_unpaywall_doi_urls_oa_status_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_oa_status_id ON unpaywall.doi_urls(oa_status_id)"),
            ("idx_unpaywall_doi_urls_host_type_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_host_type_id ON unpaywall.doi_urls(host_type_id)"),
            ("idx_unpaywall_doi_urls_work_type_id", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_work_type_id ON unpaywall.doi_urls(work_type_id)"),
            ("idx_unpaywall_doi_urls_location_type", "CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_location_type ON unpaywall.doi_urls(location_type)"),
        ]

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    for index_name, index_sql in indexes:
                        logger.debug(f"Creating index: {index_name}")
                        cur.execute(index_sql)

                    conn.commit()
                    logger.info(f"Successfully created {len(indexes)} indexes for normalized columns")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Normalized index creation failed: {e}")
                    raise

    def set_permissions(self):
        """
        Set appropriate permissions for the unpaywall schema and tables.

        Grants public access to the schema and tables for general use.

        Raises:
            psycopg2.Error: If permission setting fails
        """
        logger.info("Setting permissions for unpaywall schema...")

        with self.connect_db() as conn:
            with conn.cursor() as cur:
                try:
                    # Schema access
                    cur.execute("GRANT USAGE ON SCHEMA unpaywall TO PUBLIC")

                    # Main table permissions
                    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.doi_urls TO PUBLIC")
                    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON unpaywall.import_progress TO PUBLIC")

                    # Lookup table permissions (typically read-only for most users)
                    lookup_tables = ['license', 'oa_status', 'host_type', 'work_type']
                    for table in lookup_tables:
                        cur.execute(f"GRANT SELECT ON unpaywall.{table} TO PUBLIC")
                        # Grant full access to specific roles if needed
                        cur.execute(f"GRANT INSERT, UPDATE, DELETE ON unpaywall.{table} TO PUBLIC")

                    # Sequence permissions
                    cur.execute("GRANT USAGE, SELECT ON SEQUENCE unpaywall.doi_urls_id_seq TO PUBLIC")

                    # Lookup table sequence permissions
                    for table in lookup_tables:
                        cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE unpaywall.{table}_id_seq TO PUBLIC")

                    conn.commit()
                    logger.info("Permissions set successfully")

                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Permission setting failed: {e}")
                    raise

    def verify_schema(self) -> bool:
        """
        Verify that all schema components have been created successfully.

        Returns:
            True if all components exist, False otherwise
        """
        logger.info("Verifying schema creation...")

        try:
            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    # Check schema exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.schemata
                            WHERE schema_name = 'unpaywall'
                        )
                    """)
                    schema_exists = cur.fetchone()[0]
                    if not schema_exists:
                        logger.error("unpaywall schema does not exist")
                        return False

                    # Check tables exist
                    tables = ['doi_urls', 'import_progress']
                    for table in tables:
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables
                                WHERE table_schema = 'unpaywall' AND table_name = %s
                            )
                        """, (table,))
                        table_exists = cur.fetchone()[0]
                        if not table_exists:
                            logger.error(f"unpaywall.{table} table does not exist")
                            return False

                    # Check unique constraint exists
                    cur.execute("""
                        SELECT COUNT(*) FROM pg_constraint
                        WHERE conname = 'unique_unpaywall_doi_url' AND conrelid = 'unpaywall.doi_urls'::regclass
                    """)
                    has_constraint = cur.fetchone()[0] > 0
                    if not has_constraint:
                        logger.error("unique_unpaywall_doi_url constraint does not exist")
                        return False

                    # Get row counts for verification
                    cur.execute("SELECT COUNT(*) FROM unpaywall.doi_urls")
                    doi_urls_count = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM unpaywall.import_progress")
                    import_progress_count = cur.fetchone()[0]

                    logger.info(f"Schema verification successful:")
                    logger.info(f"  - unpaywall.doi_urls: {doi_urls_count:,} rows")
                    logger.info(f"  - unpaywall.import_progress: {import_progress_count:,} rows")

                    return True

        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            return False

    def create_complete_schema(self, verify: bool = True) -> bool:
        """
        Create the complete unpaywall database schema.

        This method orchestrates the creation of all schema components:
        - Schema namespace
        - Tables with constraints
        - Indexes
        - Permissions

        Args:
            verify: Whether to verify schema creation (default: True)

        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting complete schema creation for unpaywall...")

        try:
            # Test connection first
            if not self.test_connection():
                logger.error("Database connection test failed - cannot proceed")
                return False

            # Create schema components in order
            self.create_unpaywall_schema()
            self.create_lookup_tables()
            self.create_doi_urls_table()
            self.create_import_progress_table()
            self.create_doi_urls_indexes()
            self.create_import_progress_indexes()
            self.set_permissions()

            # Verify creation if requested
            if verify:
                if not self.verify_schema():
                    logger.error("Schema verification failed")
                    return False

            logger.info("Complete schema creation successful!")
            return True

        except Exception as e:
            logger.error(f"Complete schema creation failed: {e}")
            return False

    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get information about the current schema state.

        Returns:
            Dictionary with schema information
        """
        info = {
            'schema_exists': False,
            'tables': {},
            'indexes': {},
            'constraints': {},
            'row_counts': {}
        }

        try:
            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    # Check schema
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.schemata
                            WHERE schema_name = 'unpaywall'
                        )
                    """)
                    info['schema_exists'] = cur.fetchone()[0]

                    if info['schema_exists']:
                        # Check tables
                        tables = ['doi_urls', 'import_progress']
                        for table in tables:
                            cur.execute("""
                                SELECT EXISTS (
                                    SELECT FROM information_schema.tables
                                    WHERE table_schema = 'unpaywall' AND table_name = %s
                                )
                            """, (table,))
                            info['tables'][table] = cur.fetchone()[0]

                            # Get row count if table exists
                            if info['tables'][table]:
                                cur.execute(f"SELECT COUNT(*) FROM unpaywall.{table}")
                                info['row_counts'][table] = cur.fetchone()[0]

                        # Check constraints
                        cur.execute("""
                            SELECT COUNT(*) FROM pg_constraint
                            WHERE conname = 'unique_unpaywall_doi_url' AND conrelid = 'unpaywall.doi_urls'::regclass
                        """)
                        info['constraints']['unique_unpaywall_doi_url'] = cur.fetchone()[0] > 0

        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")

        return info


def main():
    """
    Command-line interface for database schema creation.

    Supports both .env file and command-line argument configuration.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Create unpaywall database schema',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create schema with command line arguments
  python db/create_db.py --db-name mydb --db-user myuser --db-password mypass

  # Create schema using .env file (database args optional)
  python db/create_db.py

  # Get schema information
  python db/create_db.py --info

  # Test connection only
  python db/create_db.py --test-only
        """
    )

    parser.add_argument('--db-host', help='Database host (default: localhost)')
    parser.add_argument('--db-port', type=int, help='Database port (default: 5432)')
    parser.add_argument('--db-name', help='Database name')
    parser.add_argument('--db-user', help='Database user')
    parser.add_argument('--db-password', help='Database password')
    parser.add_argument('--info', action='store_true', help='Show schema information')
    parser.add_argument('--test-only', action='store_true', help='Test connection only')
    parser.add_argument('--no-verify', action='store_true', help='Skip schema verification')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    try:
        # Create DatabaseCreator instance
        creator = DatabaseCreator.from_env_or_args(
            host=args.db_host,
            database=args.db_name,
            user=args.db_user,
            password=args.db_password,
            port=args.db_port
        )

        if args.test_only:
            # Test connection only
            success = creator.test_connection()
            if success:
                print("✓ Database connection successful")
                sys.exit(0)
            else:
                print("✗ Database connection failed")
                sys.exit(1)

        elif args.info:
            # Show schema information
            info = creator.get_schema_info()
            print("\nUnpaywall Schema Information:")
            print("=" * 40)
            print(f"Schema exists: {'✓' if info['schema_exists'] else '✗'}")

            if info['schema_exists']:
                print("\nTables:")
                for table, exists in info['tables'].items():
                    status = '✓' if exists else '✗'
                    count = info['row_counts'].get(table, 0)
                    print(f"  {table}: {status} ({count:,} rows)")

                print("\nConstraints:")
                for constraint, exists in info['constraints'].items():
                    status = '✓' if exists else '✗'
                    print(f"  {constraint}: {status}")

            sys.exit(0)

        else:
            # Create complete schema
            verify = not args.no_verify
            success = creator.create_complete_schema(verify=verify)

            if success:
                print("✓ Schema creation completed successfully")
                sys.exit(0)
            else:
                print("✗ Schema creation failed")
                sys.exit(1)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\nError: {e}")
        print("\nEither provide database credentials via command line arguments")
        print("or create a .env file with POSTGRES_* variables.")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Schema creation interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Schema creation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
