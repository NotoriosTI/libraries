import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from shopify.admin.client import ShopifyAdminClient
from shopify.admin.products import ShopifyProductManager


def _load_dotenv_if_present() -> None:
    """Carga variables desde .env para los tests de integración.

    Nota: esto es intencionalmente local a tests (la librería sigue siendo
    "configuración explícita").
    """

    repo_root = Path(__file__).resolve().parents[1]
    dotenv_path = repo_root / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_if_present()


def _get_env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


@pytest.fixture(scope="session")
def product_manager() -> ShopifyProductManager:
    shop_url = _get_env("SHOPIFY_SHOP_URL")
    admin_token = _get_env("SHOPIFY_TOKEN_API_ADMIN")
    api_version = _get_env("SHOPIFY_API_VERSION") or "2025-01"

    if not shop_url or not admin_token:
        pytest.skip(
            "Faltan variables de entorno para tests de integración: "
            "SHOPIFY_SHOP_URL y/o SHOPIFY_TOKEN_API_ADMIN"
        )

    client = ShopifyAdminClient(shop_url=shop_url, admin_token=admin_token, api_version=api_version)
    return ShopifyProductManager(client)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def test_search_products_shows_total_and_payload(product_manager: ShopifyProductManager) -> None:
    query = "pack case"
    limit = _safe_int(_get_env("SHOPIFY_TEST_SEARCH_LIMIT"), 5)

    results: List[Dict[str, Any]] = product_manager.search_products(query, limit=limit)

    print("\n=== ShopifyProductManager.search_products ===")
    print(f"query={query!r} limit={limit}")
    print(f"returned_count={len(results)}")

    stock_values = [r.get("stock_total") for r in results]
    stock_sum = sum(v for v in stock_values if isinstance(v, int))
    print(f"stock_total_sum={stock_sum}")

    print("payload=")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    assert isinstance(results, list)


def test_read_product_info_shows_total_and_payload(product_manager: ShopifyProductManager) -> None:
    identifier = _get_env("SHOPIFY_TEST_PRODUCT_IDENTIFIER")
    if not identifier:
        fallback_query = "10121115631915"
        seed = product_manager.search_products(fallback_query, limit=1)
        if not seed:
            pytest.skip("No se encontró ningún producto para usar como fallback.")
        identifier = str(seed[0]["id"])

    info = product_manager.read_product_info(identifier)

    print("\n=== ShopifyProductManager.read_product_info ===")
    print(f"identifier={identifier!r}")
    print(f"found={info is not None}")

    assert info is not None

    variants = info.get("variants") or []
    images = info.get("images") or []
    print(f"variants_count={len(variants)}")
    print(f"images_count={len(images)}")

    print("payload=")
    print(json.dumps(info, ensure_ascii=False, indent=2))

    assert "id" in info
    assert "title" in info
