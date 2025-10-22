from config_manager.common import Secret
from typing import Optional
from pydantic import Field


# --------------------------------------------------
# OpenAI
# --------------------------------------------------
class OpenAISecret(Secret):
    api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")


# --------------------------------------------------
# Anthropic
# --------------------------------------------------
class AnthropicSecret(Secret):
    api_key: Optional[str] = Field(default=None, alias="JUAN_ANTHROPIC_API_KEY")
    llm_model: Optional[str] = Field(default=None, alias="JUAN_ANTHROPIC_LLM_MODEL")


# --------------------------------------------------
# Slack
# --------------------------------------------------
class SlackSecret(Secret):
    bot_token: Optional[str] = Field(default=None, alias="SLACK_BOT_TOKEN")
    app_token: Optional[str] = Field(default=None, alias="SLACK_APP_TOKEN")


# --------------------------------------------------
# Databases
# --------------------------------------------------


class SalesDBSecret(Secret):
    host: Optional[str] = Field(default=None, alias="DB_HOST")
    name: Optional[str] = Field(default=None, alias="DB_NAME")
    port: Optional[str] = Field(default=None, alias="DB_PORT")
    username: Optional[str] = Field(default=None, alias="DB_USER")
    password: Optional[str] = Field(default=None, alias="DB_PASSWORD")


class ProductDBSecret(Secret):
    host: Optional[str] = Field(default=None, alias="PRODUCT_DB_HOST")
    name: Optional[str] = Field(default=None, alias="PRODUCT_DB_NAME")
    port: Optional[str] = Field(default=None, alias="PRODUCT_DB_PORT")
    username: Optional[str] = Field(default=None, alias="PRODUCT_DB_USER")
    password: Optional[str] = Field(default=None, alias="PRODUCT_DB_PASSWORD")


class JuanDBSecret(Secret):
    host: Optional[str] = Field(default=None, alias="JUAN_DB_HOST")
    name: Optional[str] = Field(default=None, alias="JUAN_DB_NAME")
    port: Optional[str] = Field(default=None, alias="JUAN_DB_PORT")
    username: Optional[str] = Field(default=None, alias="JUAN_DB_USER")
    password: Optional[str] = Field(default=None, alias="JUAN_DB_PASSWORD")


class BigqueryDataset(Secret):
    project_name: Optional[str] = Field(default=None, alias="JUAN_BQ_PROJECT_NAME")
    dataset: Optional[str] = Field(default=None, alias="JUAN_BQ_SALES_DATASET")
