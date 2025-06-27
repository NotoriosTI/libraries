"""
Tests for the DatabaseUpdater module.

This test suite covers the functionality of the DatabaseUpdater class, ensuring
it correctly handles data processing, database interactions, and error conditions.
Mocks are used to isolate the class from external services like the database
and Odoo API during unit testing.
"""

import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Module to be tested
from sales_engine.db_updater import DatabaseUpdater, UpdateResult

# --- Test Fixtures and Mock Data ---

@pytest.fixture
def mock_sales_data():
    """Provides mock pandas DataFrames for sales orders and lines."""
    orders_df = pd.DataFrame({
        'salesInvoiceId': ['INV001', 'INV002'],
        'issuedDate': [date(2023, 10, 26), date(2023, 10, 26)],
        # Add other necessary order columns
    })
    lines_df = pd.DataFrame({
        'salesInvoiceId': ['INV001', 'INV001', 'INV002'],
        'items_product_sku': ['SKU01', 'SKU02', 'SKU03'],
        # Add other necessary line columns
    })
    return orders_df, lines_df

@pytest.fixture
def mock_db_connection():
    """Provides a mock database connection and cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    # Simulate fetchone() for get_latest_date_records
    mock_cursor.fetchone.return_value = [date(2023, 10, 25)]
    # Simulate fetchall() for existing pairs
    mock_cursor.fetchall.return_value = {('INV000', 'SKU00')}
    
    return mock_conn

# --- Test Cases for DatabaseUpdater ---

class TestDatabaseUpdater:
    """Test suite for the DatabaseUpdater class."""

    def test_initialization_local_mode(self):
        """
        Tests that the DatabaseUpdater initializes correctly in local mode
        (when connection parameters are provided).
        """
        # In a real scenario, these would come from the config_manager
        # which reads from a local .env file.
        os.environ['ENVIRONMENT'] = 'local_machine'
        
        updater = DatabaseUpdater(use_test_odoo=True)
        
        assert updater.use_test_odoo is True
        assert updater.config.ENVIRONMENT == 'local_machine'
        assert updater.secret_manager is None # No secret manager in local mode

    @patch('sales_engine.db_updater.SecretManagerClient')
    def test_initialization_gcp_mode(self, mock_secret_manager_client):
        """
        Tests that the DatabaseUpdater initializes correctly in production (GCP) mode.
        """
        os.environ['ENVIRONMENT'] = 'production'
        os.environ['GCP_PROJECT_ID'] = 'test-project'
        
        updater = DatabaseUpdater(use_test_odoo=False)
        
        assert updater.use_test_odoo is False
        assert updater.config.ENVIRONMENT == 'production'
        assert updater.secret_manager is not None
        mock_secret_manager_client.assert_called_once_with('test-project')

    @patch('sales_engine.db_updater.read_sales_by_date_range')
    def test_run_update_success_scenario(self, mock_read_sales, mock_sales_data):
        """

        Tests a successful run of the update process, mocking all external calls.
        """
        # --- Arrange ---
        os.environ['ENVIRONMENT'] = 'local_machine'
        
        # Mock the sales data returned from the integration layer
        mock_read_sales.return_value = mock_sales_data
        
        updater = DatabaseUpdater()

        # Mock the database methods to isolate the test
        updater.get_latest_date_records = MagicMock(return_value=(date(2023, 10, 25), set()))
        updater.bulk_load_data = MagicMock(return_value=3) # 3 combined records

        # --- Act ---
        result = updater.run_update()

        # --- Assert ---
        assert isinstance(result, UpdateResult)
        assert result.success_count == 3
        assert result.failure_count == 0
        assert not result.errors
        
        # Verify that the external dependencies were called correctly
        updater.get_latest_date_records.assert_called_once()
        mock_read_sales.assert_called_once()
        updater.bulk_load_data.assert_called_once()
        
        # You can get more specific and assert the content of the DataFrame passed to bulk_load
        loaded_df = updater.bulk_load_data.call_args[0][0]
        assert len(loaded_df) == 3
        assert 'items_product_sku' in loaded_df.columns

    @patch('sales_engine.db_updater.read_sales_by_date_range')
    def test_run_update_no_new_data(self, mock_read_sales):
        """
        Tests the scenario where the Odoo API returns no new data.
        """
        # --- Arrange ---
        os.environ['ENVIRONMENT'] = 'local_machine'
        
        # Mock the Odoo call to return empty DataFrames
        mock_read_sales.return_value = (pd.DataFrame(), pd.DataFrame())
        
        updater = DatabaseUpdater()
        updater.get_latest_date_records = MagicMock(return_value=(date(2023, 10, 25), set()))
        updater.bulk_load_data = MagicMock()

        # --- Act ---
        result = updater.run_update()

        # --- Assert ---
        assert result.success_count == 0
        assert result.failure_count == 0
        # Ensure bulk_load_data was NOT called
        updater.bulk_load_data.assert_not_called()
