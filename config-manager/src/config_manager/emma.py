from config_manager.common import Secret
from typing import Optional
from pydantic import Field


class OpenAISecret(Secret):
    api_key: Optional[str] = Field(default=None, alias="EMMA_OPENAI_API_KEY")

class EnvironmentSecret(Secret):
    environment: Optional[str] = Field(default="production", alias="EMMA_ENVIRONMENT")

# --------------------------------------------------
# Databases
# --------------------------------------------------
class EmmaDBSecret(Secret):
    host: Optional[str] = Field(default=None, alias="EMMA_DB_HOST")
    name: Optional[str] = Field(default=None, alias="EMMA_DB_NAME")
    port: Optional[str] = Field(default=None, alias="EMMA_DB_PORT")
    username: Optional[str] = Field(default=None, alias="EMMA_DB_USER")
    password: Optional[str] = Field(default=None, alias="EMMA_DB_PASSWORD")


# --------------------------------------------------
# Google Cloud Platform
# --------------------------------------------------
class GoogleDocsSecret(Secret):
    sales_id: Optional[str] = Field(default=None, alias="EMMA_DOCS_SALES_ID")
    docs_summary_id: Optional[str] = Field(default=None, alias="EMMA_DOCS_SUMMARY_ID")


class ServiceAccountSecret(Secret):
    email: Optional[str] = Field(default=None, alias="EMMA_SERVICE_ACCOUNT_EMAIL")


# --------------------------------------------------
# Shopify
# --------------------------------------------------
class ShopifyAPISecret(Secret):
    url: Optional[str] = Field(default=None, alias="EMMA_SHOPIFY_SHOP_URL")
    admin_token: Optional[str] = Field(
        default=None, alias="EMMA_SHOPIFY_TOKEN_API_ADMIN"
    )
    storefront_token: Optional[str] = Field(
        default=None, alias="EMMA_SHOPIFY_TOKEN_API_STOREFRONT"
    )
    api_version: Optional[str] = Field(default=None, alias="EMMA_SHOPIFY_API_VERSION")


# --------------------------------------------------
# Chatwoot
# --------------------------------------------------
class ChatwootSecret(Secret):
    account_id: Optional[str] = Field(default=None, alias="EMMA_CHATWOOT_ACCOUNT_ID")
    token: Optional[str] = Field(default=None, alias="EMMA_CHATWOOT_TOKEN")


# --------------------------------------------------
# Local credentials
# --------------------------------------------------
class LocalCredentialSecret(Secret):
    credential_path: Optional[str] = Field(default=None, alias="EMMA_CREDENTIALS_PATH")
