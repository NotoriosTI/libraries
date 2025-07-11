"""
secret_manager.py

This module provides a client class for securely and efficiently interacting
with Google Cloud Secret Manager, including error handling, retry logic, and
structured logging. It is designed for use in applications that require robust
secret retrieval in production environments, especially on Google Cloud Platform.

Classes:
    - SecretManagerError: Custom exception for Secret Manager errors.
    - SecretManagerClient: Secure client for accessing secrets with error handling and retries.

Dependencies:
    - google-cloud-secret-manager
    - structlog

Author: Bastian Ibañez
"""

# Standard library imports
import os
import time
from typing import Dict, Optional

# Third-party imports
from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions
import structlog


class SecretManagerError(Exception):
    """Custom exception raised when Secret Manager operations fail."""
    pass


class SecretManagerClient:
    """
    Secure Secret Manager client with error handling and retry logic.
    """
    def __init__(self, project_id: Optional[str] = None):
        """
        Initializes the SecretManagerClient.

        Args:
            project_id: The Google Cloud project ID. If not provided, it will be
                        read from the GOOGLE_CLOUD_PROJECT environment variable.

        Raises:
            ValueError: If the project_id is not provided or found in the environment.
        """
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self.project_id:
            raise ValueError("Project ID must be provided or set via GOOGLE_CLOUD_PROJECT env var.")

        self.client = secretmanager.SecretManagerServiceClient()
        self.logger = structlog.get_logger().bind(component="secret_manager")

    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """
        Retrieves a secret with error handling and exponential backoff retry logic.

        Args:
            secret_name: The name of the secret to retrieve.
            version: The version of the secret (default is "latest").

        Returns:
            The secret value as a string.

        Raises:
            SecretManagerError: If secret retrieval fails after all retries.
        """
        resource_name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = self.client.access_secret_version(request={"name": resource_name})
                secret_value = response.payload.data.decode('UTF-8')
                self.logger.info("Secret retrieved successfully", secret_name=secret_name)
                return secret_value
            except gcp_exceptions.NotFound:
                self.logger.error("Secret not found", secret_name=secret_name)
                raise SecretManagerError(f"Secret '{secret_name}' not found.")
            except gcp_exceptions.PermissionDenied:
                self.logger.error("Access denied to secret", secret_name=secret_name)
                raise SecretManagerError(f"Access denied to secret '{secret_name}'.")
            except gcp_exceptions.GoogleAPIError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning(
                        "Retrying secret retrieval",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=delay,
                        error=str(e)
                    )
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(
                        "Failed to retrieve secret after all retries",
                        secret_name=secret_name,
                        error=str(e)
                    )
                    raise SecretManagerError(f"Failed to retrieve secret '{secret_name}' after {max_retries} retries.") from e
        
        # This line should not be reachable in normal flow, but is a safeguard.
        raise SecretManagerError(f"Unexpected error retrieving secret '{secret_name}'.")


    def get_database_credentials(self) -> Dict[str, str]:
        """
        Retrieves all necessary database credentials from Secret Manager.

        This is a convenience method that fetches a predefined set of secrets
        required for a database connection. It uses the correct secret names
        based on the project's naming convention.

        Returns:
            A dictionary containing the database connection parameters.

        Raises:
            SecretManagerError: If any of the required credentials cannot be fetched.
        """
        self.logger.info("Retrieving database credentials...")
        try:
            # CORRECTED: Use uppercase snake_case names to match GCP secrets
            credentials = {
                'host': self.get_secret('DB_HOST'),
                'port': self.get_secret('DB_PORT'),
                'database': self.get_secret('DB_NAME'),
                'user': self.get_secret('DB_USER'),
                'password': self.get_secret('DB_PASSWORD')
            }
            self.logger.info("Database credentials retrieved successfully.")
            return credentials
        except SecretManagerError as e:
            self.logger.error("Failed to retrieve one or more database credentials.", error=str(e))
            # Re-raise to signal that the entire operation failed
            raise SecretManagerError("Failed to retrieve complete database credentials.") from e
