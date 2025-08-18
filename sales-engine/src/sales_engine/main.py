"""
Main Entry Point for the Sales Engine Service (Unified Forecast Table)

This script orchestrates the sales data synchronization process. It is the
default command executed by the Docker container.

Key Responsibilities:
- Reads configuration from environment variables.
- Instantiates the DatabaseUpdater.
- Runs the main sync process (`run_update`).
- Executes the unified forecast pipeline.
- Handles high-level logging and returns appropriate exit codes.
"""

import os
import sys

# Imports from within the same package
from .db_updater import DatabaseUpdater, UpdateResult
from .forecaster.forecast_pipeline import run_pipeline

# Import beautiful logging from dev-utils
try:
    from dev_utils import PrettyLogger, log_header, log_success, log_error, log_info, log_warning, timer
except ImportError:
    # Fallback if dev_utils is not available
    print("⚠️  dev_utils not available, using basic logging")
    
    class FallbackLogger:
        def info(self, msg, **kwargs): print(f"ℹ️  {msg}")
        def success(self, msg, **kwargs): print(f"✅ {msg}")
        def error(self, msg, **kwargs): print(f"❌ {msg}")
        def warning(self, msg, **kwargs): print(f"⚠️  {msg}")
        def step(self, msg, **kwargs): print(f"🚀 {msg}")
        def metric(self, name, value, unit="", **kwargs): print(f"📊 {name}: {value} {unit}")
        def table(self, data, title=None): 
            if title: print(f"📋 {title}")
            for k, v in data.items(): print(f"  {k}: {v}")
        def header(self, title, **kwargs): print(f"\n=== {title} ===\n")
    
    logger = FallbackLogger()
    def log_header(title, **kwargs): logger.header(title, **kwargs)
    def log_success(msg, **kwargs): logger.success(msg, **kwargs)
    def log_error(msg, **kwargs): logger.error(msg, **kwargs)
    def log_info(msg, **kwargs): logger.info(msg, **kwargs)
    def log_warning(msg, **kwargs): logger.warning(msg, **kwargs)
    class timer:
        def __init__(self, msg): self.msg = msg
        def __enter__(self): print(f"🏁 Starting {self.msg}..."); return self
        def __exit__(self, *args): print(f"⏱️  Completed {self.msg}")


