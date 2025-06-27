import logging 
import io 
import os 
import time 
import traceback 
from datetime import datetime, date 
from typing import Dict, List, Optional, Any, Tuple, Iterator 
from dataclasses import dataclass 
from contextlib import contextmanager 
from functools import wraps

# Third-party imports
import pandas as pd 
import psycopg2 
import psycopg2.pool 
from psycopg2.extras import execute_values 
from google.cloud import secretmanager 
from google.api_core import exceptions as gcp_exceptions 
import structlog

# Local imports
class SecretManagerError(Exception):
    """Raised when Secret Manager operations fail."""
    pass

class SecretManagerClient:
    """
    Secure Secret Manager client with caching, error handling, and retry logic.
    """
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self.project_id:
            raise ValueError("Project ID must be provided or set via GOOGLE_CLOUD_PROJECT")
        
        self.client = secretmanager.SecretManagerServiceClient()
        self.logger = structlog.get_logger().bind(component="secret_manager")
    
    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """
        Retrieve secret with error handling and retry logic.
        
        Args:
            secret_name: Name of the secret
            version: Version of the secret (default: "latest")
            
        Returns:
            Secret value as string
            
        Raises:
            SecretManagerError: If secret retrieval fails
        """
        resource_name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                response = self.client.access_secret_version(
                    request={"name": resource_name}
                )
                secret_value = response.payload.data.decode('UTF-8')
                
                self.logger.info("Secret retrieved successfully", secret_name=secret_name)
                return secret_value
                
            except gcp_exceptions.NotFound:
                self.logger.error("Secret not found", secret_name=secret_name)
                raise SecretManagerError(f"Secret '{secret_name}' not found")
                
            except gcp_exceptions.PermissionDenied:
                self.logger.error("Access denied to secret", secret_name=secret_name)
                raise SecretManagerError(f"Access denied to secret '{secret_name}'")
                
            except gcp_exceptions.GoogleAPIError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning("Retrying secret retrieval", 
                                      attempt=attempt + 1, delay=delay, error=str(e))
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error("Failed to retrieve secret after retries", 
                                    secret_name=secret_name, error=str(e))
                    raise SecretManagerError(f"Failed to retrieve secret: {e}")
        
        raise SecretManagerError("Unexpected error in secret retrieval")
    
    def get_database_credentials(self) -> Dict[str, str]:
        """
        Retrieve all database credentials from Secret Manager.
        
        Returns:
            Dictionary containing database connection parameters
        """
        try:
            credentials = {
                'host': self.get_secret('db-host'),
                'port': self.get_secret('db-port'),
                'database': self.get_secret('db-name'),
                'user': self.get_secret('automation-admin-user'),
                'password': self.get_secret('automation-admin-password')
            }
            
            self.logger.info("Database credentials retrieved successfully")
            return credentials
            
        except Exception as e:
            self.logger.error("Failed to retrieve database credentials", error=str(e))
            raise SecretManagerError(f"Failed to retrieve database credentials: {e}")
