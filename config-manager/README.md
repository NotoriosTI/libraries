Config Manager
Centralized configuration and secret management for all services in the libraries ecosystem.
Overview
Config Manager is a robust configuration management package that provides unified, environment-aware configuration handling across all services in the libraries repository. It seamlessly handles secrets and configuration variables across development, staging, and production environments with automatic environment detection and appropriate secret retrieval strategies.
Key Features

🌍 Multi-Environment Support - Automatic environment detection and configuration loading
🔐 Google Cloud Secret Manager Integration - Secure production secret management
⚙️ Local Development Support - Easy .env file configuration for development
🐳 Container-Ready - Docker and container environment support
🔄 Singleton Pattern - Consistent configuration access across applications
🛡️ Type-Safe Configuration - Structured configuration with helper methods
📊 Multiple Service Support - Pre-configured for Odoo, databases, and external APIs

Architecture
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Application    │───►│ config-manager  │───►│  Configuration  │
│                 │    │                 │    │   Sources       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                ▲                       │
                                │                       ▼
                                │              ┌─────────────────┐
                                │              │                 │
                                └──────────────┤ Environment     │
                                               │ Detection       │
                                               │                 │
                                               └─────────────────┘
                                                       │
                        ┌──────────────────────────────┼──────────────────────────────┐
                        ▼                              ▼                              ▼
               ┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
               │                 │           │                 │           │                 │
               │ local_machine   │           │ local_container │           │   production    │
               │                 │           │                 │           │                 │
               │ .env file       │           │ Environment     │           │ Google Cloud    │
               │ python-decouple │           │ Variables       │           │ Secret Manager  │
               │                 │           │                 │           │                 │
               └─────────────────┘           └─────────────────┘           └─────────────────┘
Installation
From GitHub (Recommended)
bashpip install git+https://github.com/NotoriosTI/libraries.git#subdirectory=config-manager
With Poetry
bash# Add to pyproject.toml
config-manager = {git = "https://github.com/NotoriosTI/libraries.git", subdirectory = "config-manager", tag = "v0.1.0"}

# Install
poetry install
Quick Start
Import and Use
pythonfrom config_manager import secrets

# Access configuration directly
print(f"Environment: {secrets.ENVIRONMENT}")
print(f"Project ID: {secrets.GCP_PROJECT_ID}")

# Get structured configurations
odoo_config = secrets.get_odoo_config(use_test=False)
db_config = secrets.get_database_config()

# Use in your application
from your_odoo_client import OdooClient
client = OdooClient(**odoo_config)
Environment Detection
Config Manager automatically detects the environment based on the ENVIRONMENT variable:
bash# Local development
export ENVIRONMENT=local_machine

# Docker containers
export ENVIRONMENT=local_container

# Production deployment
export ENVIRONMENT=production
Environment Configuration
Local Machine Development (ENVIRONMENT=local_machine)
Setup:

Create a .env file in your project root
Add configuration variables
Config Manager uses python-decouple to load them

.env Example:
bash# Environment
ENVIRONMENT=local_machine

# Google Cloud (optional for local)
GCP_PROJECT_ID=your-project-id

# Odoo Production Configuration
ODOO_PROD_URL=https://your-odoo-domain.com
ODOO_PROD_DB=your_production_database
ODOO_PROD_USERNAME=your_api_user
ODOO_PROD_PASSWORD=your_api_password

# Odoo Test Configuration
ODOO_TEST_URL=https://your-odoo-domain.com
ODOO_TEST_DB=your_test_database
ODOO_TEST_USERNAME=your_test_user
ODOO_TEST_PASSWORD=your_test_password

# Database Configuration
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=sales_db
DB_USER=automation_admin
DB_PASSWORD=your_local_password

# External Services
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=your_project_name
OPENAI_API_KEY=your_openai_key
SLACK_BOT_TOKEN=your_slack_bot_token
SLACK_APP_TOKEN=your_slack_app_token
Container Development (ENVIRONMENT=local_container)
Setup:

Set ENVIRONMENT=local_container
Pass configuration via Docker environment variables or env_file
Config Manager reads from the container environment

Docker Compose Example:
yamlversion: '3.8'
services:
  your-app:
    build: .
    environment:
      - ENVIRONMENT=local_container
      - ODOO_PROD_URL=https://your-odoo-domain.com
      - ODOO_PROD_DB=your_database
      - DB_HOST=postgres
      - DB_PORT=5432
    env_file:
      - .env
Production Deployment (ENVIRONMENT=production)
Setup:

Set ENVIRONMENT=production
Set GCP_PROJECT_ID=your-project-id
Create secrets in Google Cloud Secret Manager
Config Manager automatically fetches secrets using service account credentials

Required Google Cloud Secrets:
bash# Database secrets
gcloud secrets create DB_HOST --data-file=-
gcloud secrets create DB_PORT --data-file=-
gcloud secrets create DB_NAME --data-file=-
gcloud secrets create DB_USER --data-file=-
gcloud secrets create DB_PASSWORD --data-file=-