def run_sync():
    """
    Main function to initialize and run the sales data synchronization.
    """
    # Initialize pretty logger for sales engine
    logger = PrettyLogger("sales-engine") if 'PrettyLogger' in globals() else FallbackLogger()
    
    log_header("🚀 Sales Engine Service (Unified Forecast)", char="=", width=70)
    
    try:
        # --- Configuration from Environment Variables ---
        use_test_odoo = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
        force_full_sync = os.getenv('FORCE_FULL_SYNC', 'false').lower() == 'true'
        test_connections_only = os.getenv('TEST_CONNECTIONS_ONLY', 'false').lower() == 'true'
        skip_forecast = os.getenv('SKIP_FORECAST', 'false').lower() == 'true'
        forecast_only = os.getenv('FORECAST_ONLY', 'false').lower() == 'true'

        logger.info("📋 Configuration loaded from environment", 
                   use_test_odoo=use_test_odoo,
                   force_full_sync=force_full_sync,
                   test_connections_only=test_connections_only,
                   skip_forecast=skip_forecast,
                   forecast_only=forecast_only)

        # The 'with' statement ensures the DatabaseUpdater's __exit__ method
        # is called, which cleanly closes the database connection pool.
        with timer("database initialization"):
            updater = DatabaseUpdater(use_test_odoo=use_test_odoo)
        
        if test_connections_only:
            logger.step("Running connection tests", 1, 1)
            
            with timer("connection tests"):
                db_test = updater.test_connection()
                
            if db_test:
                log_success("✅ All connection tests passed!")
                return 0
            else:
                log_error("❌ Connection tests failed")
                return 1
        elif forecast_only:
            # --- Execute Forecast Pipeline Only ---
            logger.step("Starting forecast pipeline only", 1, 1)
            
            try:
                with timer("forecast pipeline") as forecast_timer:
                    forecast_result = run_pipeline()
                
                # Display forecast metrics
                logger.metric("Total SKUs Forecasted", forecast_result.total_skus_forecasted, "SKUs")
                logger.metric("Total Records Upserted", forecast_result.total_records_upserted, "records")
                
                # Summary table for forecast
                logger.table({
                    "Status": "✅ FORECAST SUCCESS",
                    "Target Period": f"{forecast_result.month:02d}/{forecast_result.year}",
                    "SKUs Forecasted": f"{forecast_result.total_skus_forecasted:,}",
                    "Total Records": f"{forecast_result.total_records_upserted:,}",
                    "Database": "Unified forecast table"
                }, "📊 Forecast Pipeline Summary")
                
                log_success("🎯 Forecast pipeline completed successfully!")
                return 0
                
            except Exception as forecast_error:
                logger.error(f"❌ Forecast pipeline failed: {str(forecast_error)}")
                if os.getenv('DEBUG', 'false').lower() == 'true':
                    import traceback
                    traceback.print_exc()
                return 1
        else:
            # --- Execute the Main Sync Process ---
            logger.step("Starting sales data synchronization", 1, 3)
            
            with timer("sales data sync") as sync_timer:
                result = updater.run_update(force_full_sync=force_full_sync)

            logger.step("Processing sync results", 2, 3)
            
            # Show detailed metrics
            if not result.errors:
                logger.step("Sync completed successfully", 3, 3)
                
                # Display beautiful metrics
                logger.metric("Total Records Upserted", result.upserts_performed, "records")
                logger.metric("New Records", result.new_records, "records")
                logger.metric("Updated Records", result.updated_records, "records")
                logger.metric("Processing Duration", round(result.duration_seconds, 2), "seconds")
                
                # Summary table
                logger.table({
                    "Status": "✅ SUCCESS",
                    "Total Processed": f"{result.upserts_performed:,} records",
                    "New Records": f"{result.new_records:,}",
                    "Updated Records": f"{result.updated_records:,}",
                    "Duration": f"{result.duration_seconds:.2f}s",
                    "Avg Speed": f"{result.upserts_performed/result.duration_seconds:.1f} records/sec" if result.duration_seconds > 0 else "N/A"
                }, "📊 Synchronization Summary")
                
                log_success("🎉 Sales data synchronization completed successfully!")
                
                # --- Execute Forecast Pipeline (if not skipped) ---
                if not skip_forecast:
                    logger.step("Starting forecast pipeline", 1, 2)
                    
                    try:
                        with timer("forecast pipeline") as forecast_timer:
                            forecast_result = run_pipeline()
                        
                        logger.step("Forecast pipeline completed", 2, 2)
                        
                        # Display forecast metrics
                        logger.metric("Total SKUs Forecasted", forecast_result.total_skus_forecasted, "SKUs")
                        logger.metric("Total Records Upserted", forecast_result.total_records_upserted, "records")
                        
                        # Summary table for forecast
                        logger.table({
                            "Status": "✅ FORECAST SUCCESS",
                            "Target Period": f"{forecast_result.month:02d}/{forecast_result.year}",
                            "SKUs Forecasted": f"{forecast_result.total_skus_forecasted:,}",
                            "Total Records": f"{forecast_result.total_records_upserted:,}",
                            "Database": "Unified forecast table"
                        }, "📊 Forecast Pipeline Summary")
                        
                        log_success("🎯 Forecast pipeline completed successfully!")
                        
                    except Exception as forecast_error:
                        logger.error(f"❌ Forecast pipeline failed: {str(forecast_error)}")
                        # Don't fail the entire process, just log the error
                        if os.getenv('DEBUG', 'false').lower() == 'true':
                            import traceback
                            traceback.print_exc()
                else:
                    logger.info("⏭️  Forecast pipeline skipped as requested")
                
                return 0
            else:
                logger.step("Sync completed with errors", 3, 3)
                logger.error(f"❌ Sync failed with {len(result.errors)} error(s)")
                
                for i, error in enumerate(result.errors, 1):
                    logger.error(f"Error {i}: {error}")
                
                return 1

    except Exception as e:
        log_error(f"🔥 An unhandled exception occurred: {str(e)}")
        
        # Show exception details in debug mode
        if os.getenv('DEBUG', 'false').lower() == 'true':
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    # This block is executed when the script is run directly, e.g.,
    # python -m sales_engine.main
    exit_code = run_sync()
    sys.exit(exit_code)
