from config_manager.common import Secret
from typing import Optional
from pydantic import Field


# --------------------------------------------------
# Databases
# --------------------------------------------------
class EmiliaDBSecret(Secret):
    host: Optional[str] = Field(default=None, alias="EMILIA_DB_HOST")
    name: Optional[str] = Field(default=None, alias="EMILIA_DB_NAME")
    port: Optional[str] = Field(default=None, alias="EMILIA_DB_PORT")
    username: Optional[str] = Field(default=None, alias="EMILIA_DB_USER")
    password: Optional[str] = Field(default=None, alias="EMILIA_DB_PASSWORD")

class EnvironmentSecret(Secret):
    emilia_environment: Optional[str] = Field(default=None, alias="EMILIA_ENVIRONMENT")

# --------------------------------------------------
# Chatwoot
# --------------------------------------------------
class ChatwootSecret(Secret):
    token: Optional[str] = Field(default=None, alias="EMILIA_CHATWOOT_TOKEN")
    account_id: Optional[str] = Field(default=None, alias="EMILIA_CHATWOOT_ACCOUNT_ID")


# --------------------------------------------------
# OpenAI
# --------------------------------------------------
class OpenAISecret(Secret):
    api_key: Optional[str] = Field(default=None, alias="EMILIA_OPENAI_API_KEY")

# --------------------------------------------------
# Google Cloud Platform
# --------------------------------------------------
class GoogleDocsSecret(Secret):
    sales_id: Optional[str] = Field(default=None, alias="EMILIA_DOCS_SALES_ID")
    docs_summary_id: Optional[str] = Field(default=None, alias="EMILIA_DOCS_SUMMARY_ID")


class ServiceAccountSecret(Secret):
    email: Optional[str] = Field(default=None, alias="EMILIA_SERVICE_ACCOUNT_EMAIL")


# --------------------------------------------------
# Shopify
# --------------------------------------------------
class ShopifyAPISecret(Secret):
    url: Optional[str] = Field(default=None, alias="EMILIA_SHOPIFY_SHOP_URL")
    admin_token: Optional[str] = Field(
        default=None, alias="EMILIA_SHOPIFY_TOKEN_API_ADMIN"
    )
    storefront_token: Optional[str] = Field(
        default=None, alias="EMILIA_SHOPIFY_TOKEN_API_STOREFRONT"
    )
    api_version: Optional[str] = Field(default=None, alias="EMILIA_SHOPIFY_API_VERSION")


# --------------------------------------------------
# Local credentials
# --------------------------------------------------
class LocalCredentialSecret(Secret):
    credential_path: Optional[str] = Field(
        default=None, alias="EMILIA_CREDENTIALS_PATH"
    )
