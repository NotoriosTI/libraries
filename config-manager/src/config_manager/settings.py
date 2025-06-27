"""
Configuration settings for the config-manager package.

This module provides the Settings class, which loads environment variables and secrets
depending on the current environment (production, local_container, or local_machine).
In production, secrets are fetched from Google Cloud Secret Manager. In local environments,
variables are loaded using python-decouple from either a Docker env_file or a local .env file.

Usage:
    from config_manager.settings import Settings
    settings = Settings()
"""

import os
from decouple import config, Csv

# --- The main Settings Class ---
# It will decide how to load variables based on the ENVIRONMENT.
class Settings:
    def __init__(self):
        """
        Initializes the settings object by checking the 'ENVIRONMENT' OS variable.

        - 'production': Actively fetches secrets from Google Secret Manager.
        - 'local_container': Uses python-decouple, expecting variables from a docker-compose env_file.
        - 'local_machine' (default): Uses python-decouple, expecting variables from a local .env file.
        """
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'local_machine')

        if self.ENVIRONMENT == 'production':
            # --- PRODUCTION MODE: Active Fetch from GCP Secret Manager ---
            print("✅ Running in 'production' mode. Fetching secrets from GCP.")
            # We import this library only when needed for production
            from google.cloud import secretmanager
            
            # This project ID must be available as an environment variable in production
            self.GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
            if not self.GCP_PROJECT_ID:
                raise ValueError("GCP_PROJECT_ID environment variable not set in production.")

            # Create a single client to be reused
            gcp_client = secretmanager.SecretManagerServiceClient()

            # Fetch each secret using a helper method
            # Odoo Production
            self.ODOO_PROD_URL = self._fetch_gcp_secret('ODOO_PROD_URL', gcp_client)
            self.ODOO_PROD_DB = self._fetch_gcp_secret('ODOO_PROD_DB', gcp_client)
            self.ODOO_PROD_USERNAME = self._fetch_gcp_secret('ODOO_PROD_USERNAME', gcp_client)
            self.ODOO_PROD_PASSWORD = self._fetch_gcp_secret('ODOO_PROD_PASSWORD', gcp_client)

            # Odoo Test
            self.ODOO_TEST_URL = self._fetch_gcp_secret('ODOO_TEST_URL', gcp_client)
            self.ODOO_TEST_DB = self._fetch_gcp_secret('ODOO_TEST_DB', gcp_client)
            self.ODOO_TEST_USERNAME = self._fetch_gcp_secret('ODOO_TEST_USERNAME', gcp_client)
            self.ODOO_TEST_PASSWORD = self._fetch_gcp_secret('ODOO_TEST_PASSWORD', gcp_client)

            # Langsmith
            self.LANGSMITH_API_KEY = self._fetch_gcp_secret('LANGSMITH_API_KEY', gcp_client)
            self.LANGSMITH_PROJECT = self._fetch_gcp_secret('LANGSMITH_PROJECT', gcp_client)

            # OpenAI
            self.OPENAI_API_KEY = self._fetch_gcp_secret('OPENAI_API_KEY', gcp_client)

            # Slack
            self.SLACK_BOT_TOKEN = self._fetch_gcp_secret('SLACK_BOT_TOKEN', gcp_client)
            self.SLACK_APP_TOKEN = self._fetch_gcp_secret('SLACK_APP_TOKEN', gcp_client)

            # Database
            self.DB_HOST = self._fetch_gcp_secret('DB_HOST', gcp_client)
            self.DB_PORT = self._fetch_gcp_secret('DB_PORT', gcp_client)  
            self.DB_NAME = self._fetch_gcp_secret('DB_NAME', gcp_client)
            self.DB_USER = self._fetch_gcp_secret('DB_USER', gcp_client)
            self.DB_PASSWORD = self._fetch_gcp_secret('DB_PASSWORD', gcp_client)

        elif self.ENVIRONMENT in ('local_container', 'local_machine'):
            # --- LOCAL MODES: Load from .env file using decouple ---
            if self.ENVIRONMENT == 'local_container':
                print("✅ Running in 'local_container' mode. Loading settings from .env file (via docker-compose).")
            else: # 'local_machine'
                print("✅ Running in 'local_machine' mode. Loading settings from .env file directly.")

            # Odoo Production
            self.ODOO_PROD_URL = config('ODOO_PROD_URL')
            self.ODOO_PROD_DB = config('ODOO_PROD_DB')
            self.ODOO_PROD_USERNAME = config('ODOO_PROD_USERNAME')
            self.ODOO_PROD_PASSWORD = config('ODOO_PROD_PASSWORD')

            # Odoo Test
            self.ODOO_TEST_URL = config('ODOO_TEST_URL')
            self.ODOO_TEST_DB = config('ODOO_TEST_DB')
            self.ODOO_TEST_USERNAME = config('ODOO_TEST_USERNAME')
            self.ODOO_TEST_PASSWORD = config('ODOO_TEST_PASSWORD')

            # Langsmith
            self.LANGSMITH_API_KEY = config('LANGSMITH_API_KEY')
            self.LANGSMITH_PROJECT = config('LANGSMITH_PROJECT')

            # OpenAI
            self.OPENAI_API_KEY = config('OPENAI_API_KEY')

            # Slack
            self.SLACK_BOT_TOKEN = config('SLACK_BOT_TOKEN')
            self.SLACK_APP_TOKEN = config('SLACK_APP_TOKEN')
        
        else:
            raise ValueError(f"Unknown ENVIRONMENT: '{self.ENVIRONMENT}'. Must be one of 'production', 'local_container', or 'local_machine'.")
        
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGSMITH_API_KEY"] = self.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = self.LANGSMITH_PROJECT

    def _fetch_gcp_secret(self, secret_id: str, client, cast_to=str):
        """Helper function to fetch a single secret from GCP Secret Manager."""
        try:
            name = f"projects/{self.GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            value = response.payload.data.decode("UTF-8")
            
        except Exception as e:
            print(f"❌ Failed to fetch secret '{secret_id}'. Error: {e}")
            raise e

        print(f"✅ Fetched secret '{secret_id}' successfully.")
        return value
    
    def get_odoo_config(self, use_test: bool = False) -> dict:
        """Get Odoo configuration for sales-engine compatibility."""
        if use_test:
            return {
                'url': self.ODOO_TEST_URL,
                'db': self.ODOO_TEST_DB,
                'username': self.ODOO_TEST_USERNAME,
                'password': self.ODOO_TEST_PASSWORD
            }
        else:
            return {
                'url': self.ODOO_PROD_URL,
                'db': self.ODOO_PROD_DB,
                'username': self.ODOO_PROD_USERNAME,
                'password': self.ODOO_PROD_PASSWORD
            }

    def get_database_config(self) -> dict:
        """Get database configuration for sales-engine."""
        return {
            'project_id': getattr(self, 'GCP_PROJECT_ID', None),
            'host': self.DB_HOST,
            'port': self.DB_PORT,
            'database': self.DB_NAME,
            'user': self.DB_USER,
            'password': self.DB_PASSWORD
        }

# --- Create a single, project-wide instance to be imported everywhere ---
secrets = Settings()