# Odoo production secrets
gcloud secrets create ODOO_PROD_URL --data-file=-
gcloud secrets create ODOO_PROD_DB --data-file=-
gcloud secrets create ODOO_PROD_USERNAME --data-file=-
gcloud secrets create ODOO_PROD_PASSWORD --data-file=-

# Odoo test secrets (optional)
gcloud secrets create ODOO_TEST_URL --data-file=-
gcloud secrets create ODOO_TEST_DB --data-file=-
gcloud secrets create ODOO_TEST_USERNAME --data-file=-
gcloud secrets create ODOO_TEST_PASSWORD --data-file=-

# External service secrets
gcloud secrets create LANGSMITH_API_KEY --data-file=-
gcloud secrets create LANGSMITH_PROJECT --data-file=-
gcloud secrets create OPENAI_API_KEY --data-file=-
gcloud secrets create SLACK_BOT_TOKEN --data-file=-
gcloud secrets create SLACK_APP_TOKEN --data-file=-
Configuration Methods
Direct Access
pythonfrom config_manager import secrets

# Environment information
print(f"Environment: {secrets.ENVIRONMENT}")
print(f"GCP Project: {secrets.GCP_PROJECT_ID}")

# Odoo configuration
print(f"Odoo Production URL: {secrets.ODOO_PROD_URL}")
print(f"Odoo Test Database: {secrets.ODOO_TEST_DB}")

# Database configuration
print(f"Database Host: {secrets.DB_HOST}")
print(f"Database Port: {secrets.DB_PORT}")

# External services
print(f"OpenAI API Key: {secrets.OPENAI_API_KEY}")
Structured Configuration Helpers
get_odoo_config(use_test=False)
Returns a dictionary with Odoo connection parameters:
python# Production Odoo configuration
prod_config = secrets.get_odoo_config(use_test=False)
# Returns: {
#     'url': 'https://your-odoo-domain.com',
#     'db': 'your_production_database',
#     'username': 'your_api_user',
#     'password': 'your_api_password'
# }

# Test Odoo configuration
test_config = secrets.get_odoo_config(use_test=True)
# Returns test environment configuration

# Usage with Odoo client
from your_odoo_client import OdooClient
client = OdooClient(**prod_config)
get_database_config()
Returns a dictionary with database connection parameters:
pythondb_config = secrets.get_database_config()
# Returns: {
#     'project_id': 'your-project-id',
#     'host': '127.0.0.1',
#     'port': '5432',
#     'database': 'sales_db',
#     'user': 'automation_admin',
#     'password': 'your_password'
# }

# Usage with database connection
import psycopg2
conn = psycopg2.connect(**{k: v for k, v in db_config.items() if k != 'project_id'})
Supported Services
Odoo ERP

Production Environment: Full production Odoo instance configuration
Test Environment: Separate test instance for development and validation
Automatic Switching: Easy toggle between environments

python# Production Odoo
prod_odoo = secrets.get_odoo_config(use_test=False)

# Test Odoo
test_odoo = secrets.get_odoo_config(use_test=True)
Database (PostgreSQL)

Cloud SQL Integration: Optimized for Google Cloud SQL
Local Development: Support for local PostgreSQL instances
Connection Pooling Ready: Configuration suitable for connection pooling

pythondb_config = secrets.get_database_config()
External APIs
LangSmith
pythonapi_key = secrets.LANGSMITH_API_KEY
project = secrets.LANGSMITH_PROJECT
OpenAI
pythonapi_key = secrets.OPENAI_API_KEY
Slack
pythonbot_token = secrets.SLACK_BOT_TOKEN
app_token = secrets.SLACK_APP_TOKEN
Integration Examples
Sales Engine Integration
python# sales-engine using config-manager
from config_manager import secrets

class DatabaseUpdater:
    def __init__(self, use_test_odoo=False):
        # Get database configuration
        self.db_config = secrets.get_database_config()
        
        # Get Odoo configuration
        self.odoo_config = secrets.get_odoo_config(use_test=use_test_odoo)
        
    def connect_to_database(self):
        import psycopg2
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
Multi-Service Application
pythonfrom config_manager import secrets

class MultiServiceApp:
    def __init__(self):
        # Initialize all services with centralized config
        self.setup_odoo()
        self.setup_database()
        self.setup_external_apis()
        
    def setup_odoo(self):
        config = secrets.get_odoo_config()
        self.odoo_client = OdooClient(**config)
        
    def setup_database(self):
        config = secrets.get_database_config()
        self.db_conn = psycopg2.connect(**config)
        
    def setup_external_apis(self):
        if secrets.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=secrets.OPENAI_API_KEY)
            
        if secrets.LANGSMITH_API_KEY:
            os.environ["LANGSMITH_API_KEY"] = secrets.LANGSMITH_API_KEY
            os.environ["LANGSMITH_PROJECT"] = secrets.LANGSMITH_PROJECT
Error Handling
Configuration Validation
Config Manager provides clear error messages for missing or invalid configuration:
pythontry:
    from config_manager import secrets
    config = secrets.get_odoo_config()
