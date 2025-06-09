#!/usr/bin/env python3
"""
Database Normalization Script
============================

This script normalizes the unpaywall database to save storage space by:
1. Creating lookup tables for license, oa_status, host_type, work_type
2. Converting location_type from TEXT to CHAR(1)
3. Replacing TEXT columns with foreign key references

For a database with 250 million rows, this can save 17-40 GB of storage space.

Usage:
    python normalize_database.py [options]

Examples:
    # Normalize using .env file credentials
    python normalize_database.py

    # Normalize with explicit credentials
    python normalize_database.py --db-host localhost --db-name unpaywall --db-user myuser --db-password mypass

    # Check current status
    python normalize_database.py --status

    # Finalize normalization (drops old columns)
    python normalize_database.py --finalize
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from db.create_db import DatabaseCreator


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )


def check_normalization_status(creator: DatabaseCreator) -> dict:
    """
    Check the current status of database normalization.
    
    Returns:
        Dictionary with status information
    """
    logger = logging.getLogger(__name__)
    status = {
        'lookup_tables_exist': False,
        'foreign_keys_exist': False,
        'old_columns_exist': False,
        'location_type_normalized': False,
        'ready_for_finalization': False
    }
    
    try:
        with creator.connect_db() as conn:
            with conn.cursor() as cur:
                # Check if lookup tables exist
                lookup_tables = ['license', 'oa_status', 'host_type', 'work_type']
                tables_exist = 0
                for table in lookup_tables:
                    cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'unpaywall' AND table_name = %s
                    )
                    """, (table,))
                    if cur.fetchone()[0]:
                        tables_exist += 1
                
                status['lookup_tables_exist'] = tables_exist == len(lookup_tables)
                
                # Check if foreign key columns exist
                fk_columns = ['license_id', 'oa_status_id', 'host_type_id', 'work_type_id']
                fk_exist = 0
                for column in fk_columns:
                    cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'unpaywall' 
                        AND table_name = 'doi_urls' 
                        AND column_name = %s
                    )
                    """, (column,))
                    if cur.fetchone()[0]:
                        fk_exist += 1
                
                status['foreign_keys_exist'] = fk_exist == len(fk_columns)
                
                # Check if old TEXT columns still exist
                old_columns = ['license', 'oa_status', 'host_type', 'work_type']
                old_exist = 0
                for column in old_columns:
                    cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'unpaywall' 
                        AND table_name = 'doi_urls' 
                        AND column_name = %s
                    )
                    """, (column,))
                    if cur.fetchone()[0]:
                        old_exist += 1
                
                status['old_columns_exist'] = old_exist > 0
                
                # Check location_type status
                cur.execute("""
                SELECT data_type, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_schema = 'unpaywall' 
                AND table_name = 'doi_urls' 
                AND column_name = 'location_type'
                """)
                result = cur.fetchone()
                if result:
                    status['location_type_normalized'] = (result[0] == 'character' and result[1] == 1)
                
                # Check if ready for finalization
                status['ready_for_finalization'] = (
                    status['lookup_tables_exist'] and 
                    status['foreign_keys_exist'] and 
                    status['old_columns_exist']
                )
                
    except Exception as e:
        logger.error(f"Failed to check normalization status: {e}")
    
    return status


def print_status(status: dict):
    """Print the normalization status in a readable format."""
    print("\nDatabase Normalization Status:")
    print("=" * 40)
    
    print(f"Lookup tables exist: {'✓' if status['lookup_tables_exist'] else '✗'}")
    print(f"Foreign key columns exist: {'✓' if status['foreign_keys_exist'] else '✗'}")
    print(f"Old TEXT columns exist: {'✓' if status['old_columns_exist'] else '✗'}")
    print(f"Location type normalized: {'✓' if status['location_type_normalized'] else '✗'}")
    
    if status['ready_for_finalization']:
        print("\n🟡 Ready for finalization (run with --finalize)")
    elif not status['lookup_tables_exist']:
        print("\n🔴 Normalization not started (run without --finalize)")
    elif not status['old_columns_exist']:
        print("\n🟢 Normalization completed")
    else:
        print("\n🟡 Normalization in progress")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Normalize unpaywall database for storage efficiency',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--db-host', help='Database host')
    parser.add_argument('--db-port', type=int, help='Database port')
    parser.add_argument('--db-name', help='Database name')
    parser.add_argument('--db-user', help='Database user')
    parser.add_argument('--db-password', help='Database password')
    parser.add_argument('--status', action='store_true', help='Check normalization status')
    parser.add_argument('--finalize', action='store_true', help='Finalize normalization (drops old columns)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Create DatabaseCreator instance
        creator = DatabaseCreator.from_env_or_args(
            host=args.db_host,
            database=args.db_name,
            user=args.db_user,
            password=args.db_password,
            port=args.db_port
        )
        
        if args.status:
            # Show status only
            status = check_normalization_status(creator)
            print_status(status)
            sys.exit(0)
        
        elif args.finalize:
            # Finalize normalization
            logger.info("Finalizing database normalization...")
            
            # Check if ready for finalization
            status = check_normalization_status(creator)
            if not status['ready_for_finalization']:
                print("❌ Database is not ready for finalization.")
                print("Run the initial normalization first (without --finalize)")
                sys.exit(1)
            
            # Confirm finalization
            print("⚠️  WARNING: Finalization will permanently delete old TEXT columns.")
            print("Make sure you have verified the normalization worked correctly.")
            response = input("Continue with finalization? (yes/no): ")
            
            if response.lower() != 'yes':
                print("Finalization cancelled.")
                sys.exit(0)
            
            # Run finalization
            success = creator.finalize_normalization()
            if success:
                print("✅ Database normalization finalized successfully!")
                print("   - Old TEXT columns have been dropped")
                print("   - Location type converted to CHAR(1)")
                print("   - Backward compatibility view created")
            else:
                print("❌ Finalization failed")
                sys.exit(1)
        
        else:
            # Run initial normalization
            logger.info("Starting database normalization...")
            
            # Check current status
            status = check_normalization_status(creator)
            if not status['old_columns_exist'] and status['lookup_tables_exist']:
                print("✅ Database normalization already completed!")
                sys.exit(0)
            
            # Run normalization
            success = creator.normalize_database(verify=True)
            
            if success:
                print("✅ Database normalization completed successfully!")
                print("   - Created lookup tables for license, oa_status, host_type, work_type")
                print("   - Added foreign key columns")
                print("   - Prepared location_type for conversion")
                print("   - Storage space will be significantly reduced")
                print("")
                print("🔄 Next step: Verify the migration worked correctly, then run:")
                print("   python normalize_database.py --finalize")
            else:
                print("❌ Database normalization failed")
                sys.exit(1)
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\nError: {e}")
        print("Either provide database credentials via command line arguments")
        print("or create a .env file with POSTGRES_* variables.")
        sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Normalization interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
