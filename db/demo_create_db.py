#!/usr/bin/env python3
"""
Database Creation Module Demo
=============================

This script demonstrates the usage of the DatabaseCreator module
for creating and managing the unpaywall database schema.

This is a demonstration script that shows various features without
actually connecting to a real database.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from db.create_db import DatabaseCreator


def demo_configuration_methods():
    """Demonstrate different ways to configure DatabaseCreator."""
    print("=" * 60)
    print("DATABASE CREATOR CONFIGURATION DEMO")
    print("=" * 60)
    
    print("\n1. Direct instantiation:")
    print("-" * 30)
    try:
        creator = DatabaseCreator(
            host='localhost',
            database='demo_db',
            user='demo_user',
            password='demo_pass',
            port=5432
        )
        print(f"✓ Created DatabaseCreator with config: {creator.db_config}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n2. From environment/args (will fail without credentials):")
    print("-" * 30)
    try:
        creator = DatabaseCreator.from_env_or_args(
            host='localhost',
            database='demo_db'
            # Missing user and password - should fail
        )
        print(f"✓ Created DatabaseCreator: {creator.db_config}")
    except ValueError as e:
        print(f"✗ Expected error (missing credentials): {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    
    print("\n3. Complete configuration from args:")
    print("-" * 30)
    try:
        creator = DatabaseCreator.from_env_or_args(
            host='localhost',
            database='demo_db',
            user='demo_user',
            password='demo_pass',
            port=5432
        )
        print(f"✓ Created DatabaseCreator with complete config")
        print(f"  Host: {creator.db_config['host']}")
        print(f"  Database: {creator.db_config['database']}")
        print(f"  User: {creator.db_config['user']}")
        print(f"  Port: {creator.db_config['port']}")
    except Exception as e:
        print(f"✗ Error: {e}")


def demo_schema_info_structure():
    """Demonstrate the schema info structure."""
    print("\n" + "=" * 60)
    print("SCHEMA INFO STRUCTURE DEMO")
    print("=" * 60)
    
    # Create a mock schema info structure to show what it looks like
    mock_schema_info = {
        'schema_exists': True,
        'tables': {
            'doi_urls': True,
            'import_progress': True
        },
        'indexes': {
            'idx_unpaywall_doi_urls_doi': True,
            'idx_unpaywall_doi_urls_url': True,
            'idx_unpaywall_doi_urls_pdf_url': True,
            # ... more indexes
        },
        'constraints': {
            'unique_unpaywall_doi_url': True
        },
        'row_counts': {
            'doi_urls': 1234567,
            'import_progress': 15
        }
    }
    
    print("\nExample schema info structure:")
    print("-" * 30)
    print(f"Schema exists: {mock_schema_info['schema_exists']}")
    print("\nTables:")
    for table, exists in mock_schema_info['tables'].items():
        status = '✓' if exists else '✗'
        count = mock_schema_info['row_counts'].get(table, 0)
        print(f"  {table}: {status} ({count:,} rows)")
    
    print("\nConstraints:")
    for constraint, exists in mock_schema_info['constraints'].items():
        status = '✓' if exists else '✗'
        print(f"  {constraint}: {status}")


def demo_method_overview():
    """Demonstrate the available methods and their purposes."""
    print("\n" + "=" * 60)
    print("AVAILABLE METHODS OVERVIEW")
    print("=" * 60)
    
    methods = [
        ("Configuration Methods", [
            ("DatabaseCreator()", "Direct instantiation with credentials"),
            ("from_env_or_args()", "Create from .env file with CLI overrides"),
            ("_load_env_config()", "Load configuration from .env file"),
        ]),
        ("Connection Methods", [
            ("connect_db()", "Establish database connection"),
            ("test_connection()", "Test database connectivity"),
        ]),
        ("Schema Creation Methods", [
            ("create_unpaywall_schema()", "Create unpaywall namespace"),
            ("create_doi_urls_table()", "Create main DOI-URL table"),
            ("create_import_progress_table()", "Create import tracking table"),
        ]),
        ("Index Management Methods", [
            ("create_doi_urls_indexes()", "Create all DOI-URL table indexes"),
            ("create_import_progress_indexes()", "Create import progress indexes"),
        ]),
        ("Orchestration Methods", [
            ("create_complete_schema()", "Create complete schema in order"),
            ("verify_schema()", "Verify all components exist"),
            ("set_permissions()", "Set database permissions"),
            ("get_schema_info()", "Get current schema state"),
        ]),
    ]
    
    for category, method_list in methods:
        print(f"\n{category}:")
        print("-" * len(category))
        for method, description in method_list:
            print(f"  {method:<35} - {description}")


def demo_usage_patterns():
    """Demonstrate common usage patterns."""
    print("\n" + "=" * 60)
    print("COMMON USAGE PATTERNS")
    print("=" * 60)
    
    print("\n1. Complete Schema Creation:")
    print("-" * 30)
    print("""
from db.create_db import DatabaseCreator

# Create instance
creator = DatabaseCreator.from_env_or_args(
    database='mydb',
    user='myuser',
    password='mypass'
)

# Create complete schema
success = creator.create_complete_schema()
if success:
    print("Schema created successfully!")
else:
    print("Schema creation failed!")
""")
    
    print("\n2. Schema Information Gathering:")
    print("-" * 30)
    print("""
# Get schema information
info = creator.get_schema_info()
print(f"Schema exists: {info['schema_exists']}")
print(f"Tables: {info['tables']}")
print(f"Row counts: {info['row_counts']}")
""")
    
    print("\n3. Connection Testing:")
    print("-" * 30)
    print("""
# Test connection before operations
if creator.test_connection():
    print("Database connection successful")
    # Proceed with schema operations
else:
    print("Database connection failed")
    # Handle connection error
""")
    
    print("\n4. Integration with DOI URL Importer:")
    print("-" * 30)
    print("""
# In doi_url_importer.py
def create_schema(self):
    creator = DatabaseCreator(**self.db_config)
    success = creator.create_complete_schema(verify=True)
    if not success:
        raise RuntimeError("Schema creation failed")
""")


def demo_command_line_usage():
    """Demonstrate command-line usage."""
    print("\n" + "=" * 60)
    print("COMMAND-LINE USAGE EXAMPLES")
    print("=" * 60)
    
    examples = [
        ("Create schema with explicit credentials",
         "python db/create_db.py --db-name mydb --db-user myuser --db-password mypass"),
        
        ("Create schema using .env file",
         "python db/create_db.py"),
        
        ("Test connection only",
         "python db/create_db.py --test-only"),
        
        ("Get schema information",
         "python db/create_db.py --info"),
        
        ("Create schema with verbose output",
         "python db/create_db.py --verbose"),
        
        ("Create schema without verification",
         "python db/create_db.py --no-verify"),
    ]
    
    for description, command in examples:
        print(f"\n{description}:")
        print(f"  {command}")


def main():
    """Run all demonstrations."""
    print("DATABASE CREATOR MODULE DEMONSTRATION")
    print("=" * 60)
    print("This demo shows the features and usage of the DatabaseCreator module")
    print("without actually connecting to a database.")
    
    demo_configuration_methods()
    demo_schema_info_structure()
    demo_method_overview()
    demo_usage_patterns()
    demo_command_line_usage()
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nFor actual database operations, ensure you have:")
    print("1. PostgreSQL server running")
    print("2. Valid database credentials")
    print("3. Appropriate database permissions")
    print("\nRefer to manual/database_creation_module.md for detailed documentation.")


if __name__ == '__main__':
    main()
