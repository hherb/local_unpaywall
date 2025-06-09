#!/usr/bin/env python3
"""
Unit tests for the DatabaseCreator module.

These tests verify that the DatabaseCreator class works correctly
for schema creation and management.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from db.create_db import DatabaseCreator


class TestDatabaseCreator(unittest.TestCase):
    """Test cases for DatabaseCreator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db_config = {
            'host': 'localhost',
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_pass',
            'port': 5432
        }
        self.creator = DatabaseCreator(**self.db_config)
    
    def test_init(self):
        """Test DatabaseCreator initialization."""
        self.assertEqual(self.creator.db_config['host'], 'localhost')
        self.assertEqual(self.creator.db_config['database'], 'test_db')
        self.assertEqual(self.creator.db_config['user'], 'test_user')
        self.assertEqual(self.creator.db_config['password'], 'test_pass')
        self.assertEqual(self.creator.db_config['port'], 5432)
    
    @patch('db.create_db.load_dotenv')
    @patch('db.create_db.Path')
    @patch('db.create_db.os.getenv')
    def test_load_env_config_success(self, mock_getenv, mock_path, mock_load_dotenv):
        """Test successful loading of .env configuration."""
        # Mock .env file exists
        mock_env_file = Mock()
        mock_env_file.exists.return_value = True
        mock_path.return_value = mock_env_file
        
        # Mock environment variables
        env_vars = {
            'POSTGRES_HOST': 'env_host',
            'POSTGRES_PORT': '5433',
            'POSTGRES_DB': 'env_db',
            'POSTGRES_USER': 'env_user',
            'POSTGRES_PASSWORD': 'env_pass'
        }
        mock_getenv.side_effect = lambda key: env_vars.get(key)
        
        config = DatabaseCreator._load_env_config()
        
        expected = {
            'host': 'env_host',
            'port': 5433,
            'database': 'env_db',
            'user': 'env_user',
            'password': 'env_pass'
        }
        self.assertEqual(config, expected)
    
    @patch('db.create_db.Path')
    def test_load_env_config_no_file(self, mock_path):
        """Test .env config loading when file doesn't exist."""
        # Mock .env file doesn't exist
        mock_env_file = Mock()
        mock_env_file.exists.return_value = False
        mock_path.return_value = mock_env_file
        
        config = DatabaseCreator._load_env_config()
        self.assertIsNone(config)
    
    def test_from_env_or_args_with_args(self):
        """Test creating instance with command line arguments."""
        creator = DatabaseCreator.from_env_or_args(
            host='arg_host',
            database='arg_db',
            user='arg_user',
            password='arg_pass',
            port=5434
        )
        
        self.assertEqual(creator.db_config['host'], 'arg_host')
        self.assertEqual(creator.db_config['database'], 'arg_db')
        self.assertEqual(creator.db_config['user'], 'arg_user')
        self.assertEqual(creator.db_config['password'], 'arg_pass')
        self.assertEqual(creator.db_config['port'], 5434)
    
    def test_from_env_or_args_missing_params(self):
        """Test error when required parameters are missing."""
        with self.assertRaises(ValueError) as context:
            DatabaseCreator.from_env_or_args(host='localhost')
        
        self.assertIn("Missing required database parameters", str(context.exception))
    
    @patch('db.create_db.psycopg2.connect')
    def test_connect_db_success(self, mock_connect):
        """Test successful database connection."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        conn = self.creator.connect_db()
        
        mock_connect.assert_called_once_with(**self.db_config)
        self.assertEqual(conn, mock_conn)
    
    @patch('db.create_db.psycopg2.connect')
    def test_connect_db_failure(self, mock_connect):
        """Test database connection failure."""
        import psycopg2
        mock_connect.side_effect = psycopg2.Error("Connection failed")
        
        with self.assertRaises(psycopg2.Error):
            self.creator.connect_db()
    
    @patch.object(DatabaseCreator, 'connect_db')
    def test_test_connection_success(self, mock_connect_db):
        """Test successful connection test."""
        # Mock database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = [1]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect_db.return_value.__enter__.return_value = mock_conn
        
        result = self.creator.test_connection()
        
        self.assertTrue(result)
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @patch.object(DatabaseCreator, 'connect_db')
    def test_test_connection_failure(self, mock_connect_db):
        """Test connection test failure."""
        mock_connect_db.side_effect = Exception("Connection failed")
        
        result = self.creator.test_connection()
        
        self.assertFalse(result)
    
    @patch.object(DatabaseCreator, 'connect_db')
    def test_create_unpaywall_schema(self, mock_connect_db):
        """Test unpaywall schema creation."""
        # Mock database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect_db.return_value.__enter__.return_value = mock_conn
        
        self.creator.create_unpaywall_schema()
        
        mock_cursor.execute.assert_called_once_with("CREATE SCHEMA IF NOT EXISTS unpaywall")
        mock_conn.commit.assert_called_once()
    
    @patch.object(DatabaseCreator, 'test_connection')
    @patch.object(DatabaseCreator, 'create_unpaywall_schema')
    @patch.object(DatabaseCreator, 'create_doi_urls_table')
    @patch.object(DatabaseCreator, 'create_import_progress_table')
    @patch.object(DatabaseCreator, 'create_doi_urls_indexes')
    @patch.object(DatabaseCreator, 'create_import_progress_indexes')
    @patch.object(DatabaseCreator, 'set_permissions')
    @patch.object(DatabaseCreator, 'verify_schema')
    def test_create_complete_schema_success(self, mock_verify, mock_permissions,
                                          mock_import_indexes, mock_doi_indexes,
                                          mock_import_table, mock_doi_table,
                                          mock_schema, mock_test):
        """Test successful complete schema creation."""
        # Mock all methods to succeed
        mock_test.return_value = True
        mock_verify.return_value = True
        
        result = self.creator.create_complete_schema()
        
        self.assertTrue(result)
        mock_test.assert_called_once()
        mock_schema.assert_called_once()
        mock_doi_table.assert_called_once()
        mock_import_table.assert_called_once()
        mock_doi_indexes.assert_called_once()
        mock_import_indexes.assert_called_once()
        mock_permissions.assert_called_once()
        mock_verify.assert_called_once()
    
    @patch.object(DatabaseCreator, 'test_connection')
    def test_create_complete_schema_connection_failure(self, mock_test):
        """Test complete schema creation with connection failure."""
        mock_test.return_value = False
        
        result = self.creator.create_complete_schema()
        
        self.assertFalse(result)
        mock_test.assert_called_once()


if __name__ == '__main__':
    unittest.main()
