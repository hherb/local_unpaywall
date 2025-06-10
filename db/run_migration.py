#!/usr/bin/env python3
"""
Database Migration Runner

Runs database migrations in order. Currently supports migration 001 which
integrates work_type and is_retracted fields into the main doi_urls table.
"""

import argparse
import logging
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path to import database connection utilities
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database migrations"""
    
    def __init__(self, db_host: str, db_name: str, db_user: str, db_password: str, db_port: int = 5432):
        self.db_config = {
            'host': db_host,
            'database': db_name,
            'user': db_user,
            'password': db_password,
            'port': db_port
        }
        self.migrations_dir = Path(__file__).parent / 'migrations'
    
    def connect_db(self):
        """Create database connection"""
        try:
            return psycopg2.connect(**self.db_config)
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def create_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        with self.connect_db() as conn:
            with conn.cursor() as cur:
                # Create unpaywall schema first
                cur.execute("CREATE SCHEMA IF NOT EXISTS unpaywall")

                # Create migrations table in unpaywall schema
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS unpaywall.schema_migrations (
                        migration_id TEXT PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        description TEXT
                    )
                """)
                conn.commit()
                logger.info("Unpaywall migrations tracking table ready")
    
    def get_applied_migrations(self):
        """Get list of already applied migrations"""
        try:
            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT migration_id FROM unpaywall.schema_migrations ORDER BY migration_id")
                    return [row[0] for row in cur.fetchall()]
        except psycopg2.Error:
            # Table might not exist yet
            return []
    
    def run_migration(self, migration_file: Path, force: bool = False):
        """Run a single migration file"""
        migration_id = migration_file.stem
        
        # Check if already applied
        applied_migrations = self.get_applied_migrations()
        if migration_id in applied_migrations and not force:
            logger.info(f"Migration {migration_id} already applied, skipping")
            return True
        
        logger.info(f"Running migration: {migration_id}")
        
        # Read migration SQL
        try:
            sql_content = migration_file.read_text()
        except Exception as e:
            logger.error(f"Failed to read migration file {migration_file}: {e}")
            return False
        
        # Execute migration
        try:
            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    # Execute the migration SQL
                    cur.execute(sql_content)
                    
                    # Record the migration as applied
                    cur.execute("""
                        INSERT INTO unpaywall.schema_migrations (migration_id, description)
                        VALUES (%s, %s)
                        ON CONFLICT (migration_id) DO UPDATE SET
                            applied_at = CURRENT_TIMESTAMP
                    """, (migration_id, f"Migration from {migration_file.name}"))
                    
                    conn.commit()
                    logger.info(f"Migration {migration_id} completed successfully")
                    return True
                    
        except psycopg2.Error as e:
            logger.error(f"Migration {migration_id} failed: {e}")
            return False
    
    def run_all_migrations(self, force: bool = False):
        """Run all pending migrations"""
        if not self.migrations_dir.exists():
            logger.error(f"Migrations directory not found: {self.migrations_dir}")
            return False
        
        # Create migrations table
        self.create_migrations_table()
        
        # Find all migration files
        migration_files = sorted(self.migrations_dir.glob("*.sql"))
        
        if not migration_files:
            logger.info("No migration files found")
            return True
        
        logger.info(f"Found {len(migration_files)} migration files")
        
        success = True
        for migration_file in migration_files:
            if not self.run_migration(migration_file, force):
                success = False
                break
        
        return success
    
    def list_migrations(self):
        """List all migrations and their status"""
        applied_migrations = self.get_applied_migrations()
        migration_files = sorted(self.migrations_dir.glob("*.sql"))
        
        print("\nMigration Status:")
        print("-" * 50)
        
        for migration_file in migration_files:
            migration_id = migration_file.stem
            status = "APPLIED" if migration_id in applied_migrations else "PENDING"
            print(f"{migration_id}: {status}")
        
        if applied_migrations:
            print(f"\nApplied migrations: {len(applied_migrations)}")
            print(f"Pending migrations: {len(migration_files) - len(applied_migrations)}")
        else:
            print(f"\nNo migrations applied yet")
            print(f"Total migrations available: {len(migration_files)}")


def main():
    parser = argparse.ArgumentParser(description='Run database migrations')
    parser.add_argument('--db-host', default='localhost', help='Database host')
    parser.add_argument('--db-name', required=True, help='Database name')
    parser.add_argument('--db-user', required=True, help='Database user')
    parser.add_argument('--db-password', required=True, help='Database password')
    parser.add_argument('--db-port', type=int, default=5432, help='Database port')
    parser.add_argument('--list', action='store_true', help='List migration status')
    parser.add_argument('--force', action='store_true', help='Force re-run applied migrations')
    parser.add_argument('--migration', help='Run specific migration by ID')
    
    args = parser.parse_args()
    
    runner = MigrationRunner(
        db_host=args.db_host,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        db_port=args.db_port
    )
    
    try:
        if args.list:
            runner.list_migrations()
        elif args.migration:
            migration_file = runner.migrations_dir / f"{args.migration}.sql"
            if not migration_file.exists():
                logger.error(f"Migration file not found: {migration_file}")
                sys.exit(1)
            success = runner.run_migration(migration_file, args.force)
            sys.exit(0 if success else 1)
        else:
            success = runner.run_all_migrations(args.force)
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
