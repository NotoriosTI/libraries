# models.py
import os
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv

# Load .env at startup (only needed in local_machine mode)
load_dotenv()


# --------------------------------------------------
# Secret Base Class
# --------------------------------------------------
class Secret(BaseModel):
    environment: Literal["local_machine", "production"] = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "local_machine"),
        description="Determines whether to fetch secrets from .env or GCP Secret Manager",
    )
    gcp_project_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("GCP_PROJECT_ID"),
        description="GCP project ID. Required in production mode.",
    )

    @model_validator(mode="after")
    def _validate_gcp_project(self):
        if self.environment == "production" and not self.gcp_project_id:
            raise ValueError(
                "GCP_PROJECT_ID must be set in production mode (via env or constructor)."
            )
        return self

    def _fetch_gcp_secret(self, secret_id: str) -> str:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{self.gcp_project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    def _fetch_env_secret(self, secret_id: str) -> str:
        value = os.getenv(secret_id)
        if value is None:
            raise KeyError(f"❌ Environment variable '{secret_id}' not found")
        return value

    def _get_secret(self, secret_id: str) -> str:
        if self.environment == "production":
            return self._fetch_gcp_secret(secret_id)
        return self._fetch_env_secret(secret_id)

    def _cast_value(self, value: str, target_type: Any) -> Any:
        if isinstance(target_type, str):
            return value
        if isinstance(target_type, int):
            return int(value)
        if isinstance(target_type, float):
            return float(value)
        if isinstance(target_type, bool):
            lower_val = value.lower()
            if lower_val in {"true", "1", "yes"}:
                return True
            if lower_val in {"false", "0", "no"}:
                return False
            raise ValueError(f"Cannot cast '{value}' to bool")
        return value

    def _load_all_fields(self):
        # ✅ use class-level model_fields to fix deprecation warning
        for name, field in self.__class__.model_fields.items():
            if name in {"environment", "gcp_project_id"}:
                continue

            secret_id = field.alias or name
            raw_value = self._get_secret(secret_id)
            casted_value = self._cast_value(raw_value, field.annotation)
            setattr(self, name, casted_value)

    def __init__(self, **data):
        super().__init__(**data)
        self._load_all_fields()


# --------------------------------------------------
# LangSmith
# --------------------------------------------------
class LangSmithSecret(Secret):
    api_key: Optional[str] = Field(default=None, alias="LANGMISH_API_KEY")
    project: Optional[str] = Field(default=None, alias="LANGSMITH_PROJECT")


# --------------------------------------------------
# Odoo
# --------------------------------------------------
class OdooProductionSecret(Secret):
    url: Optional[str] = Field(default=None, alias="ODOO_PROD_URL")
    db: Optional[str] = Field(default=None, alias="ODOO_PROD_DB")
    username: Optional[str] = Field(default=None, alias="ODOO_PROD_USERNAME")
    password: Optional[str] = Field(default=None, alias="ODOO_PROD_PASSWORD")


class OdooTestSecret(Secret):
    url: Optional[str] = Field(default=None, alias="ODOO_TEST_URL")
    db: Optional[str] = Field(default=None, alias="ODOO_TEST_DB")
    username: Optional[str] = Field(default=None, alias="ODOO_TEST_USERNAME")
    password: Optional[str] = Field(default=None, alias="ODOO_TEST_PASSWORD")

# Run as a script for quick testing
if __name__ == "__main__":
    secret = OdooProductionSecret()

    print(f"{secret.url = }")
    print(f"{secret.db = }")
    print(f"{secret.username = }")
    print(f"{secret.password = }")
