"""
Main Entry Point for the Refactored Sales Engine Service

This script orchestrates the sales data synchronization process. It is the
default command executed by the Docker container.

Key Responsibilities:
- Reads configuration from environment variables.
- Instantiates the DatabaseUpdater.
- Runs the main sync process (`run_update`).
- Handles high-level logging and returns appropriate exit codes.
"""

import os
import sys
import structlog

# Imports from within the same package
from .db_updater import DatabaseUpdater, UpdateResult

# Configure structured logging for the entire application
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def run_sync():
    """
    Main function to initialize and run the sales data synchronization.
    """
    main_logger = logger.bind(component="main_runner")
    main_logger.info("Starting Refactored Sales Engine Service...")

    try:
        # --- Configuration from Environment Variables ---
        # Determines if the service connects to the production or test Odoo instance.
        use_test_odoo = os.getenv('USE_TEST_ODOO', 'false').lower() == 'true'
        
        # If true, ignores the last sync time and fetches a wider range of data.
        force_full_sync = os.getenv('FORCE_FULL_SYNC', 'false').lower() == 'true'
        
        # A flag to only test connections without running a full sync.
        test_connections_only = os.getenv('TEST_CONNECTIONS_ONLY', 'false').lower() == 'true'

        main_logger.info(
            "Configuration loaded from environment",
            use_test_odoo=use_test_odoo,
            force_full_sync=force_full_sync,
            test_connections_only=test_connections_only
        )

        # The 'with' statement ensures the DatabaseUpdater's __exit__ method
        # is called, which cleanly closes the database connection pool.
        with DatabaseUpdater(use_test_odoo=use_test_odoo) as updater:
            if test_connections_only:
                main_logger.info("Running in connection test mode...")
                if updater.test_connection():
                    main_logger.info("Connection test successful.")
                    return 0  # Success exit code
                else:
                    main_logger.error("Connection test failed.")
                    return 1  # Failure exit code
            else:
                # --- Execute the Main Sync Process ---
                result = updater.run_update(force_full_sync=force_full_sync)

                main_logger.info(
                    "Sync process completed.",
                    status="SUCCESS" if not result.errors else "FAILURE",
                    total_upserted=result.upserts_performed,
                    new_records=result.new_records,
                    updated_records=result.updated_records,
                    duration_seconds=round(result.duration_seconds, 2),
                    errors=result.errors
                )
                return 0 if not result.errors else 1

    except Exception as e:
        main_logger.error(
            "An unhandled exception occurred in the main runner.",
            error=str(e),
            exc_info=True  # Includes stack trace in the log
        )
        return 1  # Return a failure exit code


if __name__ == "__main__":
    # This block is executed when the script is run directly, e.g.,
    # python -m sales_engine.main
    exit_code = run_sync()
    sys.exit(exit_code)
