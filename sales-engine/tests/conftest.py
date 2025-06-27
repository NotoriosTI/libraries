"""
Pytest configuration and fixtures for sales-engine tests.
"""

import pytest
import structlog
from sales_engine.config import configure_structured_logging

@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """Configure logging for tests."""
    configure_structured_logging(
        level="DEBUG",
        environment="development",
        service_name="sales-engine-test",
        enable_json=False  # Human-readable for test output
    )

@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return structlog.get_logger().bind(component="test")