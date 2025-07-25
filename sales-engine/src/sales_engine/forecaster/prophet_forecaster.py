"""
Prophet Sales Forecasting Module

This module generates sales forecasts for each product SKU using the Prophet model.
It is designed to integrate seamlessly with the existing sales-engine infrastructure,
leveraging the DatabaseUpdater for all database communications.

Key Features:
- Connects to the database via the shared DatabaseUpdater class.
- Fetches and processes historical sales data into a daily time series.
- Generates daily forecasts for each product SKU using Prophet.
- Includes data validation to handle products with insufficient history.
- Manages resources correctly using a context manager.

Author: Gemini (adapted from user's structure)
"""
import pandas as pd
from prophet import Prophet
from typing import Dict, Optional

# Assuming the script is placed within the sales_engine structure,
# allowing for this relative import.
try:
    from sales_engine.db_updater import DatabaseUpdater, DatabaseConnectionError
except ImportError:
    # Fallback for standalone execution or if structure is different
    from sales_engine.db_updater import DatabaseUpdater, DatabaseConnectionError

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("prophet-forecaster")
except ImportError:
    # A simple logger fallback if dev_utils is not available
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("prophet-forecaster-fallback")


class ProphetSalesForecaster:
    """
    Orchestrates the sales forecasting process using the Prophet model.
    It uses the existing DatabaseUpdater for all database interactions.
    """

    def __init__(self, use_test_odoo: bool = False):
        """
        Initializes the forecaster and the database connection manager.
        """
        self.logger = logger
        self.db_updater = DatabaseUpdater(use_test_odoo=use_test_odoo)
        self.logger.info("ProphetSalesForecaster initialized.")

    def get_historical_sales_data(self) -> Optional[pd.DataFrame]:
        """
        Fetches historical sales data from the database.

        Returns:
            A pandas DataFrame with historical sales data, or None on failure.
        """
        self.logger.info("Fetching historical sales data...")
        query = """
        SELECT
            issueddate,
            items_product_sku,
            SUM(items_quantity) AS daily_units_sold
        FROM
            sales_items
        WHERE
            items_quantity > 0
        GROUP BY
            issueddate, items_product_sku
        ORDER BY
            items_product_sku, issueddate;
        """
        try:
            # Use the connection pool from the DatabaseUpdater instance
            with self.db_updater.get_connection() as conn:
                df = pd.read_sql(query, conn)
            
            if df.empty:
                self.logger.warning("No historical sales data found in the database.")
                return None

            df['issueddate'] = pd.to_datetime(df['issueddate'])
            self.logger.info(f"Successfully fetched {len(df):,} daily sales records.")
            return df
        except DatabaseConnectionError as e:
            self.logger.error("Could not connect to the database to fetch sales data.", extra={"error": str(e)})
            return None
        except Exception as e:
            self.logger.error("An unexpected error occurred while fetching data.", extra={"error": str(e)})
            return None

    def _forecast_single_sku(self, sku_df: pd.DataFrame, steps: int = 90) -> Optional[pd.DataFrame]:
        """
        Generates a forecast for a single product's time series using Prophet.

        Args:
            sku_df: A pandas DataFrame with the sales history for one SKU.
            steps: The number of days to forecast into the future.

        Returns:
            A pandas DataFrame with the forecasted values, or None if forecasting fails.
        """
        sku = sku_df['items_product_sku'].iloc[0]
        
        # Prophet requires at least 2 data points for a forecast.
        if len(sku_df) < 2:
            self.logger.warning(f"Skipping SKU {sku}: insufficient data points ({len(sku_df)}).")
            return None
        
        # Prepare the DataFrame in the format Prophet requires: ['ds', 'y']
        prophet_df = sku_df[['issueddate', 'daily_units_sold']].rename(
            columns={'issueddate': 'ds', 'daily_units_sold': 'y'}
        )

        try:
            # Initialize and fit the Prophet model
            model = Prophet()
            model.fit(prophet_df)

            # Create a future DataFrame for making predictions
            future = model.make_future_dataframe(periods=steps)
            forecast = model.predict(future)
            
            # Return only the relevant forecast columns
            return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        except Exception as e:
            self.logger.error(f"Failed to generate forecast for SKU {sku}.", extra={"error": str(e)})
            return None

    def run_forecasting_for_all_skus(self, forecast_days: int = 90) -> Optional[pd.DataFrame]:
        """
        Main orchestration method to generate forecasts for all products.
        """
        historical_data = self.get_historical_sales_data()
        if historical_data is None:
            return None
            
        all_forecasts = {}
        unique_skus = historical_data['items_product_sku'].unique()
        
        self.logger.info(f"Starting forecasting process for {len(unique_skus)} SKUs...")
        
        for i, sku in enumerate(unique_skus):
            self.logger.info(f"({i+1}/{len(unique_skus)}) Forecasting for SKU: {sku}")
            
            # Isolate the data for the current SKU
            sku_data = historical_data[historical_data['items_product_sku'] == sku]
            
            # Generate the forecast for this SKU
            forecast_result = self._forecast_single_sku(sku_data, steps=forecast_days)
            
            if forecast_result is not None:
                all_forecasts[sku] = forecast_result
        
        if not all_forecasts:
            self.logger.warning("Forecasting process finished, but no projections were generated.")
            return None

        # Combine all forecasts into a single, tidy DataFrame
        final_forecast_df = pd.concat(all_forecasts, names=['sku', 'id']).reset_index()
        
        self.logger.info(f"Forecasting complete. Generated projections for {len(all_forecasts)} SKUs.")
        return final_forecast_df

    def __enter__(self):
        """Enter the context manager, returning the forecaster instance."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager, ensuring the database connection is closed."""
        self.logger.info("Closing database connections...")
        self.db_updater.close()


if __name__ == '__main__':
    # --- Example of how to run the script ---
    # 1. Ensure the Cloud SQL Proxy is running.
    # 2. Ensure your environment variables are set for the DatabaseUpdater.
    
    # The 'with' statement ensures the database connection is managed correctly.
    with ProphetSalesForecaster(use_test_odoo=False) as forecaster:
        # Generate forecasts for the next 90 days
        forecasts_df = forecaster.run_forecasting_for_all_skus(forecast_days=90)
        
        if forecasts_df is not None:
            print("\n--- 🔮 Prophet Sales Forecast Results ---")
            print(forecasts_df.head())
            
            # Optional: Save the results to a CSV file
            try:
                output_path = "prophet_sales_forecast.csv"
                forecasts_df.to_csv(output_path, index=False)
                logger.info(f"Forecast results saved to {output_path}")
            except Exception as e:
                logger.error("Could not save forecast results to CSV.", extra={"error": str(e)})