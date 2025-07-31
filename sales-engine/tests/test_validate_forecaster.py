"""
Live Integration Validation Script for SalesForecaster.

This script connects to the REAL database to validate the end-to-end
functionality of the SalesForecaster. It uses PrettyLogger to provide
a clear, step-by-step account of the process.

** PRE-REQUISITES **
1.  The Cloud SQL Proxy MUST be running and connected to your database instance.
2.  Your environment must have the necessary database credentials configured
    so that 'config_manager.secrets' can access them.

This script will:
- Establish a real database connection.
- Fetch all historical sales data.
- Process the data and attempt to generate a forecast for every SKU.
- Log the results, including successes, failures, and skipped products.

How to run:
1.  Start the Cloud SQL Proxy.
2.  Run from the root of the library project:
    python -m sales-engine.validation.validate_forecaster_live
"""
import pandas as pd

try:
    from dev_utils import PrettyLogger
    logger = PrettyLogger("sales-forecaster-live-validation")
except ImportError:
    # Fallback logger if dev_utils is not in the path
    class LoggerFallback:
        def info(self, msg, **kwargs): print(f"ℹ️  [INFO] {msg} {kwargs}")
        def error(self, msg, **kwargs): print(f"❌ [ERROR] {msg} {kwargs}")
        def warning(self, msg, **kwargs): print(f"⚠️  [WARN] {msg} {kwargs}")
        def success(self, msg, **kwargs): print(f"✅ [SUCCESS] {msg} {kwargs}")
    logger = LoggerFallback()

# Import the class we want to validate
from sales_engine.db_client.sales_forcaster import SalesForecaster

def run_live_validation():
    """
    Main function to run all live validation steps.
    """
    logger.info("--- Starting SalesForecaster LIVE Validation Script ---")
    logger.warning("This script will connect to the real database.")

    # The 'with' statement ensures the database connection is properly closed.
    with SalesForecaster() as forecaster:
        
        # Step 1: Test the database connection first
        logger.info("Step 1: Testing database connectivity...")
        if not forecaster.db_updater.test_connection():
             logger.error("Halting script: Database connection could not be established.")
             return
        logger.success("Database connection successful.")

        # Step 2: Run the main forecasting process
        logger.info("Step 2: Running the main forecasting process for all SKUs from the database...")
        
        all_forecasts = forecaster.run_forecasting_for_all_skus()
        
        if all_forecasts is None:
            logger.error("Validation failed: The forecasting process did not return any data. Check logs for connection errors.")
            return

        if not all_forecasts:
            logger.warning("The forecasting process ran but did not generate any projections. This might be due to all products having insufficient historical data.")
        else:
            logger.success(f"Main process completed. Generated forecasts for {len(all_forecasts)} SKUs.")

        # --- Verification Step ---
        logger.info("Step 3: Analyzing the output...")

        # Check 1: Is the output a dictionary?
        if isinstance(all_forecasts, dict):
            logger.success("Output is a dictionary.", type=str(type(all_forecasts)))
        else:
            logger.error("Output is NOT a dictionary.", type=str(type(all_forecasts)))
            return

        # Check 2: Display a sample of the results
        if all_forecasts:
            # Get the first SKU from the results to display as a sample
            sample_sku = next(iter(all_forecasts))
            forecast_series = all_forecasts[sample_sku]
            
            logger.info(f"Displaying sample forecast for one SKU: '{sample_sku}'")
            if isinstance(forecast_series, pd.Series) and len(forecast_series) == 12:
                logger.success("Sample forecast appears to have the correct format (Series of length 12).")
                logger.info("Forecasted values:", data=forecast_series.to_dict())
            else:
                logger.error("Sample forecast for '{sample_sku}' has an incorrect format or length.")
        else:
            logger.info("No forecasts were generated, so no sample can be displayed.")


    logger.info("--- Live Validation Script Finished ---")


if __name__ == '__main__':
    run_live_validation()