except ValueError as e:
    print(f"Configuration error: {e}")
    # Handle missing or invalid configuration
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle other errors
Common Error Scenarios
Missing Environment Variable
bash# Error: ODOO_PROD_URL not set
RuntimeError: Failed to load Odoo configuration: 'ODOO_PROD_URL'
Missing GCP Project ID in Production
bash# Error: GCP_PROJECT_ID not set in production
ValueError: GCP_PROJECT_ID environment variable not set in production.
Secret Not Found in Production
bash# Error: Secret doesn't exist in Secret Manager
❌ Failed to fetch secret 'DB_PASSWORD'. Error: Secret not found
Security Best Practices
Local Development

Never commit .env files - Add .env to .gitignore
Use .env.example - Provide template without actual secrets
Rotate credentials regularly - Use temporary/limited credentials for development

Production Deployment

Use Service Accounts - Dedicated service accounts with minimal permissions
Secret Manager Only - Never use environment variables for production secrets
IAM Roles - Grant only necessary secretmanager.secretAccessor role
Audit Access - Monitor secret access through Cloud Logging

Container Security

No Secrets in Images - Never bake secrets into Docker images
Runtime Injection - Inject secrets at container runtime
Least Privilege - Container processes run with minimal permissions

Google Cloud Setup
Prerequisites
bash# Enable APIs
gcloud services enable secretmanager.googleapis.com

# Create service account
gcloud iam service-accounts create config-manager-sa \
    --display-name="Config Manager Service Account"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:config-manager-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
Secret Creation Script
bash#!/bin/bash
# create-secrets.sh

# Database secrets
echo "your-db-host" | gcloud secrets create DB_HOST --data-file=-
echo "5432" | gcloud secrets create DB_PORT --data-file=-
echo "your_database" | gcloud secrets create DB_NAME --data-file=-
echo "your_user" | gcloud secrets create DB_USER --data-file=-
echo "your_password" | gcloud secrets create DB_PASSWORD --data-file=-

# Odoo production secrets
echo "https://your-odoo.com" | gcloud secrets create ODOO_PROD_URL --data-file=-
echo "your_prod_db" | gcloud secrets create ODOO_PROD_DB --data-file=-
echo "your_api_user" | gcloud secrets create ODOO_PROD_USERNAME --data-file=-
echo "your_api_password" | gcloud secrets create ODOO_PROD_PASSWORD --data-file=-

echo "✅ Secrets created successfully"
Development
Local Development Setup
bash# Clone repository
git clone https://github.com/NotoriosTI/libraries.git
cd libraries/config-manager

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Type checking
poetry run mypy src/
Testing Configuration
python# test_config.py
import pytest
from config_manager import Settings

def test_local_environment():
    # Test local environment configuration
    settings = Settings()
    assert settings.ENVIRONMENT == 'local_machine'
    
def test_odoo_config():
    # Test Odoo configuration helper
    settings = Settings()
    config = settings.get_odoo_config(use_test=False)
    assert 'url' in config
    assert 'db' in config
    assert 'username' in config
    assert 'password' in config

def test_database_config():
    # Test database configuration helper
    settings = Settings()
    config = settings.get_database_config()
    assert 'host' in config
    assert 'port' in config
    assert 'database' in config
Adding New Services
To add support for a new service:

Add configuration variables to the Settings class:

python# In production mode
self.NEW_SERVICE_API_KEY = self._fetch_gcp_secret('NEW_SERVICE_API_KEY', gcp_client)

# In local modes
self.NEW_SERVICE_API_KEY = config('NEW_SERVICE_API_KEY', default='')

Add helper method (optional):

pythondef get_new_service_config(self) -> dict:
    return {
        'api_key': self.NEW_SERVICE_API_KEY,
        'endpoint': self.NEW_SERVICE_ENDPOINT,
    }

Update documentation and examples

Troubleshooting
Common Issues
Import Error
bashModuleNotFoundError: No module named 'config_manager'
Solution: Ensure package is installed: pip install git+https://github.com/NotoriosTI/libraries.git#subdirectory=config-manager
Environment Not Detected
bash# Check environment variable
echo $ENVIRONMENT

# Set explicitly if needed
export ENVIRONMENT=local_machine
Secret Manager Permission Denied
bashgoogle.api_core.exceptions.PermissionDenied: 403 Permission denied
Solution: Verify service account has roles/secretmanager.secretAccessor role
Configuration Missing
bashRuntimeError: Failed to load Odoo configuration
Solution: Check that all required variables are set in .env or Secret Manager
Debug Mode
Enable verbose output:
pythonimport os
os.environ['CONFIG_DEBUG'] = 'true'

from config_manager import secrets
# Will print configuration loading details
Performance Considerations

Singleton Pattern: Settings loaded once per process
Lazy Loading: Secrets fetched only when first accessed
Caching: Secret Manager responses cached during process lifetime
Memory Usage: ~5-10MB for typical configuration sets
Startup Time: ~100-500ms depending on number of secrets

Version Compatibility

Python: 3.13+
Google Cloud Secret Manager: 2.16.0+
python-decouple: 3.8+

Changelog
v0.1.0

Initial release
Multi-environment support
Google Cloud Secret Manager integration
Odoo and database configuration helpers
LangSmith integration

License
MIT License - see LICENSE file for details.
